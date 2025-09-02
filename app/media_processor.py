import os
import whisper
import requests
import tempfile
import logging

from PIL import Image
from app.config import settings
from typing import Optional, Dict, Any, Tuple

# Configure logging
logger = logging.getLogger(__name__)

class MediaProcessor:
    def __init__(self):
        logger.info("🔧 Initializing MediaProcessor...")
        self.whisper_model = None
        if settings.openai_api_key:
            try:
                logger.debug("🎤 Loading Whisper model...")
                self.whisper_model = whisper.load_model("base")
                logger.info("✅ Whisper model loaded successfully")
            except Exception as e:
                logger.warning(f"⚠️ Could not load Whisper model: {e}")
        else:
            logger.warning("⚠️ No OpenAI API key provided - audio transcription will not work")
        
        logger.info("✅ MediaProcessor initialized")
    
    async def download_media(self, media_url: str, auth: Tuple[str, str]) -> bytes:
        """Download media from Twilio URL"""
        logger.debug(f"⬇️ Downloading media from: {media_url}")
        
        try:
            response = requests.get(media_url, auth=auth)
            response.raise_for_status()
            content = response.content
            logger.info(f"✅ Downloaded media: {len(content)} bytes")
            return content
        except Exception as e:
            logger.error(f"❌ Failed to download media: {str(e)}", exc_info=True)
            raise Exception(f"Failed to download media: {str(e)}")
    
    async def process_image(self, image_data: bytes, mime_type: str) -> Dict[str, Any]:
        """Process image and extract metadata"""
        logger.debug(f"🖼️ Processing image, mime type: {mime_type}")
        
        try:
            # Save image to temporary file for processing
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                temp_file.write(image_data)
                temp_file_path = temp_file.name
            
            logger.debug(f"💾 Saved image to temp file: {temp_file_path}")
            
            # Open image with PIL to get metadata
            with Image.open(temp_file_path) as img:
                metadata = {
                    "format": img.format,
                    "mode": img.mode,
                    "size": img.size,
                    "width": img.width,
                    "height": img.height,
                    "mime_type": mime_type
                }
            
            logger.info(f"✅ Processed image: {img.width}x{img.height}, format: {img.format}")
            
            # Clean up temporary file
            os.unlink(temp_file_path)
            logger.debug("🧹 Cleaned up temporary image file")
            
            return metadata
        except Exception as e:
            logger.error(f"❌ Failed to process image: {str(e)}", exc_info=True)
            raise Exception(f"Failed to process image: {str(e)}")
    
    async def transcribe_audio(self, audio_data: bytes, mime_type: str) -> str:
        """Transcribe audio using Whisper"""
        if not self.whisper_model:
            logger.error("❌ Whisper model not available. Please set OPENAI_API_KEY.")
            raise Exception("Whisper model not available. Please set OPENAI_API_KEY.")
        
        logger.debug(f"🎤 Transcribing audio, mime type: {mime_type}")
        
        try:
            # Save audio to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
            
            logger.debug(f"💾 Saved audio to temp file: {temp_file_path}")
            
            # Transcribe with Whisper
            logger.debug("🎤 Running Whisper transcription...")
            result = self.whisper_model.transcribe(temp_file_path)
            transcript = result["text"].strip()
            
            logger.info(f"✅ Transcription completed: '{transcript}'")
            
            # Clean up temporary file
            os.unlink(temp_file_path)
            logger.debug("🧹 Cleaned up temporary audio file")
            
            return transcript
        except Exception as e:
            logger.error(f"❌ Failed to transcribe audio: {str(e)}", exc_info=True)
            raise Exception(f"Failed to transcribe audio: {str(e)}")
    
    async def get_media_metadata(self, media_data: bytes, mime_type: str) -> Dict[str, Any]:
        """Get metadata for any media type"""
        logger.debug(f"📊 Getting metadata for media, mime type: {mime_type}")
        
        metadata = {
            "mime_type": mime_type,
            "file_size": len(media_data)
        }
        
        if mime_type.startswith("image/"):
            logger.debug("🖼️ Processing image metadata...")
            image_metadata = await self.process_image(media_data, mime_type)
            metadata.update(image_metadata)
        elif mime_type.startswith("audio/"):
            logger.debug("🎵 Processing audio metadata...")
            metadata["type"] = "audio"
            # Add audio-specific metadata if needed
        elif mime_type.startswith("video/"):
            logger.debug("🎬 Processing video metadata...")
            metadata["type"] = "video"
            # Add video-specific metadata if needed
        else:
            logger.warning(f"⚠️ Unknown media type: {mime_type}")
        
        logger.debug(f"📊 Final metadata: {metadata}")
        return metadata


# Global media processor instance
media_processor = MediaProcessor()
