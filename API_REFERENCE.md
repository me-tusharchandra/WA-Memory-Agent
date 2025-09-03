# WhatsApp Memory Assistant - API Reference

## Overview

The WhatsApp Memory Assistant API provides endpoints for managing memories, interactions, and analytics. The API supports multimodal content (text, images, audio) and integrates with Mem0 for semantic memory storage.

## Base URL

```
http://localhost:8000
```

## Authentication

Currently, the API uses a simple user-based system. For production, consider implementing proper authentication.

## Endpoints

### 1. Webhook Endpoint

#### `POST /webhook`

Handles incoming WhatsApp messages from Twilio.

**Request Body (Form Data):**
```json
{
  "MessageSid": "string",
  "From": "whatsapp:+1234567890",
  "To": "whatsapp:+0987654321",
  "Body": "string (optional)",
  "NumMedia": "0",
  "MediaUrl0": "string (optional)",
  "MediaContentType0": "string (optional)"
}
```

**Response:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Message>Response message</Message>
</Response>
```

**Example:**
```bash
curl -X POST "http://localhost:8000/webhook" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "MessageSid=MSG123&From=whatsapp:+1234567890&Body=Hello"
```

### 2. Memory Management

#### `POST /memories`

Create a new memory.

**Request Body:**
```json
{
  "content": "string",
  "memory_type": "text|image|audio",
  "tags": ["string"]
}
```

**Response:**
```json
{
  "id": 1,
  "mem0_id": "uuid",
  "content": "string",
  "memory_type": "text",
  "tags": ["string"],
  "created_at": "2025-01-01T12:00:00Z",
  "interaction_id": 1
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/memories" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "I have a pet dog named Dave",
    "memory_type": "text",
    "tags": ["pets", "personal"]
  }'
```

#### `GET /memories`

Search memories using natural language queries.

**Query Parameters:**
- `query` (string, required): Search query
- `limit` (integer, optional, default: 10): Maximum number of results

**Response:**
```json
[
  {
    "id": "uuid",
    "content": "string",
    "type": "text|image|audio",
    "metadata": {
      "user_id": 1,
      "interaction_id": 1,
      "memory_type": "text",
      "tags": ["string"],
      "intent_classification": {},
      "search_query": "string"
    },
    "created_at": "2025-01-01T12:00:00Z",
    "local_id": 1,
    "interaction_id": 1,
    "tags": ["string"]
  }
]
```

**Example:**
```bash
curl "http://localhost:8000/memories?query=pet%20dog&limit=5"
```

#### `GET /memories/list`

List all memories for a user (newest first).

**Query Parameters:**
- `limit` (integer, optional, default: 50): Maximum number of results
- `user_id` (integer, optional): Specific user ID (defaults to first user)

**Response:**
```json
[
  {
    "id": 1,
    "mem0_id": "uuid",
    "content": "string",
    "memory_type": "text",
    "tags": ["string"],
    "created_at": "2025-01-01T12:00:00Z",
    "interaction_id": 1
  }
]
```

**Example:**
```bash
curl "http://localhost:8000/memories/list?limit=20&user_id=1"
```

### 3. Interaction Management

#### `GET /interactions/recent`

Get recent interactions for a user.

**Query Parameters:**
- `user_id` (integer, required): User ID
- `limit` (integer, optional, default: 10, range: 1-100): Maximum number of results

**Response:**
```json
[
  {
    "id": 1,
    "type": "text|image|audio|command|search|reminder",
    "content": "string",
    "transcript": "string (for audio)",
    "created_at": "2025-01-01T12:00:00Z",
    "metadata": {
      "intent_classification": {},
      "search_query": "string",
      "media_metadata": {}
    }
  }
]
```

**Example:**
```bash
curl "http://localhost:8000/interactions/recent?user_id=1&limit=10"
```

### 4. Analytics

#### `GET /analytics/summary`

Get analytics summary for a user.

**Query Parameters:**
- `user_id` (integer, optional): Specific user ID (defaults to first user)

**Response:**
```json
{
  "memory_types": {
    "text": 10,
    "image": 5,
    "audio": 3
  },
  "interaction_types": {
    "text": 15,
    "image": 5,
    "audio": 3,
    "command": 2,
    "search": 8,
    "reminder": 1
  },
  "last_ingest_time": "2025-01-01T12:00:00Z",
  "top_tags": {
    "pets": 3,
    "work": 2,
    "personal": 1
  },
  "total_memories": 18,
  "total_interactions": 34,
  "total_reminders": 5,
  "pending_reminders": 2
}
```

**Example:**
```bash
curl "http://localhost:8000/analytics/summary?user_id=1"
```

### 5. User Management

#### `GET /users/list`

List all users (for debugging).

**Response:**
```json
{
  "users": [
    {
      "id": 1,
      "whatsapp_id": "+1234567890",
      "created_at": "2025-01-01T12:00:00Z"
    }
  ]
}
```

**Example:**
```bash
curl "http://localhost:8000/users/list"
```

### 6. Media Management

#### `GET /media/{filename}`

Serve media files (images, audio).

**Path Parameters:**
- `filename` (string): Media filename (content hash + extension)

**Response:**
Binary file content with appropriate content-type header.

**Example:**
```bash
curl "http://localhost:8000/media/8a3ccc105cc1ace8b5b129856cdaa00166791639133273edafdd34ca2709c387.jpeg"
```

### 7. Health & Testing

#### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "message": "WhatsApp Memory Assistant API",
  "status": "running"
}
```

#### `GET /test-webhook`

Test webhook endpoint.

**Response:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Message>Test message from WhatsApp Memory Assistant!</Message>
</Response>
```

#### `POST /test-webhook`

Test webhook POST endpoint.

**Response:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Message>Test POST message from WhatsApp Memory Assistant!</Message>
</Response>
```

## Data Models

### MemoryCreate
```json
{
  "content": "string",
  "memory_type": "text|image|audio",
  "tags": ["string"]
}
```

### MemoryResponse
```json
{
  "id": 1,
  "mem0_id": "uuid",
  "content": "string",
  "memory_type": "text",
  "tags": ["string"],
  "created_at": "2025-01-01T12:00:00Z",
  "interaction_id": 1
}
```

### MemorySearchResponse
```json
{
  "id": "uuid",
  "content": "string",
  "type": "text|image|audio",
  "metadata": {
    "user_id": 1,
    "interaction_id": 1,
    "memory_type": "text",
    "tags": ["string"],
    "intent_classification": {},
    "search_query": "string"
  },
  "created_at": "2025-01-01T12:00:00Z",
  "local_id": 1,
  "interaction_id": 1,
  "tags": ["string"]
}
```

### InteractionResponse
```json
{
  "id": 1,
  "type": "text|image|audio|command|search|reminder",
  "content": "string",
  "transcript": "string",
  "created_at": "2025-01-01T12:00:00Z",
  "metadata": {
    "intent_classification": {},
    "search_query": "string",
    "media_metadata": {}
  }
}
```

### AnalyticsSummary
```json
{
  "memory_types": {
    "text": 10,
    "image": 5,
    "audio": 3
  },
  "interaction_types": {
    "text": 15,
    "image": 5,
    "audio": 3,
    "command": 2,
    "search": 8,
    "reminder": 1
  },
  "last_ingest_time": "2025-01-01T12:00:00Z",
  "top_tags": {
    "pets": 3,
    "work": 2,
    "personal": 1
  },
  "total_memories": 18,
  "total_interactions": 34,
  "total_reminders": 5,
  "pending_reminders": 2
}
```

### TwilioWebhookRequest
```json
{
  "MessageSid": "string",
  "From": "whatsapp:+1234567890",
  "To": "whatsapp:+0987654321",
  "Body": "string",
  "NumMedia": "0",
  "MediaUrl0": "string",
  "MediaContentType0": "string"
}
```

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid request data"
}
```

### 404 Not Found
```json
{
  "detail": "User not found"
}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["query", "user_id"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error message"
}
```

## WhatsApp Commands

### `/list`
Lists all user memories with type indicators and dates.

**Response Example:**
```
Your memories (3 total):

1. User has a pet dog named Dave 📝 (Sep 3, 2025)
2. User's wallpaper has been this image for a decade 📷 (Sep 3, 2025)
3. Tushar Loves badminton 📝 (Sep 3, 2025)

💡 Use natural language to search specific memories!
```

## Features

### Multimodal Support
- **Text**: Direct memory creation
- **Images**: Automatic processing and metadata extraction
- **Audio**: Whisper transcription with intent classification

### Intent Classification
- **Search**: Natural language queries
- **Reminder**: Time-based reminders
- **Memory**: New memory creation

### Metadata Enrichment
- Interaction metadata from local database
- Intent classification results
- Media processing metadata
- User context and tags

### Idempotency
- Message deduplication using Twilio MessageSid
- Media deduplication using content hash
- Safe repeated processing

## Rate Limits

Currently no rate limits are implemented. For production, consider adding rate limiting based on user_id or IP address.

## Notes

- All timestamps are in ISO 8601 format
- Memory content is truncated for WhatsApp display (80 characters)
- Image memories include URLs for media retrieval
- Analytics are calculated from local database
- Reminder scheduling uses local timezone
