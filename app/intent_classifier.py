import re
import openai
import logging
from app.config import settings
from typing import Dict, Any, Literal
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger(__name__)

class IntentClassifier:
    def __init__(self):
        logger.info("🔧 Initializing IntentClassifier...")
        if not settings.openai_api_key:
            logger.warning("⚠️ No OpenAI API key provided - intent classification will not work")
            self.client = None
        else:
            self.client = openai.OpenAI(api_key=settings.openai_api_key)
            logger.info("✅ IntentClassifier initialized with OpenAI")
    
    def _get_current_datetime_context(self) -> str:
        """Get current datetime context for the model"""
        now = datetime.now().astimezone()
        return f"Current date and time: {now.strftime('%A, %B %d, %Y at %I:%M %p')} ({now.strftime('%Y-%m-%d %H:%M:%S')})"
    
    async def classify_intent(self, message: str, user_id: str) -> Dict[str, Any]:
        """
        Classify the intent of a WhatsApp message with real-time datetime context.
        Returns: {
            "intent": "memory" | "search" | "reminder",
            "confidence": float,
            "reasoning": str,
            "extracted_query": str (if search intent),
            "updated_content": str (if memory intent with temporal reference, the updated content),
            "reminder_info": dict (if reminder intent, contains timing and message info)
        }
        """
        if not self.client:
            logger.warning("⚠️ OpenAI client not available, using fallback classification")
            return self._fallback_classification(message)
        
        logger.debug(f"🔍 Classifying intent for message: '{message[:100]}...'")
        
        try:
            # Get current datetime context
            datetime_context = self._get_current_datetime_context()
            
            # Create the classification prompt with real-time context
            system_prompt = f"""You are an intent classifier for a WhatsApp memory assistant. 

{datetime_context}

Your job is to determine if a user message is:

1. A NEW MEMORY - User is sharing information to be stored (e.g., "I got a haircut today", "Meeting with John tomorrow", "My birthday is next week")
2. A SEARCH QUERY - User is asking about previously stored information (e.g., "What did I do yesterday?", "When did I get my last haircut?", "What was my last trip?")
3. A REMINDER REQUEST - User is asking to be reminded about something at a specific time (e.g., "Remind me to call mom tomorrow at 3pm", "Set a reminder for my meeting at 2pm", "Remind me to buy groceries in 2 hours")

IMPORTANT RULES:
- ONLY classify as "reminder" if the user uses the word "remind" or "reminder"
- Use the current date/time context to understand temporal references and calculate exact dates.
- For reminders, ALWAYS schedule in the user's LOCAL timezone, NOT UTC
- When the user says "in 2 minutes", calculate 2 minutes from the CURRENT TIME shown above
- When the user says "at 3pm", use 3pm in their local timezone today (or tomorrow if it's already past 3pm)
- ALWAYS calculate relative times (like "in 2 minutes", "in 1 hour") from the current time shown above
- NEVER use hardcoded times - always calculate from the current time
- CRITICAL: "tomorrow" means the day AFTER the current date shown above
- CRITICAL: "today" means the current date shown above
- CRITICAL: "yesterday" means the day BEFORE the current date shown above

Respond with JSON format:
{{
    "intent": "memory" or "search" or "reminder",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation considering the current date/time context",
    "extracted_query": "The search query extracted from the message (only if intent is 'search')",
    "updated_content": "The updated message content with temporal references replaced by exact dates (only if intent is 'memory' and contains temporal references)",
    "reminder_info": {{
        "message": "The reminder message to send",
        "scheduled_time": "YYYY-MM-DD HH:MM:SS format in LOCAL timezone",
        "timezone": "LOCAL" (use local machine timezone)
    }} (only if intent is 'reminder')
}}

EXAMPLES:
- "I got a haircut today" → {{"intent": "memory", "confidence": 0.95, "reasoning": "Recent personal update", "extracted_query": "", "updated_content": "I got a haircut on September 4, 2025"}}
- "Meeting with John tomorrow" → {{"intent": "memory", "confidence": 0.95, "reasoning": "Future event", "extracted_query": "", "updated_content": "Meeting with John on September 5, 2025"}}
- "What did I do yesterday?" → {{"intent": "search", "confidence": 0.9, "reasoning": "Question about past events", "extracted_query": "yesterday activities"}}
- "Remind me to call mom tomorrow at 3pm" → {{"intent": "reminder", "confidence": 0.95, "reasoning": "Request for future reminder", "extracted_query": "", "updated_content": "", "reminder_info": {{"message": "Call mom", "scheduled_time": "2025-09-05 15:00:00", "timezone": "LOCAL"}}}}
- "Set a reminder for my meeting at 2pm" → {{"intent": "reminder", "confidence": 0.95, "reasoning": "Request for reminder today", "extracted_query": "", "updated_content": "", "reminder_info": {{"message": "Meeting", "scheduled_time": "2025-09-04 14:00:00", "timezone": "LOCAL"}}}}
- "Remind me to buy groceries in 2 hours" → {{"intent": "reminder", "confidence": 0.95, "reasoning": "Request for reminder in 2 hours", "extracted_query": "", "updated_content": "", "reminder_info": {{"message": "Buy groceries", "scheduled_time": "2025-09-04 02:46:00", "timezone": "LOCAL"}}}}
- "Remind me to call varsha in 2 minutes" → {{"intent": "reminder", "confidence": 0.95, "reasoning": "Request for reminder in 2 minutes", "extracted_query": "", "updated_content": "", "reminder_info": {{"message": "Call varsha", "scheduled_time": "2025-09-04 00:48:00", "timezone": "LOCAL"}}}}
- "Talk to mom after 2 minutes" → {{"intent": "memory", "confidence": 0.95, "reasoning": "Future event without reminder keyword", "extracted_query": "", "updated_content": "Talk to mom after 2 minutes"}}
- "Call mom in 1 hour" → {{"intent": "memory", "confidence": 0.95, "reasoning": "Future event without reminder keyword", "extracted_query": "", "updated_content": "Call mom in 1 hour"}}"""

            user_prompt = f"Classify this WhatsApp message: '{message}'"
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )
            
            # Parse the response
            response_text = response.choices[0].message.content.strip()
            logger.debug(f"🤖 OpenAI response: {response_text}")
            
            # Extract JSON from response
            import json
            try:
                result = self._parse_json_response(response_text)
                logger.info(f"✅ Intent classified as: {result['intent']} (confidence: {result['confidence']})")
                return result
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"❌ Failed to parse OpenAI response: {e}")
                return self._fallback_classification(message)
                
        except Exception as e:
            logger.error(f"❌ Error calling OpenAI API: {str(e)}", exc_info=True)
            return self._fallback_classification(message)
    
    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """Parse JSON response from OpenAI"""
        import json
        
        # Try to find JSON in the response
        if response_text.startswith('{') and response_text.endswith('}'):
            result = json.loads(response_text)
        else:
            # Try to extract JSON from the response
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start != -1 and end != 0:
                result = json.loads(response_text[start:end])
            else:
                raise ValueError("No JSON found in response")
        
        # Validate the response
        required_fields = ["intent", "confidence", "reasoning"]
        for field in required_fields:
            if field not in result:
                raise ValueError(f"Missing required field: {field}")
        
        if result["intent"] not in ["memory", "search", "reminder"]:
            raise ValueError(f"Invalid intent: {result['intent']}")
        
        # Ensure extracted_query is present for search intent
        if result["intent"] == "search" and "extracted_query" not in result:
            result["extracted_query"] = ""
        
        # Ensure updated_content is present for memory intent
        if result["intent"] == "memory" and "updated_content" not in result:
            result["updated_content"] = ""
        
        # Ensure reminder_info is present for reminder intent
        if result["intent"] == "reminder" and "reminder_info" not in result:
            result["reminder_info"] = {}
        
        return result
    
    def _fallback_classification(self, message: str) -> Dict[str, Any]:
        """
        Fallback classification when OpenAI is not available.
        Uses simple heuristics to determine intent.
        """
        logger.debug("🔄 Using fallback classification")
        
        message_lower = message.lower().strip()
        
        # Reminder indicators
        reminder_indicators = [
            "remind me", "set a reminder", "reminder", "alert me", "notify me",
            "call me", "text me", "message me", "ping me", "wake me up"
        ]
        
        # Search indicators
        search_indicators = [
            "what", "when", "where", "who", "why", "how",
            "show me", "find", "search", "look for", "recall",
            "remember", "remind me", "what did", "what was",
            "do you remember", "can you find", "where is"
        ]
        
        # Check if message contains reminder indicators
        is_reminder = any(indicator in message_lower for indicator in reminder_indicators)
        
        # Check if message contains search indicators
        is_search = any(indicator in message_lower for indicator in search_indicators)
        
        # Check if message ends with question mark
        if message.strip().endswith('?'):
            is_search = True
        
        # Check for specific search patterns
        if any(pattern in message_lower for pattern in ["my", "me", "I"]) and any(indicator in message_lower for indicator in ["what", "when", "where", "show", "find"]):
            is_search = True
        
        # Determine intent priority: reminder > search > memory
        if is_reminder:
            intent = "reminder"
            confidence = 0.8
            reasoning = "Fallback classification based on reminder indicators"
        elif is_search:
            intent = "search"
            confidence = 0.8
            reasoning = "Fallback classification based on search indicators"
        else:
            intent = "memory"
            confidence = 0.7
            reasoning = "Fallback classification defaulting to memory"
        
        result = {
            "intent": intent,
            "confidence": confidence,
            "reasoning": reasoning,
            "extracted_query": message if intent == "search" else "",
            "updated_content": ""  # Fallback doesn't update content
        }
        
        # For reminder intent, we can't extract timing without AI, so we'll return empty reminder_info
        if intent == "reminder":
            result["reminder_info"] = {}
        
        logger.info(f"✅ Fallback intent: {intent} (confidence: {confidence})")
        return result
