import os
import pytz
import logging

from sqlalchemy import func
from app.config import settings
from sqlalchemy.orm import Session
from app.mem0_client import mem0_client
from typing import Optional, List, Dict, Any
from app.media_processor import media_processor
from datetime import datetime, timedelta, timezone
from app.database import User, Media, Interaction, Memory, Reminder, get_content_hash, ensure_media_directory

# Configure logging
logger = logging.getLogger(__name__)

class UserService:
    @staticmethod
    def get_or_create_user(db: Session, whatsapp_id: str) -> User:
        """Get existing user or create new one"""
        logger.debug(f"🔍 Looking for user with WhatsApp ID: {whatsapp_id}")
        user = db.query(User).filter(User.whatsapp_id == whatsapp_id).first()
        if not user:
            logger.info(f"👤 Creating new user for WhatsApp ID: {whatsapp_id}")
            user = User(whatsapp_id=whatsapp_id)
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"✅ Created user with ID: {user.id}")
        else:
            logger.info(f"✅ Found existing user with ID: {user.id}")
        return user


class InteractionService:
    @staticmethod
    def create_interaction(
        db: Session,
        user_id: int,
        twilio_message_sid: str,
        interaction_type: str,
        content: Optional[str] = None,
        media_id: Optional[int] = None,
        transcript: Optional[str] = None,
        interaction_metadata: Optional[Dict[str, Any]] = None
    ) -> Interaction:
        """Create a new interaction with idempotency check"""
        logger.debug(f"🔍 Checking for existing interaction with SID: {twilio_message_sid}")
        # Check for existing interaction
        existing = db.query(Interaction).filter(
            Interaction.twilio_message_sid == twilio_message_sid
        ).first()
        
        if existing:
            logger.info(f"✅ Found existing interaction ID: {existing.id}")
            return existing
        
        logger.info(f"💾 Creating new interaction for user {user_id}, type: {interaction_type}")
        interaction = Interaction(
            user_id=user_id,
            twilio_message_sid=twilio_message_sid,
            interaction_type=interaction_type,
            content=content,
            media_id=media_id,
            transcript=transcript,
            interaction_metadata=interaction_metadata or {}
        )
        
        db.add(interaction)
        db.commit()
        db.refresh(interaction)
        logger.info(f"✅ Created interaction ID: {interaction.id}")
        return interaction
    
    @staticmethod
    def get_recent_interactions(db: Session, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent interactions for a user"""
        logger.debug(f"🔍 Getting recent interactions for user {user_id}, limit: {limit}")
        interactions = db.query(Interaction).filter(
            Interaction.user_id == user_id
        ).order_by(Interaction.created_at.desc()).limit(limit).all()
        
        logger.info(f"📊 Found {len(interactions)} interactions")
        return [
            {
                "id": interaction.id,
                "type": interaction.interaction_type,
                "content": interaction.content,
                "transcript": interaction.transcript,
                "created_at": interaction.created_at.isoformat(),
                "metadata": interaction.interaction_metadata
            }
            for interaction in interactions
        ]


class MediaService:
    @staticmethod
    def create_or_get_media(
        db: Session,
        content: bytes,
        media_type: str,
        mime_type: str,
        media_metadata: Optional[Dict[str, Any]] = None
    ) -> Media:
        """Create media entry with deduplication"""
        content_hash = get_content_hash(content)
        logger.debug(f"🔍 Checking for existing media with hash: {content_hash[:16]}...")
        
        # Check for existing media with same hash
        existing_media = db.query(Media).filter(Media.content_hash == content_hash).first()
        if existing_media:
            logger.info(f"✅ Found existing media ID: {existing_media.id}")
            return existing_media
        
        logger.info(f"💾 Creating new media entry, type: {media_type}, size: {len(content)} bytes")
        # Ensure media directory exists
        media_dir = ensure_media_directory()
        
        # Save file
        file_extension = mime_type.split('/')[-1]
        filename = f"{content_hash}.{file_extension}"
        file_path = os.path.join(media_dir, filename)
        
        logger.debug(f"💾 Saving file to: {file_path}")
        with open(file_path, 'wb') as f:
            f.write(content)
        
        media = Media(
            content_hash=content_hash,
            media_type=media_type,
            file_path=file_path,
            file_size=len(content),
            mime_type=mime_type,
            media_metadata=media_metadata or {}
        )
        
        db.add(media)
        db.commit()
        db.refresh(media)
        logger.info(f"✅ Created media ID: {media.id}")
        return media

    @staticmethod
    def get_existing_transcript(db: Session, content_hash: str) -> Optional[str]:
        """Get existing transcript for a media file by content hash"""
        logger.debug(f"🔍 Checking for existing transcript with hash: {content_hash[:16]}...")
        
        # Find media by content hash
        media = db.query(Media).filter(Media.content_hash == content_hash).first()
        if not media:
            logger.debug("❌ No existing media found")
            return None
        
        # Find interaction with transcript for this media
        interaction = db.query(Interaction).filter(
            Interaction.media_id == media.id,
            Interaction.transcript.isnot(None)
        ).first()
        
        if interaction and interaction.transcript:
            logger.info(f"✅ Found existing transcript: {interaction.transcript[:50]}...")
            return interaction.transcript
        
        logger.debug("❌ No existing transcript found")
        return None


class MemoryService:
    @staticmethod
    def create_memory(
        db: Session,
        user_id: int,
        interaction_id: int,
        content: str,
        memory_type: str,
        tags: Optional[List[str]] = None
    ) -> Memory:
        """Create a new memory linked to interaction"""
        logger.info(f"🧠 Creating memory in Mem0 for user {user_id}, type: {memory_type}")
        logger.debug(f"📝 Content preview: {content[:100]}...")
        
        # Get user object to get WhatsApp ID
        user = db.query(User).filter(User.id == user_id).first()
        user_external_id = user.whatsapp_id if user else str(user_id)
        
        # Get interaction metadata from local database
        interaction = db.query(Interaction).filter(Interaction.id == interaction_id).first()
        interaction_metadata = interaction.interaction_metadata if interaction else {}
        
        # Prepare metadata for Mem0 using local interaction metadata
        # For image and audio memories, try without metadata to see if that's causing the issue
        if memory_type in ["image", "audio"]:
            mem0_metadata = None
            logger.debug(f"🔍 Trying {memory_type} memory without metadata")
        else:
            mem0_metadata = {
                "user_id": user_id, 
                "interaction_id": interaction_id,
                "memory_type": memory_type,
                "tags": tags or [],
                **interaction_metadata  # Include all local interaction metadata
            }
        
        # Create memory in Mem0
        mem0_id = mem0_client.create_memory(
            content=content,
            memory_type=memory_type,
            metadata=mem0_metadata,
            user_id=user_external_id
        )
        logger.info(f"✅ Created Mem0 memory with ID: {mem0_id}")
        
        logger.debug("💾 Storing memory in local database...")
        
        # Check if memory with this mem0_id already exists
        existing_memory = db.query(Memory).filter(Memory.mem0_id == mem0_id).first()
        if existing_memory:
            logger.info(f"✅ Memory with mem0_id {mem0_id} already exists (ID: {existing_memory.id})")
            logger.info(f"📝 Updating existing memory content from '{existing_memory.content}' to '{content}'")
            
            # Update the existing memory with new content and interaction
            existing_memory.content = content
            existing_memory.interaction_id = interaction_id
            existing_memory.memory_type = memory_type
            existing_memory.tags = tags or []
            
            db.commit()
            db.refresh(existing_memory)
            logger.info(f"✅ Updated existing memory ID: {existing_memory.id}")
            return existing_memory
        
        # Create new memory
        memory = Memory(
            mem0_id=mem0_id,
            user_id=user_id,
            interaction_id=interaction_id,
            content=content,
            memory_type=memory_type,
            tags=tags or []
        )
        
        db.add(memory)
        db.commit()
        db.refresh(memory)
        logger.info(f"✅ Created new local memory ID: {memory.id}")
        return memory
    
    @staticmethod
    def search_memories(db: Session, user_id: int, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search memories using Mem0 and enrich with local data"""
        logger.info(f"🔍 Searching memories for user {user_id}, query: '{query}', limit: {limit}")
        
        # Get user object to get WhatsApp ID
        user = db.query(User).filter(User.id == user_id).first()
        user_external_id = user.whatsapp_id if user else str(user_id)
        
        # Search in Mem0 (with fallback)
        logger.debug("🔍 Searching in Mem0...")
        try:
            mem0_results = mem0_client.search_memories(query, user_external_id, limit)
            logger.info(f"📊 Found {len(mem0_results)} results in Mem0")
        except Exception as e:
            logger.warning(f"⚠️ Failed to search Mem0: {e}")
            logger.info("🔍 Falling back to local search...")
            # Fallback to local search
            local_memories = db.query(Memory).filter(
                Memory.user_id == user_id,
                Memory.content.contains(query)
            ).order_by(Memory.created_at.desc()).limit(limit).all()
            
            mem0_results = []
            for memory in local_memories:
                mem0_results.append({
                    "id": memory.mem0_id,
                    "content": memory.content,
                    "type": memory.memory_type,
                    "metadata": {"user_id": memory.user_id, "interaction_id": memory.interaction_id},
                    "created_at": memory.created_at.isoformat()
                })
        
        # Enrich with local database data
        logger.debug("🔍 Enriching with local database data...")
        enriched_results = []
        for result in mem0_results:
            memory = db.query(Memory).filter(Memory.mem0_id == result["id"]).first()
            if memory and memory.user_id == user_id:
                # Get interaction metadata from local database
                interaction = db.query(Interaction).filter(Interaction.id == memory.interaction_id).first()
                interaction_metadata = interaction.interaction_metadata if interaction else {}
                
                # Use local interaction metadata if Mem0 metadata is empty
                metadata = result.get("metadata", {})
                if not metadata and interaction_metadata:
                    metadata = {
                        "user_id": memory.user_id,
                        "interaction_id": memory.interaction_id,
                        "memory_type": memory.memory_type,
                        "tags": memory.tags or [],
                        **interaction_metadata  # Include all local interaction metadata
                    }
                
                enriched_result = {
                    **result,
                    "local_id": memory.id,
                    "interaction_id": memory.interaction_id,
                    "tags": memory.tags,
                    "created_at": memory.created_at.isoformat(),
                    "type": memory.memory_type,  # Use local database type instead of Mem0 type
                    "metadata": metadata  # Use enriched metadata
                }
                enriched_results.append(enriched_result)
        
        logger.info(f"✅ Returning {len(enriched_results)} enriched results")
        return enriched_results
    
    @staticmethod
    def list_memories(db: Session, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """List all memories for a user - read from local DB as per task requirements"""
        logger.debug(f"🔍 Listing memories for user {user_id}, limit: {limit}")
        
        # Get local memories from DB (newest first) - as specified in task requirements
        local_memories = db.query(Memory).filter(
            Memory.user_id == user_id
        ).order_by(Memory.created_at.desc()).limit(limit).all()
        
        logger.info(f"📊 Found {len(local_memories)} local memories")
        
        # Format results with metadata from local interactions
        memories = []
        for memory in local_memories:
            # Get interaction metadata from local database
            interaction = db.query(Interaction).filter(Interaction.id == memory.interaction_id).first()
            interaction_metadata = interaction.interaction_metadata if interaction else {}
            
            memories.append({
                "id": memory.id,
                "mem0_id": memory.mem0_id,
                "content": memory.content,
                "type": memory.memory_type,
                "tags": memory.tags,
                "created_at": memory.created_at.isoformat(),
                "interaction_id": memory.interaction_id,
                "metadata": {
                    "user_id": memory.user_id,
                    "interaction_id": memory.interaction_id,
                    "memory_type": memory.memory_type,
                    "tags": memory.tags or [],
                    **interaction_metadata  # Include all local interaction metadata
                }
            })
        
        return memories


class ReminderService:
    @staticmethod
    def create_reminder(
        db: Session,
        user_id: int,
        interaction_id: int,
        message: str,
        scheduled_time: datetime,
        user_timezone: str = "UTC",
        reminder_type: str = "message",
        recurrence_pattern: Optional[Dict[str, Any]] = None
    ) -> Reminder:
        """Create a new reminder"""
        logger.info(f"⏰ Creating reminder for user {user_id}, scheduled for {scheduled_time}")
        logger.debug(f"🕐 Scheduled time (original): {scheduled_time}")
        logger.debug(f"🕐 Timezone: {user_timezone}")
        
        # Use local machine timezone
        from datetime import timezone
        local_tz = datetime.now().astimezone().tzinfo
        
        # Make the datetime timezone-aware if it isn't already
        if scheduled_time.tzinfo is None:
            scheduled_time = scheduled_time.replace(tzinfo=local_tz)
        
        logger.debug(f"🕐 Scheduled time (local): {scheduled_time}")
        logger.debug(f"🕐 Current time (local): {datetime.now().astimezone()}")
        
        reminder = Reminder(
            user_id=user_id,
            interaction_id=interaction_id,
            message=message,
            scheduled_time=scheduled_time,
            timezone=user_timezone,
            reminder_type=reminder_type,
            recurrence_pattern=recurrence_pattern or {},
            status="pending"
        )
        
        db.add(reminder)
        db.commit()
        db.refresh(reminder)
        logger.info(f"✅ Created reminder ID: {reminder.id}")
        return reminder
    
    @staticmethod
    def get_pending_reminders(db: Session, limit: int = 100) -> List[Reminder]:
        """Get all pending reminders that are due to be sent"""
        logger.debug(f"🔍 Getting pending reminders, limit: {limit}")
        
        # Use local machine timezone, but convert to naive datetime for comparison
        now = datetime.now().astimezone()  # Use local timezone for comparison
        now_naive = now.replace(tzinfo=None)  # Convert to naive datetime for DB comparison
        logger.debug(f"🕐 Current local time: {now}")
        logger.debug(f"🕐 Current naive time: {now_naive}")
        
        reminders = db.query(Reminder).filter(
            Reminder.status == "pending",
            Reminder.scheduled_time <= now_naive
        ).limit(limit).all()
        
        # Log the scheduled times for debugging
        for reminder in reminders:
            logger.debug(f"⏰ Reminder {reminder.id}: scheduled for {reminder.scheduled_time}, status: {reminder.status}")
        
        logger.info(f"📊 Found {len(reminders)} pending reminders")
        return reminders
    
    @staticmethod
    def get_user_reminders(db: Session, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all reminders for a user"""
        logger.debug(f"🔍 Getting reminders for user {user_id}, limit: {limit}")
        
        reminders = db.query(Reminder).filter(
            Reminder.user_id == user_id
        ).order_by(Reminder.scheduled_time.desc()).limit(limit).all()
        
        logger.info(f"📊 Found {len(reminders)} reminders for user")
        
        return [
            {
                "id": reminder.id,
                "message": reminder.message,
                "scheduled_time": reminder.scheduled_time.isoformat(),
                "timezone": reminder.timezone,
                "status": reminder.status,
                "reminder_type": reminder.reminder_type,
                "created_at": reminder.created_at.isoformat(),
                "sent_at": reminder.sent_at.isoformat() if reminder.sent_at else None,
                "user_id": reminder.user_id,
                "interaction_id": reminder.interaction_id
            }
            for reminder in reminders
        ]
    
    @staticmethod
    def mark_reminder_sent(db: Session, reminder_id: int) -> bool:
        """Mark a reminder as sent"""
        logger.debug(f"✅ Marking reminder {reminder_id} as sent")
        
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if reminder:
            reminder.status = "sent"
            reminder.sent_at = datetime.now().astimezone()
            db.commit()
            logger.info(f"✅ Marked reminder {reminder_id} as sent")
            return True
        else:
            logger.warning(f"⚠️ Reminder {reminder_id} not found")
            return False
    
    @staticmethod
    def cancel_reminder(db: Session, reminder_id: int, user_id: int) -> bool:
        """Cancel a reminder"""
        logger.debug(f"❌ Cancelling reminder {reminder_id} for user {user_id}")
        
        reminder = db.query(Reminder).filter(
            Reminder.id == reminder_id,
            Reminder.user_id == user_id
        ).first()
        
        if reminder and reminder.status == "pending":
            reminder.status = "cancelled"
            db.commit()
            logger.info(f"✅ Cancelled reminder {reminder_id}")
            return True
        else:
            logger.warning(f"⚠️ Reminder {reminder_id} not found or already processed")
            return False


class AnalyticsService:
    @staticmethod
    def get_analytics_summary(db: Session, user_id: int) -> Dict[str, Any]:
        """Get analytics summary for a user"""
        logger.debug(f"📊 Generating analytics summary for user {user_id}")
        
        # Total memories by type
        memory_types = db.query(Memory.memory_type, func.count(Memory.id)).filter(
            Memory.user_id == user_id
        ).group_by(Memory.memory_type).all()
        
        # Total interactions by type
        interaction_types = db.query(Interaction.interaction_type, func.count(Interaction.id)).filter(
            Interaction.user_id == user_id
        ).group_by(Interaction.interaction_type).all()
        
        # Last ingest time
        last_interaction = db.query(Interaction).filter(
            Interaction.user_id == user_id
        ).order_by(Interaction.created_at.desc()).first()
        
        # Top tags (if any)
        all_tags = []
        memories_with_tags = db.query(Memory.tags).filter(
            Memory.user_id == user_id,
            Memory.tags.isnot(None)
        ).all()
        
        for memory_tags in memories_with_tags:
            if memory_tags[0]:
                all_tags.extend(memory_tags[0])
        
        tag_counts = {}
        for tag in all_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Reminder statistics
        total_reminders = db.query(func.count(Reminder.id)).filter(
            Reminder.user_id == user_id
        ).scalar()
        
        pending_reminders = db.query(func.count(Reminder.id)).filter(
            Reminder.user_id == user_id,
            Reminder.status == "pending"
        ).scalar()
        
        analytics = {
            "memory_types": dict(memory_types),
            "interaction_types": dict(interaction_types),
            "last_ingest_time": last_interaction.created_at.isoformat() if last_interaction else None,
            "top_tags": dict(top_tags),
            "total_memories": sum(count for _, count in memory_types),
            "total_interactions": sum(count for _, count in interaction_types),
            "total_reminders": total_reminders,
            "pending_reminders": pending_reminders
        }
        
        logger.info(f"📊 Analytics summary: {analytics['total_memories']} memories, {analytics['total_interactions']} interactions, {analytics['total_reminders']} reminders")
        return analytics
