import openai
import logging

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
    
    async def classify_intent(self, message: str, user_id: str) -> Dict[str, Any]:
        """
        Classify the intent of a WhatsApp message.
        Returns: {
            "intent": "memory" | "search",
            "confidence": float,
            "reasoning": str,
            "extracted_query": str (if search intent)
        }
        """
        if not self.client:
            logger.warning("⚠️ OpenAI client not available, using fallback classification")
            return self._fallback_classification(message)
        
        logger.debug(f"🔍 Classifying intent for message: '{message[:100]}...'")
        
        try:
            # Create the classification prompt
            system_prompt = """You are an intent classifier for a WhatsApp memory assistant. Your job is to determine if a user message is:

1. A NEW MEMORY - User is sharing information to be stored (e.g., "I got a haircut today", "My grocery list: milk, bread", "Meeting with John at 3pm")
2. A SEARCH QUERY - User is asking about previously stored information (e.g., "What did I plan for dinner?", "Show me my recent photos", "What was my to-do list?")

Respond with JSON format:
{
    "intent": "memory" or "search",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation of your classification",
    "extracted_query": "The search query extracted from the message (only if intent is 'search')"
}

Examples:
- "I bought groceries today" → {"intent": "memory", "confidence": 0.95, "reasoning": "User is sharing new information", "extracted_query": ""}
- "What did I buy at the store?" → {"intent": "search", "confidence": 0.9, "reasoning": "User is asking about previous information", "extracted_query": "groceries store shopping"}
- "Meeting with Sarah tomorrow" → {"intent": "memory", "confidence": 0.9, "reasoning": "User is sharing a new appointment", "extracted_query": ""}
- "When is my meeting with Sarah?" → {"intent": "search", "confidence": 0.85, "reasoning": "User is asking about a previous appointment", "extracted_query": "meeting Sarah appointment"}
- "My new haircut looks great" → {"intent": "memory", "confidence": 0.9, "reasoning": "User is sharing personal update", "extracted_query": ""}
- "Show me my recent photos" → {"intent": "search", "confidence": 0.95, "reasoning": "User is requesting to see stored media", "extracted_query": "recent photos images"}
- "Hello" → {"intent": "memory", "confidence": 0.7, "reasoning": "Greeting, treating as new interaction", "extracted_query": ""}
- "How are you?" → {"intent": "memory", "confidence": 0.6, "reasoning": "Conversational question, treating as new interaction", "extracted_query": ""}"""

            user_prompt = f"Classify this WhatsApp message: '{message}'"
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=200
            )
            
            # Parse the response
            response_text = response.choices[0].message.content.strip()
            logger.debug(f"🤖 OpenAI response: {response_text}")
            
            # Extract JSON from response
            import json
            try:
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
                    result["extracted_query"] = message
                
                logger.info(f"✅ Intent classified as: {result['intent']} (confidence: {result['confidence']})")
                return result
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"❌ Failed to parse OpenAI response: {e}")
                logger.error(f"❌ Response text: {response_text}")
                return self._fallback_classification(message)
                
        except Exception as e:
            logger.error(f"❌ Error calling OpenAI API: {str(e)}", exc_info=True)
            return self._fallback_classification(message)
    
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
            "extracted_query": message if is_search else ""
        }
        
        logger.info(f"✅ Fallback intent: {intent} (confidence: {confidence})")
        return result
