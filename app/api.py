import os
import logging
import requests

from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import Response, Request
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query
from twilio.twiml.messaging_response import MessagingResponse

from app.database import get_db, create_tables, Interaction, Media, User, Memory
from app.services import (
    UserService, InteractionService, MediaService, 
    MemoryService, AnalyticsService
)
from app.models import (
    MemoryCreate, MemoryResponse, MemorySearchResponse,
    InteractionResponse, AnalyticsSummary, TwilioWebhookRequest,
    WhatsAppResponse
)
from app.config import settings
from app.media_processor import media_processor
from app.intent_classifier import IntentClassifier

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize intent classifier
intent_classifier = IntentClassifier()

def _twiml(msg: str) -> str:
    """Helper function to create TwiML response"""
    safe = (msg or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<Response><Message>{safe}</Message></Response>"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    # Startup
    logger.info("🚀 Starting WhatsApp Memory Assistant...")
    logger.info(f"📊 Database URL: {settings.database_url}")
    logger.info(f"🔧 Debug mode: {settings.debug}")
    logger.info(f"🌐 Host: {settings.host}:{settings.port}")
    
    try:
        create_tables()
        logger.info("✅ Database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Failed to create database tables: {e}")
        raise
    
    logger.info("✅ Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down WhatsApp Memory Assistant...")


app = FastAPI(
    title="WhatsApp Memory Assistant",
    description="A WhatsApp chatbot using Twilio and Mem0 for memory management",
    version="1.0.0",
    lifespan=lifespan
)


@app.post("/webhook")
async def twilio_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle incoming WhatsApp messages from Twilio"""
    logger.info(f"📱 Received webhook from Twilio")
    logger.info(f"📱 Request URL: {request.url}")
    logger.info(f"📱 Request method: {request.method}")
    logger.info(f"📱 User-Agent: {request.headers.get('user-agent', 'Not found')}")
    logger.info(f"📱 Content-Type: {request.headers.get('content-type', 'Not found')}")
    logger.info(f"📱 X-Twilio-Signature: {request.headers.get('x-twilio-signature', 'Not found')}")
    
    # Test immediate response
    logger.info(f"📱 Webhook processing started")
    
    # Log raw request data for debugging
    form_data = await request.form()
    logger.info(f"🔍 Raw form data: {dict(form_data)}")
    
    # Parse the form data into our model
    try:
        webhook_data = TwilioWebhookRequest(**dict(form_data))
        logger.debug(f"Message SID: {webhook_data.MessageSid}")
        logger.debug(f"From: {webhook_data.From}")
        logger.debug(f"Body: {webhook_data.Body}")
        logger.debug(f"NumMedia: {webhook_data.NumMedia}")
    except Exception as e:
        logger.error(f"❌ Failed to parse webhook data: {e}")
        logger.error(f"❌ Form data: {dict(form_data)}")
        return Response(content="Invalid request data", status_code=400)
    
    try:
        # Extract WhatsApp ID (remove 'whatsapp:' prefix)
        whatsapp_id = webhook_data.From.replace('whatsapp:', '')
        logger.info(f"👤 Processing message for user: {whatsapp_id}")
        
        # Get or create user
        logger.debug("🔍 Getting or creating user...")
        user = UserService.get_or_create_user(db, whatsapp_id)
        logger.info(f"✅ User ID: {user.id}")
        
        # Handle different message types
        if webhook_data.NumMedia and int(webhook_data.NumMedia) > 0:
            logger.info("📷 Processing media message...")
            logger.info(f"📷 Media URL: {webhook_data.MediaUrl0}")
            logger.info(f"📷 Media Content Type: {webhook_data.MediaContentType0}")
            logger.info(f"📷 Message Body: {webhook_data.Body}")
            response_message = await handle_media_message(db, user, webhook_data)
        elif webhook_data.Body and webhook_data.Body.strip().lower() == '/list':
            logger.info("📋 Processing list command...")
            response_message = await handle_list_command(db, user)
        elif webhook_data.Body:
            logger.info("💬 Processing text message...")
            response_message = await handle_text_message(db, user, webhook_data, request)
        else:
            logger.warning("⚠️ Received message with no body or media")
            response_message = "I received your message but couldn't process it. Please send text, images, or voice notes."
        
        # Log response message (handle both string and dict responses)
        if isinstance(response_message, dict):
            logger.info(f"📤 Sending response with {len(response_message.get('image_memories', []))} images: {response_message.get('message', '')[:100]}...")
        else:
            logger.info(f"📤 Sending response: {response_message[:100]}...")
        
        # Return TwiML response
        response = MessagingResponse()
        
        # Check if response_message is a dict with image memories
        if isinstance(response_message, dict) and "image_memories" in response_message:
            # Send text message first
            response.message(response_message["message"])
            
            # Send images as media messages
            for image_memory in response_message["image_memories"]:
                if image_memory.get("image_url"):
                    # Convert relative URL to absolute URL for Twilio
                    # Use the request's host to construct the full URL
                    request_host = request.headers.get("host", "localhost:8000")
                    protocol = "https" if "ngrok" in request_host else "http"
                    image_url = f"{protocol}://{request_host}{image_memory['image_url']}"
                    response.message("").media(image_url)
        else:
            # Regular text response
            response.message(response_message)
        
        twiml_content = str(response)
        logger.info(f"📤 Final TwiML response: {twiml_content}")
        logger.info(f"📤 Response status: 200 OK")
        
        # Return proper TwiML response for Twilio with explicit headers
        response_obj = Response(
            content=twiml_content, 
            media_type="application/xml",
            headers={
                "Content-Type": "application/xml",
                "Cache-Control": "no-cache",
                "Access-Control-Allow-Origin": "*"
            },
            status_code=200
        )
        
        logger.info(f"📤 Response object created successfully")
        return response_obj
        
    except Exception as e:
        logger.error(f"❌ Error processing webhook: {str(e)}", exc_info=True)
        response = MessagingResponse()
        response.message("Sorry, I encountered an error processing your message. Please try again.")
        twiml_content = str(response)
        logger.debug(f"📤 Error TwiML content: {twiml_content}")
        
        return Response(
            content=twiml_content, 
            media_type="application/xml",
            headers={
                "Content-Type": "application/xml"
            }
        )


async def handle_text_message(db: Session, user, request: TwilioWebhookRequest, http_request: Request):
    """Handle text messages"""
    logger.debug(f"📝 Processing text message: {request.Body}")
    
    # Check if it's a command
    if request.Body.startswith('/'):
        command = request.Body.lower().strip()
        if command == '/list':
            logger.info("📋 Processing /list command...")
            # Create interaction for the command
            interaction = InteractionService.create_interaction(
                db=db,
                user_id=user.id,
                twilio_message_sid=request.MessageSid,
                interaction_type="command",
                content=request.Body
            )
            logger.info(f"✅ Created command interaction ID: {interaction.id}")
            return await handle_list_command(db, user)
        else:
            logger.warning(f"⚠️ Unknown command: {request.Body}")
            return "I don't recognize that command. Use /list to see your memories."
    else:
        # Use intent classification to determine if this is a search query or new memory
        logger.debug("🤖 Classifying message intent...")
        intent_result = await intent_classifier.classify_intent(request.Body, user.whatsapp_id)
        logger.info(f"✅ Intent classified as: {intent_result['intent']} (confidence: {intent_result['confidence']})")
        
        if intent_result['intent'] == 'search':
            # Handle as search query
            logger.info("🔍 Processing as search query...")
            search_query = intent_result.get('extracted_query', request.Body)
            
            # Create interaction for the search
            interaction = InteractionService.create_interaction(
                db=db,
                user_id=user.id,
                twilio_message_sid=request.MessageSid,
                interaction_type="search",
                content=request.Body,
                interaction_metadata={
                    "intent_classification": intent_result,
                    "search_query": search_query
                }
            )
            logger.info(f"✅ Created search interaction ID: {interaction.id}")
            
            return await handle_search_query(db, user, search_query, http_request)
        else:
            # Handle as new memory
            logger.info("💾 Processing as new memory...")
            
            # Create interaction
            interaction = InteractionService.create_interaction(
                db=db,
                user_id=user.id,
                twilio_message_sid=request.MessageSid,
                interaction_type="text",
                content=request.Body,
                interaction_metadata={
                    "intent_classification": intent_result
                }
            )
            logger.info(f"✅ Created interaction ID: {interaction.id}")
            
            logger.debug("🧠 Creating memory in Mem0...")
            
            # Use the updated content from intent classification (already processed with exact date if needed)
            enhanced_content = intent_result.get('updated_content', request.Body)
            logger.info(f"📅 Using content: {enhanced_content}")
            
            # Create memory
            memory = MemoryService.create_memory(
                db=db,
                user_id=user.id,
                interaction_id=interaction.id,
                content=enhanced_content,
                memory_type="text"
            )
            logger.info(f"✅ Created memory ID: {memory.id} (Mem0 ID: {memory.mem0_id})")
            
            # Provide feedback based on whether content was updated
            if enhanced_content != request.Body:
                return f"I've saved your memory: {enhanced_content}"
            else:
                return "I've saved your text message as a memory! You can ask me about it later."


async def handle_media_message(db: Session, user, request: TwilioWebhookRequest):
    """Handle media messages (images, audio)"""
    logger.info(f"📷 Processing media message...")
    logger.debug(f"Media URL: {request.MediaUrl0}")
    logger.debug(f"Media Content Type: {request.MediaContentType0}")
    
    try:
        # Process first media file (support for multiple media files can be added)
        media_url = request.MediaUrl0
        media_content_type = request.MediaContentType0
        
        if not media_url or not media_content_type:
            logger.error("❌ Missing media URL or content type")
            return "I couldn't process the media file. Please try again."
        
        logger.debug("⬇️ Downloading media from Twilio...")
        # Download media from Twilio
        auth = (settings.twilio_account_sid, settings.twilio_auth_token)
        media_data = await media_processor.download_media(media_url, auth)
        logger.info(f"✅ Downloaded media: {len(media_data)} bytes")
        
        # Determine media type
        if media_content_type.startswith('image/'):
            media_type = "image"
            # Create a more descriptive content for the image
            content = f"Image uploaded by user: {request.Body if request.Body else 'No caption'}"
            logger.info("🖼️ Processing image...")
        elif media_content_type.startswith('audio/'):
            media_type = "audio"
            logger.info("🎵 Processing audio...")
            # Transcribe audio
            logger.debug("🎤 Transcribing audio with Whisper...")
            transcript = await media_processor.transcribe_audio(media_data, media_content_type)
            content = f"Audio transcript: {transcript}"
            logger.info(f"✅ Transcription: {transcript}")
        else:
            media_type = "other"
            content = f"Media file: {media_content_type}"
            logger.warning(f"⚠️ Unknown media type: {media_content_type}")
        
        logger.debug("📊 Getting media metadata...")
        # Get media metadata
        metadata = await media_processor.get_media_metadata(media_data, media_content_type)
        logger.debug(f"📊 Metadata: {metadata}")
        
        logger.debug("💾 Creating or getting media entry...")
        # Create or get media entry (deduplication)
        media = MediaService.create_or_get_media(
            db=db,
            content=media_data,
            media_type=media_type,
            mime_type=media_content_type,
            media_metadata=metadata
        )
        logger.info(f"✅ Media ID: {media.id}")
        
        logger.debug("💾 Creating interaction...")
        # Create interaction
        interaction = InteractionService.create_interaction(
            db=db,
            user_id=user.id,
            twilio_message_sid=request.MessageSid,
            interaction_type=media_type,
            media_id=media.id,
            transcript=transcript if media_type == "audio" else None,
            interaction_metadata=metadata
        )
        logger.info(f"✅ Created interaction ID: {interaction.id}")
        
        logger.debug("🧠 Creating memory in Mem0...")
        # Create memory
        memory = MemoryService.create_memory(
            db=db,
            user_id=user.id,
            interaction_id=interaction.id,
            content=content,
            memory_type=media_type
        )
        logger.info(f"✅ Created memory ID: {memory.id} (Mem0 ID: {memory.mem0_id})")
        
        response_message = f"I've saved your {media_type} as a memory!"
        if media_type == "audio" and transcript:
            response_message += f" I transcribed it as: '{transcript}'"
        
        return response_message
        
    except Exception as e:
        logger.error(f"❌ Error processing media: {str(e)}", exc_info=True)
        return "Sorry, I couldn't process your media file. Please try again."


async def handle_list_command(db: Session, user):
    """Handle /list command"""
    logger.info("📋 Processing /list command...")
    
    try:
        logger.debug("🔍 Retrieving memories from database...")
        memories = MemoryService.list_memories(db, user.id, limit=10)
        logger.info(f"📊 Found {len(memories)} memories")
        
        if not memories:
            logger.info("📭 No memories found for user")
            return "You don't have any memories yet. Send me text, images, or voice notes to create memories!"
        
        # Format memories for WhatsApp
        memory_list = []
        for i, memory in enumerate(memories[:5], 1):  # Limit to 5 for WhatsApp
            memory_list.append(f"{i}. {memory['content'][:100]}... ({memory['type']})")
        
        message = "Your recent memories:\n" + "\n".join(memory_list)
        
        if len(memories) > 5:
            message += f"\n\n... and {len(memories) - 5} more memories"
        
        logger.info(f"📤 Sending memory list: {len(memories)} memories")
        return message
        
    except Exception as e:
        logger.error(f"❌ Error listing memories: {str(e)}", exc_info=True)
        return "Sorry, I couldn't retrieve your memories. Please try again."


async def handle_search_query(db: Session, user, query: str, http_request: Request):
    """Handle search queries with image support"""
    logger.info(f"🔍 Processing search query: '{query}'")
    
    try:
        logger.debug("🔍 Searching memories...")
        memories = MemoryService.search_memories(db, user.id, query, limit=5)
        logger.info(f"📊 Found {len(memories)} matching memories")
        
        # Debug: Log the structure of first few memories
        for i, memory in enumerate(memories[:3]):
            logger.debug(f"🔍 Memory {i+1} structure: {memory}")
        
        # Enhance memories with image URLs if they're images
        enhanced_memories = []
        logger.debug(f"🔍 Processing {len(memories)} memories for image enhancement")
        
        for i, memory in enumerate(memories):
            logger.debug(f"🔍 Memory {i+1}: type={memory.get('type')}, interaction_id={memory.get('interaction_id')}")
            
            if memory.get('type') == 'image':
                logger.debug(f"🖼️ Found image memory, interaction_id: {memory.get('interaction_id')}")
                
                # Get image file path from interaction
                interaction = db.query(Interaction).filter(
                    Interaction.id == memory.get('interaction_id')
                ).first()
                
                if interaction:
                    logger.debug(f"✅ Found interaction, media_id: {interaction.media_id}")
                    
                    if interaction.media_id:
                        media = db.query(Media).filter(Media.id == interaction.media_id).first()
                        if media:
                            # Add image URL to memory
                            file_extension = media.mime_type.split('/')[-1]
                            memory['image_url'] = f"/media/{media.content_hash}.{file_extension}"
                            logger.info(f"🖼️ Added image URL: {memory['image_url']}")
                        else:
                            logger.warning(f"⚠️ Media not found for media_id: {interaction.media_id}")
                    else:
                        logger.warning(f"⚠️ Interaction has no media_id: {interaction.id}")
                else:
                    logger.warning(f"⚠️ Interaction not found for id: {memory.get('interaction_id')}")
            else:
                logger.debug(f"📝 Non-image memory: {memory.get('type')}")
            
            enhanced_memories.append(memory)
        
        memories = enhanced_memories
        
        if not memories:
            logger.info("📭 No matching memories found")
            return f"I couldn't find any memories matching '{query}'. Try asking about something else or use /list to see all your memories."
        
        # Format search results for WhatsApp
        if len(memories) == 1:
            memory = memories[0]
            
            # Format the date/time information
            created_at = memory.get('created_at')
            if created_at:
                try:
                    from datetime import datetime
                    import pytz
                    
                    # Parse the ISO timestamp (assuming it's in UTC)
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    
                    # Convert to local timezone (you can adjust this)
                    local_tz = pytz.timezone('Asia/Kolkata')  # IST timezone
                    local_dt = dt.astimezone(local_tz)
                    
                    formatted_date = local_dt.strftime('%A, %B %d, %Y at %I:%M %p')
                    date_info = f"\n📅 Date: {formatted_date}"
                except Exception as e:
                    logger.error(f"❌ Error formatting date: {e}")
                    date_info = f"\n📅 Date: {created_at}"
            else:
                date_info = ""
            
            message = f"Found this memory:\n\n{memory['content'][:300]}...{date_info}"
            if len(memory['content']) > 300:
                message += "\n\n(Message truncated)"
            
            # Check if it's an image memory
            if memory.get('type') == 'image' and memory.get('image_url'):
                # Return dictionary format for image memories (single or multiple)
                return {
                    "message": message,
                    "image_memories": [memory]
                }
            else:
                # Return simple string for non-image memories
                return message
        else:
            memory_list = []
            image_memories = []
            
            for i, memory in enumerate(memories[:3], 1):  # Limit to 3 for WhatsApp
                content_preview = memory['content'][:80] + "..." if len(memory['content']) > 80 else memory['content']
                memory_type_indicator = " 📷" if memory.get('type') == 'image' else ""
                
                # Add date information
                created_at = memory.get('created_at')
                if created_at:
                    try:
                        from datetime import datetime
                        import pytz
                        
                        # Parse the ISO timestamp (assuming it's in UTC)
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        
                        # Convert to local timezone
                        local_tz = pytz.timezone('Asia/Kolkata')  # IST timezone
                        local_dt = dt.astimezone(local_tz)
                        
                        formatted_date = local_dt.strftime('%B %d, %Y')
                        date_info = f" ({formatted_date})"
                    except Exception as e:
                        logger.error(f"❌ Error formatting date: {e}")
                        date_info = f" ({created_at[:10]})"  # Just the date part
                else:
                    date_info = ""
                
                memory_list.append(f"{i}. {content_preview}{memory_type_indicator}{date_info}")
                
                # Collect image memories for media response
                if memory.get('type') == 'image' and memory.get('image_url'):
                    image_memories.append(memory)
            
            message = f"Found {len(memories)} memories matching '{query}':\n\n" + "\n".join(memory_list)
            
            if len(memories) > 3:
                message += f"\n\n... and {len(memories) - 3} more results"
            
            # Return both message and image memories for media response
            return {
                "message": message,
                "image_memories": image_memories
            }
        
        logger.info(f"📤 Sending search results: {len(memories)} memories")
        return message
        
    except Exception as e:
        logger.error(f"❌ Error searching memories: {str(e)}", exc_info=True)
        return "Sorry, I couldn't search your memories right now. Please try again."


@app.post("/memories", response_model=MemoryResponse)
async def create_memory(
    memory: MemoryCreate,
    db: Session = Depends(get_db)
):
    """Create a new memory"""
    try:
        # For API, we need to specify a user_id (in production, this would come from auth)
        # For demo purposes, we'll use a default user
        user = await UserService.get_or_create_user(db, "demo_user")
        
        # Create a dummy interaction for the memory
        interaction = InteractionService.create_interaction(
            db=db,
            user_id=user.id,
            twilio_message_sid=f"api_{memory.content[:20]}",
            interaction_type=memory.memory_type,
            content=memory.content
        )
        
        # Create memory
        memory_obj = MemoryService.create_memory(
            db=db,
            user_id=user.id,
            interaction_id=interaction.id,
            content=memory.content,
            memory_type=memory.memory_type,
            tags=memory.tags
        )
        
        return MemoryResponse(
            id=memory_obj.id,
            mem0_id=memory_obj.mem0_id,
            content=memory_obj.content,
            memory_type=memory_obj.memory_type,
            tags=memory_obj.tags,
            created_at=memory_obj.created_at.isoformat(),
            interaction_id=memory_obj.interaction_id
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memories", response_model=List[MemorySearchResponse])
async def search_memories(
    query: str = Query(..., description="Search query"),
    limit: int = Query(10, description="Maximum number of results"),
    db: Session = Depends(get_db)
):
    """Search memories"""
    try:
        # For demo purposes, use a default user
        user = UserService.get_or_create_user(db, "demo_user")
        
        memories = MemoryService.search_memories(db, user.id, query, limit)
        return memories
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memories/list", response_model=List[MemoryResponse])
async def list_memories(
    limit: int = Query(50, description="Maximum number of results"),
    db: Session = Depends(get_db)
):
    """List all memories"""
    try:
        # For demo purposes, use a default user
        user = UserService.get_or_create_user(db, "demo_user")
        
        memories = MemoryService.list_memories(db, user.id, limit)
        return [
            MemoryResponse(
                id=memory["id"],
                mem0_id=memory["mem0_id"],
                content=memory["content"],
                memory_type=memory["type"],
                tags=memory["tags"],
                created_at=memory["created_at"],
                interaction_id=memory["interaction_id"]
            )
            for memory in memories
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/interactions/recent", response_model=List[InteractionResponse])
async def get_recent_interactions(
    limit: int = Query(10, description="Maximum number of results"),
    db: Session = Depends(get_db)
):
    """Get recent interactions"""
    try:
        # For demo purposes, use a default user
        user = UserService.get_or_create_user(db, "demo_user")
        
        interactions = InteractionService.get_recent_interactions(db, user.id, limit)
        return [
            InteractionResponse(
                id=interaction["id"],
                type=interaction["type"],
                content=interaction["content"],
                transcript=interaction["transcript"],
                created_at=interaction["created_at"],
                metadata=interaction["metadata"]
            )
            for interaction in interactions
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(db: Session = Depends(get_db)):
    """Get analytics summary"""
    try:
        # For demo purposes, use a default user
        user = UserService.get_or_create_user(db, "demo_user")
        
        analytics = AnalyticsService.get_analytics_summary(db, user.id)
        return AnalyticsSummary(**analytics)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root_get():
    """Root GET handler for Twilio validation"""
    return Response(content=_twiml("Memory Saved"), media_type="application/xml; charset=utf-8")


@app.post("/")
async def root_post():
    """Root POST handler for Twilio validation"""
    return Response(content=_twiml("Memory Saved"), media_type="application/xml; charset=utf-8")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"message": "WhatsApp Memory Assistant API", "status": "running"}


@app.get("/media/{filename}")
async def serve_media(filename: str):
    """Serve media files"""
    media_path = f"media/{filename}"
    if os.path.exists(media_path):
        return FileResponse(media_path)
    else:
        raise HTTPException(status_code=404, detail="Media not found")


@app.get("/test-webhook")
async def test_webhook():
    """Test webhook endpoint"""
    response = MessagingResponse()
    response.message("Test message from WhatsApp Memory Assistant!")
    twiml_content = str(response)
    logger.info(f"📤 Test TwiML content: {twiml_content}")
    
    return Response(
        content=twiml_content, 
        media_type="application/xml",
        headers={
            "Content-Type": "application/xml"
        }
    )


@app.post("/test-webhook")
async def test_webhook_post():
    """Test webhook POST endpoint"""
    response = MessagingResponse()
    response.message("Test POST message from WhatsApp Memory Assistant!")
    twiml_content = str(response)
    logger.info(f"📤 Test POST TwiML content: {twiml_content}")
    
    return Response(
        content=twiml_content, 
        media_type="application/xml",
        headers={
            "Content-Type": "application/xml"
        }
    )


@app.get("/test/reset-all-data")
async def reset_all_data(db: Session = Depends(get_db)):
    """PRIVATE TESTING ENDPOINT: Delete all data from database and Mem0"""
    logger.warning("🧨 RESET ALL DATA ENDPOINT CALLED - DELETING ALL DATA")
    
    try:
        # Delete all data from local database
        logger.info("🗑️ Deleting all data from local database...")
        
        # Delete in correct order to respect foreign key constraints
        db.query(Memory).delete()
        db.query(Interaction).delete()
        db.query(Media).delete()
        db.query(User).delete()
        
        db.commit()
        logger.info("✅ All local database data deleted")
        
        # Delete all data from Mem0
        logger.info("🗑️ Deleting all data from Mem0...")
        
        # Get all users from Mem0 and delete their memories
        # Note: This is a simplified approach - in production you'd want more granular control
        try:
            # Delete memories for all users (this is a test endpoint)
            # You might need to adjust this based on your Mem0 API capabilities
            logger.info("⚠️ Mem0 deletion not implemented - please manually clear Mem0 data")
            logger.info("💡 You can use Mem0's web interface or API to clear data")
        except Exception as e:
            logger.error(f"❌ Error deleting Mem0 data: {e}")
        
        # Delete media files from filesystem
        logger.info("🗑️ Deleting media files...")
        media_dir = "media"
        if os.path.exists(media_dir):
            for filename in os.listdir(media_dir):
                file_path = os.path.join(media_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        logger.debug(f"🗑️ Deleted file: {filename}")
                except Exception as e:
                    logger.error(f"❌ Error deleting file {filename}: {e}")
            logger.info("✅ Media files deleted")
        else:
            logger.info("ℹ️ Media directory doesn't exist")
        
        return {
            "status": "success",
            "message": "All data has been reset",
            "details": {
                "database": "cleared",
                "mem0": "manual_clear_required",
                "media_files": "deleted"
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error resetting data: {e}", exc_info=True)
        db.rollback()
        return {
            "status": "error",
            "message": f"Error resetting data: {str(e)}"
        }
