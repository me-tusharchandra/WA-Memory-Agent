import openai
import logging
from datetime import datetime, timedelta
import re
from app.config import settings
from typing import Dict, Any, Literal

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
        now = datetime.now()
        return f"Current date and time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}"
    
    async def classify_intent(self, message: str, user_id: str) -> Dict[str, Any]:
        """
        Classify the intent of a WhatsApp message with real-time datetime context.
        Returns: {
            "intent": "memory" | "search",
            "confidence": float,
            "reasoning": str,
            "extracted_query": str (if search intent),
            "updated_content": str (if memory intent with temporal reference, the updated content)
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

IMPORTANT: Use the current date/time context to understand temporal references and calculate exact dates.

Respond with JSON format:
{{
    "intent": "memory" or "search",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation considering the current date/time context",
    "extracted_query": "The search query extracted from the message (only if intent is 'search')",
    "updated_content": "The updated message content with temporal references replaced by exact dates (only if intent is 'memory' and contains temporal references)"
}}

EXAMPLES:
- "I got a haircut today" → {{"intent": "memory", "confidence": 0.95, "reasoning": "Recent personal update", "extracted_query": "", "updated_content": "I got a haircut on September 3, 2025"}}
- "Meeting with John tomorrow" → {{"intent": "memory", "confidence": 0.95, "reasoning": "Future event", "extracted_query": "", "updated_content": "Meeting with John on September 4, 2025"}}
- "My birthday is next week" → {{"intent": "memory", "confidence": 0.95, "reasoning": "Future event", "extracted_query": "", "updated_content": "My birthday is on September 10, 2025"}}
- "What did I do yesterday?" → {{"intent": "search", "confidence": 0.9, "reasoning": "Question about past events", "extracted_query": "yesterday activities"}}
- "When did I get my last haircut?" → {{"intent": "search", "confidence": 0.9, "reasoning": "Question about past personal event", "extracted_query": "haircut last time"}}"""

            user_prompt = f"Classify this WhatsApp message: '{message}'"
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=200
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
        
        if result["intent"] not in ["memory", "search"]:
            raise ValueError(f"Invalid intent: {result['intent']}")
        
        # Ensure extracted_query is present for search intent
        if result["intent"] == "search" and "extracted_query" not in result:
            result["extracted_query"] = ""
        
        # Ensure updated_content is present for memory intent
        if result["intent"] == "memory" and "updated_content" not in result:
            result["updated_content"] = ""
        
        return result
    
    def _fallback_classification(self, message: str) -> Dict[str, Any]:
        """
        Fallback classification when OpenAI is not available.
        Uses simple heuristics to determine intent.
        """
        logger.debug("🔄 Using fallback classification")
        
        message_lower = message.lower().strip()
        
        # Search indicators
        search_indicators = [
            "what", "when", "where", "who", "why", "how",
            "show me", "find", "search", "look for", "recall",
            "remember", "remind me", "what did", "what was",
            "do you remember", "can you find", "where is"
        ]
        
        # Check if message contains search indicators
        is_search = any(indicator in message_lower for indicator in search_indicators)
        
        # Check if message ends with question mark
        if message.strip().endswith('?'):
            is_search = True
        
        # Check for specific search patterns
        if any(pattern in message_lower for pattern in ["my", "me", "I"]) and any(indicator in message_lower for indicator in ["what", "when", "where", "show", "find"]):
            is_search = True
        
        intent = "search" if is_search else "memory"
        confidence = 0.8 if is_search else 0.7
        
        result = {
            "intent": intent,
            "confidence": confidence,
            "reasoning": f"Fallback classification based on {'search indicators' if is_search else 'default to memory'}",
            "extracted_query": message if is_search else "",
            "updated_content": ""  # Fallback doesn't update content
        }
        
        logger.info(f"✅ Fallback intent: {intent} (confidence: {confidence})")
        return result
