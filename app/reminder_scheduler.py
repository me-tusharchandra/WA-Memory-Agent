import logging
import asyncio
import requests
from typing import Optional
from datetime import datetime
from app.config import settings
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.services import ReminderService

# Configure logging
logger = logging.getLogger(__name__)

class ReminderScheduler:
    def __init__(self):
        self.running = False
        self.check_interval = 60  # Check every 60 seconds
        logger.info("🔧 Initializing ReminderScheduler...")
    
    async def start(self):
        """Start the reminder scheduler"""
        if self.running:
            logger.warning("⚠️ ReminderScheduler is already running")
            return
        
        self.running = True
        logger.info("🚀 Starting ReminderScheduler...")
        
        while self.running:
            try:
                await self.check_and_send_reminders()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"❌ Error in reminder scheduler: {e}", exc_info=True)
                await asyncio.sleep(self.check_interval)
    
    def stop(self):
        """Stop the reminder scheduler"""
        logger.info("🛑 Stopping ReminderScheduler...")
        self.running = False
    
    async def check_and_send_reminders(self):
        """Check for pending reminders and send them"""
        logger.debug("🔍 Checking for pending reminders...")
        
        db = SessionLocal()
        try:
            # Get pending reminders
            pending_reminders = ReminderService.get_pending_reminders(db, limit=50)
            
            if not pending_reminders:
                logger.debug("📭 No pending reminders found")
                return
            
            logger.info(f"📤 Found {len(pending_reminders)} pending reminders to send")
            
            for reminder in pending_reminders:
                try:
                    await self.send_reminder(reminder, db)
                except Exception as e:
                    logger.error(f"❌ Error sending reminder {reminder.id}: {e}", exc_info=True)
                    
        finally:
            db.close()
    
    async def send_reminder(self, reminder, db: Session):
        """Send a reminder via Twilio WhatsApp"""
        logger.info(f"📤 Sending reminder {reminder.id}: {reminder.message}")
        
        try:
            # Get user's WhatsApp ID
            from app.database import User
            user = db.query(User).filter(User.id == reminder.user_id).first()
            
            if not user:
                logger.error(f"❌ User not found for reminder {reminder.id}")
                return
            
            whatsapp_id = f"whatsapp:{user.whatsapp_id}"
            
            # Send message via Twilio
            response = await self.send_twilio_message(whatsapp_id, reminder.message)
            
            if response:
                # Mark reminder as sent
                ReminderService.mark_reminder_sent(db, reminder.id)
                logger.info(f"✅ Successfully sent reminder {reminder.id}")
            else:
                logger.error(f"❌ Failed to send reminder {reminder.id}")
                
        except Exception as e:
            logger.error(f"❌ Error sending reminder {reminder.id}: {e}", exc_info=True)
    
    async def send_twilio_message(self, to_whatsapp_id: str, message: str) -> bool:
        """Send a message via Twilio WhatsApp API"""
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
            
            data = {
                "From": settings.twilio_phone_number,
                "To": to_whatsapp_id,
                "Body": f"⏰ REMINDER: {message}"
            }
            
            response = requests.post(
                url,
                data=data,
                auth=(settings.twilio_account_sid, settings.twilio_auth_token)
            )
            
            if response.status_code == 201:
                logger.info(f"✅ Twilio message sent successfully to {to_whatsapp_id}")
                return True
            else:
                logger.error(f"❌ Twilio API error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error sending Twilio message: {e}", exc_info=True)
            return False
    
    async def send_reminder_now(self, user_id: int, message: str) -> bool:
        """Send a reminder immediately (for testing)"""
        logger.info(f"📤 Sending immediate reminder to user {user_id}: {message}")
        
        db = SessionLocal()
        try:
            # Get user's WhatsApp ID
            from app.database import User
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                logger.error(f"❌ User not found for user_id {user_id}")
                return False
            
            whatsapp_id = f"whatsapp:{user.whatsapp_id}"
            
            # Send message via Twilio
            success = await self.send_twilio_message(whatsapp_id, message)
            
            if success:
                logger.info(f"✅ Successfully sent immediate reminder to user {user_id}")
            else:
                logger.error(f"❌ Failed to send immediate reminder to user {user_id}")
            
            return success
            
        finally:
            db.close()


# Global reminder scheduler instance
reminder_scheduler = ReminderScheduler()
