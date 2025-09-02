import os
import pytz
import logging

from app.config import settings
from sqlalchemy.orm import Session
from app.mem0_client import mem0_client
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from app.media_processor import media_processor
from app.database import User, Media, Interaction, Memory, get_content_hash, ensure_media_directory

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
            media_metadata=metadata or {}
        )
        
        db.add(media)
        db.commit()
        db.refresh(media)
        logger.info(f"✅ Created media ID: {media.id}")
        return media


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
        user_external_id = f"user:wa:{user.whatsapp_id}" if user else f"user:wa:{user_id}"
        
        # Create memory in Mem0
        mem0_id = mem0_client.create_memory(
            content=content,
            memory_type=memory_type,
            metadata={"user_id": user_id, "interaction_id": interaction_id},
            user_id=user_external_id
        )
        logger.info(f"✅ Created Mem0 memory with ID: {mem0_id}")
        
        logger.debug("💾 Storing memory in local database...")
        # Store in local database
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
        logger.info(f"✅ Created local memory ID: {memory.id}")
        return memory
    
    @staticmethod
    def search_memories(db: Session, user_id: int, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search memories using Mem0 and enrich with local data"""
        logger.info(f"🔍 Searching memories for user {user_id}, query: '{query}', limit: {limit}")
        
        # Get user object to get WhatsApp ID
        user = db.query(User).filter(User.id == user_id).first()
        user_external_id = f"user:wa:{user.whatsapp_id}" if user else f"user:wa:{user_id}"
        
        # Search in Mem0
        logger.debug("🔍 Searching in Mem0...")
        mem0_results = mem0_client.search_memories(query, user_external_id, limit)
        logger.info(f"📊 Found {len(mem0_results)} results in Mem0")
        
        # Enrich with local database data
        logger.debug("🔍 Enriching with local database data...")
        enriched_results = []
        for result in mem0_results:
            memory = db.query(Memory).filter(Memory.mem0_id == result["id"]).first()
            if memory and memory.user_id == user_id:
                enriched_result = {
                    **result,
                    "local_id": memory.id,
                    "interaction_id": memory.interaction_id,
                    "tags": memory.tags,
                    "created_at": memory.created_at.isoformat()
                }
                enriched_results.append(enriched_result)
        
        logger.info(f"✅ Returning {len(enriched_results)} enriched results")
        return enriched_results
    
    @staticmethod
    def list_memories(db: Session, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """List all memories for a user"""
        logger.debug(f"🔍 Listing memories for user {user_id}, limit: {limit}")
        
        # Get user object to get WhatsApp ID
        user = db.query(User).filter(User.id == user_id).first()
        user_external_id = f"user:wa:{user.whatsapp_id}" if user else f"user:wa:{user_id}"
        
        # Get memories from Mem0
        mem0_memories = mem0_client.list_memories(user_external_id, limit)
        
        # Get local memories
        local_memories = db.query(Memory).filter(
            Memory.user_id == user_id
        ).order_by(Memory.created_at.desc()).limit(limit).all()
        
        logger.info(f"📊 Found {len(local_memories)} local memories")
        
        # Combine and format results
        memories = []
        for memory in local_memories:
            memories.append({
                "id": memory.id,
                "mem0_id": memory.mem0_id,
                "content": memory.content,
                "type": memory.memory_type,
                "tags": memory.tags,
                "created_at": memory.created_at.isoformat(),
                "interaction_id": memory.interaction_id
            })
        
        return memories


class AnalyticsService:
    @staticmethod
    def get_analytics_summary(db: Session, user_id: int) -> Dict[str, Any]:
        """Get analytics summary for a user"""
        logger.debug(f"📊 Generating analytics summary for user {user_id}")
        
        # Total memories by type
        memory_types = db.query(Memory.memory_type, db.func.count(Memory.id)).filter(
            Memory.user_id == user_id
        ).group_by(Memory.memory_type).all()
        
        # Total interactions by type
        interaction_types = db.query(Interaction.interaction_type, db.func.count(Interaction.id)).filter(
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
        
        analytics = {
            "memory_types": dict(memory_types),
            "interaction_types": dict(interaction_types),
            "last_ingest_time": last_interaction.created_at.isoformat() if last_interaction else None,
            "top_tags": dict(top_tags),
            "total_memories": sum(count for _, count in memory_types),
            "total_interactions": sum(count for _, count in interaction_types)
        }
        
        logger.info(f"📊 Analytics summary: {analytics['total_memories']} memories, {analytics['total_interactions']} interactions")
        return analytics
