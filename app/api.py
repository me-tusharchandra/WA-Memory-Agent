import logging
import requests

from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import Response, Request
from fastapi import FastAPI, Depends, HTTPException, Query
from twilio.twiml.messaging_response import MessagingResponse

from app.database import get_db, create_tables
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

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def _twiml(msg: str) -> str:
    """Helper function to create TwiML response"""
    safe = (msg or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<Response><Message>{safe}</Message></Response>"


app = FastAPI(
    title="WhatsApp Memory Assistant",
    description="A WhatsApp chatbot using Twilio and Mem0 for memory management",
    version="1.0.0"
)

@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup"""
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


@app.post("/webhook")
async def twilio_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle incoming WhatsApp messages from Twilio"""
    logger.info(f"📱 Received webhook from Twilio")
    
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
            response_message = await handle_media_message(db, user, webhook_data)
        elif webhook_data.Body and webhook_data.Body.strip().lower() == '/list':
            logger.info("📋 Processing list command...")
            response_message = await handle_list_command(db, user)
        elif webhook_data.Body:
            logger.info("💬 Processing text message...")
            response_message = await handle_text_message(db, user, webhook_data)
        else:
            logger.warning("⚠️ Received message with no body or media")
            response_message = "I received your message but couldn't process it. Please send text, images, or voice notes."
        
        logger.info(f"📤 Sending response: {response_message[:100]}...")
        
        # Return TwiML response
        response = MessagingResponse()
        response.message(response_message)
        return Response(content=str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"❌ Error processing webhook: {str(e)}", exc_info=True)
        response = MessagingResponse()
        response.message("Sorry, I encountered an error processing your message. Please try again.")
        return Response(content=str(response), media_type="application/xml")


async def handle_text_message(db: Session, user, request: TwilioWebhookRequest):
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
        # Handle regular text message
        logger.debug("💾 Creating interaction for text message...")
        # Create interaction
        interaction = InteractionService.create_interaction(
            db=db,
            user_id=user.id,
            twilio_message_sid=request.MessageSid,
            interaction_type="text",
            content=request.Body
        )
        logger.info(f"✅ Created interaction ID: {interaction.id}")
        
        logger.debug("🧠 Creating memory in Mem0...")
        # Create memory
        memory = MemoryService.create_memory(
            db=db,
            user_id=user.id,
            interaction_id=interaction.id,
            content=request.Body,
            memory_type="text"
        )
        logger.info(f"✅ Created memory ID: {memory.id} (Mem0 ID: {memory.mem0_id})")
        
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
            content = f"Image: {media_content_type}"
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
