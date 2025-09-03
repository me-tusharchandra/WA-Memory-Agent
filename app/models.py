from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class MemoryCreate(BaseModel):
    content: str = Field(..., description="Memory content")
    memory_type: str = Field(..., description="Type of memory (text, image, audio)")
    tags: Optional[List[str]] = Field(default=[], description="Tags for the memory")


class MemoryResponse(BaseModel):
    id: int
    mem0_id: str
    content: str
    memory_type: str
    tags: List[str]
    created_at: str
    interaction_id: int


class MemorySearchResponse(BaseModel):
    id: str
    content: str
    type: str
    metadata: Dict[str, Any]
    created_at: str
    local_id: Optional[int]
    interaction_id: Optional[int]
    tags: Optional[List[str]]


class InteractionResponse(BaseModel):
    id: int
    type: str
    content: Optional[str]
    transcript: Optional[str]
    created_at: str
    metadata: Dict[str, Any]


class AnalyticsSummary(BaseModel):
    memory_types: Dict[str, int]
    interaction_types: Dict[str, int]
    last_ingest_time: Optional[str]
    top_tags: Dict[str, int]
    total_memories: int
    total_interactions: int
    total_reminders: int
    pending_reminders: int


class ReminderCreate(BaseModel):
    message: str = Field(..., description="Reminder message")
    scheduled_time: datetime = Field(..., description="When to send the reminder")
    timezone: str = Field(default="UTC", description="Timezone for the reminder")
    reminder_type: str = Field(default="message", description="Type of reminder")
    recurrence_pattern: Optional[Dict[str, Any]] = Field(default=None, description="Recurrence pattern for recurring reminders")


class ReminderResponse(BaseModel):
    id: int
    message: str
    scheduled_time: str
    timezone: str
    status: str
    reminder_type: str
    created_at: str
    sent_at: Optional[str]
    user_id: int
    interaction_id: int


class TwilioWebhookRequest(BaseModel):
    MessageSid: str
    From: str
    To: str
    Body: Optional[str] = None
    NumMedia: Optional[str] = "0"
    MediaUrl0: Optional[str] = None
    MediaContentType0: Optional[str] = None
    MediaUrl1: Optional[str] = None
    MediaContentType1: Optional[str] = None
    MediaUrl2: Optional[str] = None
    MediaContentType2: Optional[str] = None
    MediaUrl3: Optional[str] = None
    MediaContentType3: Optional[str] = None
    MediaUrl4: Optional[str] = None
    MediaContentType4: Optional[str] = None
    MediaUrl5: Optional[str] = None
    MediaContentType5: Optional[str] = None
    MediaUrl6: Optional[str] = None
    MediaContentType6: Optional[str] = None
    MediaUrl7: Optional[str] = None
    MediaContentType7: Optional[str] = None
    MediaUrl8: Optional[str] = None
    MediaContentType8: Optional[str] = None
    MediaUrl9: Optional[str] = None
    MediaContentType9: Optional[str] = None


class WhatsAppResponse(BaseModel):
    message: str
    success: bool = True
