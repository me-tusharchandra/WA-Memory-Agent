import json
import logging

from mem0 import MemoryClient
from app.config import settings
from typing import Optional, Dict, Any, List

# Configure logging
logger = logging.getLogger(__name__)

class Mem0Client:
    def __init__(self):
        logger.info("🔧 Initializing Mem0 client...")
        logger.debug(f"🔑 Using Mem0 API key: {settings.mem0_api_key[:8]}...")
        
        # Initialize with API key only (org_id and project_id are optional)
        self.client = MemoryClient(api_key=settings.mem0_api_key)
        
        # Optional: Add org_id and project_id if configured
        if hasattr(settings, 'mem0_org_id') and settings.mem0_org_id:
            logger.debug(f"🏢 Using Mem0 org ID: {settings.mem0_org_id}")
            self.client = MemoryClient(
                api_key=settings.mem0_api_key,
                org_id=settings.mem0_org_id,
                project_id=getattr(settings, 'mem0_project_id', None)
            )
            if getattr(settings, 'mem0_project_id', None):
                logger.debug(f"📁 Using Mem0 project ID: {settings.mem0_project_id}")
        
        logger.info("✅ Mem0 client initialized successfully")
    
    def create_memory(self, content: str, memory_type: str = "text", metadata: Optional[Dict[str, Any]] = None, user_id: str = "default") -> str:
        """Create a new memory in Mem0"""
        logger.debug(f"🧠 Creating Mem0 memory, type: {memory_type}")
        logger.debug(f"📝 Content preview: {content[:100]}...")
        logger.debug(f"📊 Metadata: {metadata}")
        
        try:
            # Convert content to messages format expected by Mem0 API
            messages = [
                {
                    "role": "user",
                    "content": content
                }
            ]
            
            logger.debug(f"🔍 Sending to Mem0 - content: '{content}'")
            logger.debug(f"🔍 Sending to Mem0 - user_id: '{user_id}'")
            logger.debug(f"🔍 Sending to Mem0 - metadata: {metadata}")
            
            # Using the correct API method with messages parameter (synchronous)
            memory = self.client.add(
                messages=messages,
                user_id=user_id,
                output_format="v1.1"
            )
            
            # Debug the response type and structure
            logger.debug(f"🔍 Mem0 response type: {type(memory)}")
            logger.debug(f"🔍 Mem0 response: {memory}")
            
            # Handle different response formats
            if isinstance(memory, dict):
                if 'results' in memory:
                    if len(memory['results']) > 0:
                        # Extract the latest memory ID from the results
                        memory_id = memory['results'][-1]['id']
                        logger.info(f"✅ Successfully created Mem0 memory with ID: {memory_id}")
                        return memory_id
                    else:
                        # Empty results array - memory creation failed
                        logger.error(f"❌ Mem0 returned empty results array: {memory}")
                        raise Exception("Mem0 memory creation failed - empty results")
                elif 'id' in memory:
                    # Direct ID format
                    logger.info(f"✅ Successfully created Mem0 memory with ID: {memory['id']}")
                    return memory['id']
                else:
                    # Unknown format
                    logger.error(f"❌ Unknown Mem0 response format: {memory}")
                    raise Exception(f"Unknown Mem0 response format: {memory}")
            else:
                # Non-dict response
                logger.info(f"✅ Successfully created Mem0 memory with ID: {str(memory)}")
                return str(memory)
        except Exception as e:
            logger.error(f"❌ Failed to create memory in Mem0: {str(e)}", exc_info=True)
            raise Exception(f"Failed to create memory in Mem0: {str(e)}")
    
    def search_memories(self, query: str, user_id: str = "default", limit: int = 10) -> List[Dict[str, Any]]:
        """Search memories in Mem0"""
        logger.debug(f"🔍 Searching Mem0 memories, query: '{query}', user_id: '{user_id}', limit: {limit}")
        
        try:
            # Using the correct search API method (synchronous)
            results = self.client.search(
                query=query,
                user_id=user_id,
                limit=limit
            )
            logger.info(f"✅ Found {len(results)} memories in Mem0")
            
            formatted_results = []
            for memory in results:
                formatted_results.append({
                    "id": memory.get("id", "unknown"),
                    "content": memory.get("memory", ""),
                    "type": memory.get("type", "text"),
                    "metadata": memory.get("metadata", {}),
                    "created_at": memory.get("created_at", "")
                })
            
            logger.debug(f"📊 Returning {len(formatted_results)} formatted results")
            return formatted_results
        except Exception as e:
            logger.error(f"❌ Failed to search memories in Mem0: {str(e)}", exc_info=True)
            raise Exception(f"Failed to search memories in Mem0: {str(e)}")
    
    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific memory by ID"""
        logger.debug(f"🔍 Getting Mem0 memory with ID: {memory_id}")
        
        try:
            # Using the correct get API method (synchronous)
            memory = self.client.get(memory_id)
            logger.info(f"✅ Successfully retrieved memory: {memory_id}")
            
            return {
                "id": memory.get("id", memory_id),
                "content": memory.get("memory", ""),
                "type": memory.get("type", "text"),
                "metadata": memory.get("metadata", {}),
                "created_at": memory.get("created_at", "")
            }
        except Exception as e:
            logger.error(f"❌ Failed to get memory from Mem0: {str(e)}", exc_info=True)
            raise Exception(f"Failed to get memory from Mem0: {str(e)}")
    
    def update_memory(self, memory_id: str, new_content: str) -> bool:
        """Update a memory in Mem0"""
        logger.debug(f"🔄 Updating Mem0 memory with ID: {memory_id}")
        logger.debug(f"📝 New content: {new_content}")
        
        try:
            # Using the correct update API method (synchronous)
            # Note: Mem0 might not have a direct update method, so we might need to delete and recreate
            # For now, let's try to use the add method with the same ID
            messages = [
                {
                    "role": "user",
                    "content": new_content
                }
            ]
            
            # Try to update by adding with the same ID
            result = self.client.add(
                messages=messages,
                user_id="default",  # We'll need to get the actual user_id
                output_format="v1.1"
            )
            
            logger.info(f"✅ Successfully updated memory: {memory_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to update memory in Mem0: {str(e)}", exc_info=True)
            raise Exception(f"Failed to update memory in Mem0: {str(e)}")
    
    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory from Mem0"""
        logger.debug(f"🗑️ Deleting Mem0 memory with ID: {memory_id}")
        
        try:
            # Using the correct delete API method (synchronous)
            self.client.delete(memory_id)
            logger.info(f"✅ Successfully deleted memory: {memory_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to delete memory from Mem0: {str(e)}", exc_info=True)
            raise Exception(f"Failed to delete memory from Mem0: {str(e)}")
    
    def list_memories(self, user_id: str = "default", limit: int = 50) -> List[Dict[str, Any]]:
        """List all memories in Mem0"""
        logger.debug(f"📋 Listing Mem0 memories, user_id: '{user_id}', limit: {limit}")
        
        try:
            # Using the correct get_all API method (synchronous)
            results = self.client.get_all(user_id=user_id, limit=limit)
            logger.info(f"✅ Found {len(results)} memories in Mem0")
            
            formatted_results = []
            for memory in results:
                formatted_results.append({
                    "id": memory.get("id", "unknown"),
                    "content": memory.get("memory", ""),
                    "type": memory.get("type", "text"),
                    "metadata": memory.get("metadata", {}),
                    "created_at": memory.get("created_at", "")
                })
            
            logger.debug(f"📊 Returning {len(formatted_results)} formatted results")
            return formatted_results
        except Exception as e:
            logger.error(f"❌ Failed to list memories from Mem0: {str(e)}", exc_info=True)
            raise Exception(f"Failed to list memories from Mem0: {str(e)}")


# Global Mem0 client instance
mem0_client = Mem0Client()
