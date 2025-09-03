# WhatsApp Memory Assistant

A WhatsApp chatbot using Twilio's WhatsApp API and Mem0's memory layer to ingest and recall images, audio, and text as memories. The bot supports natural language queries and provides persistent memory storage with database analytics.

## Features

- **Multimodal Ingestion**: Accept and process images, voice notes, and text messages
- **Persistent Memory**: Store entries in Mem0 with metadata and embeddings for fast, semantic retrieval
- **Database Persistence**: Capture user interactions and memories with idempotent ingestion and media deduplication
- **Interactive Chat**: Handle conversational queries using context awareness
- **Semantic Search**: AI-powered intent classification for natural language queries
- **Memory Listing**: `/list` command to enumerate all user memories
- **Scheduled Reminders**: Set reminders with natural language time expressions
- **Analytics**: Database-backed queries and analytics summary
- **Timezone-aware**: Support for timezone-aware queries and filtering
- **Robust Error Handling**: Graceful handling of API failures with fallback mechanisms

## Architecture

### System Overview

The application follows a modular architecture with clear separation of concerns:

![Architecture Diagram](misc/old-uml-class-diag.png)

### Database Schema

The application uses a custom database schema with the following entities:

- **Users**: WhatsApp user identities
- **Interactions**: Inbound messages (text, image, audio) with metadata
- **Media**: Media files with content-based deduplication
- **Memories**: Links to Mem0 memories with local metadata
- **Reminders**: Scheduled reminders with timing information

### Key Features

- **Idempotent Ingestion**: Processing the same Twilio message twice won't create duplicates
- **Media Deduplication**: Identical media stored once and re-referenced
- **Memory Linkage**: Each memory traceable to its originating interaction
- **Timezone Support**: Queries support user timezone context
- **AI Intent Classification**: Uses OpenAI to distinguish between new memories, search queries, and reminder requests
- **Scheduled Reminders**: Background scheduler sends reminders at specified times
- **Mem0 Integration**: Optimized for different memory types (text, image, audio)

### Technical Implementation Details

#### Idempotency & Deduplication Strategy

**Message Idempotency:**
- Uses Twilio's unique `MessageSid` as the deduplication key
- Before creating any interaction, checks if `MessageSid` already exists in database
- If duplicate message received, returns existing interaction without creating duplicates
- Ensures safe retry mechanisms and webhook reliability

**Media Deduplication:**
- Generates SHA256 content hash for all media files
- Stores media files with hash-based filenames: `{content_hash}.{extension}`
- Identical media files are reused, not duplicated
- Multiple interactions can reference the same media file
- Saves storage space and processing time

**Memory Deduplication:**
- Uses Mem0's returned memory ID as unique constraint
- If Mem0 returns existing memory ID, updates local record instead of creating duplicate
- Handles cases where Mem0 updates existing memories rather than creating new ones

#### Timezone Handling

**Local Timezone Processing:**
- All datetime operations use local machine timezone (`datetime.now().astimezone()`)
- Reminder scheduling calculates times in user's local timezone, not UTC
- Intent classification includes current local time context for accurate temporal references
- Natural language time expressions ("tomorrow", "in 2 hours") calculated from current local time

**Database Storage:**
- All timestamps stored with timezone information (`DateTime(timezone=True)`)
- Queries support timezone-aware filtering and sorting
- Analytics and reporting respect local timezone context

**Reminder Scheduling:**
- Converts local time expressions to exact timestamps using current local time
- Background scheduler runs in local timezone for accurate reminder delivery
- Handles edge cases like "tomorrow at 3pm" when it's already past 3pm today

### Semantic Search & Intent Classification

The application uses AI-powered intent classification to automatically determine whether a message is:
- **New Memory**: Information to be stored (e.g., "I got a haircut today", "Meeting with John at 3pm")
- **Search Query**: Request for previously stored information (e.g., "What did I plan for dinner?", "Show me my recent photos")
- **Reminder Request**: Request to be reminded at a specific time (e.g., "Remind me to call mom tomorrow at 3pm")

**How it works:**
1. Every text message is analyzed using OpenAI's GPT-4
2. The AI classifies the intent with confidence scores
3. Search queries trigger semantic search in Mem0
4. New memories are stored for future retrieval
5. Reminder requests are scheduled for future delivery

**Example interactions:**
- User: "I bought groceries: milk, bread, eggs" → Saved as memory
- User: "What did I buy at the store?" → Searches for grocery-related memories
- User: "Meeting with Sarah tomorrow" → Saved as memory  
- User: "When is my meeting with Sarah?" → Searches for meeting-related memories
- User: "Remind me to call mom tomorrow at 3pm" → Scheduled reminder
- User: "Set a reminder for my meeting at 2pm" → Scheduled reminder

### Scheduled Reminders

The application includes a sophisticated reminder system that:

- **Natural Language Processing**: Understands time expressions like "tomorrow at 3pm", "in 2 hours", "next Monday"
- **Background Scheduling**: Automatically checks for due reminders every minute
- **WhatsApp Delivery**: Sends reminder messages directly to users via WhatsApp
- **Timezone Support**: Handles different timezones correctly
- **Status Tracking**: Tracks reminder status (pending, sent, cancelled)

**Example reminder requests:**
- "Remind me to call mom tomorrow at 3pm"
- "Set a reminder for my meeting at 2pm"
- "Remind me to buy groceries in 2 hours"
- "Alert me to take medicine at 9am"
- "Remind me about the dentist appointment next Monday"

## Setup Instructions

### Prerequisites

- Python 3.8+
- Twilio Account with WhatsApp Sandbox
- Mem0 API Key
- OpenAI API Key (for Whisper transcription and intent classification)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd WA-Memory-Agent
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` with your credentials (see `.env.example` for all required variables):
   ```env
   # Twilio Configuration
   TWILIO_ACCOUNT_SID=your_twilio_account_sid
   TWILIO_AUTH_TOKEN=your_twilio_auth_token
   TWILIO_PHONE_NUMBER=whatsapp:+1234567890
   
   # Mem0 Configuration
   MEM0_API_KEY=your_mem0_api_key
   MEM0_ORG_ID=your_org_id  # Optional
   MEM0_PROJECT_ID=your_project_id  # Optional
   
   # OpenAI Configuration (for Whisper transcription and intent classification)
   OPENAI_API_KEY=your_openai_api_key
   
   # Database Configuration
   DATABASE_URL=sqlite:///./whatsapp_memory.db
   
   # Application Configuration
   SECRET_KEY=your-secret-key-change-this
   DEBUG=true
   HOST=0.0.0.0
   PORT=8000
   ```

4. **Run the application**
   ```bash
   python main.py
   ```

   The server will start at `http://localhost:8000`

### Twilio Configuration

1. **Set up Twilio WhatsApp Sandbox**
   - Go to [Twilio Console](https://console.twilio.com/)
   - Navigate to Messaging > Try it out > Send a WhatsApp message
   - Follow the instructions to join your sandbox

2. **Configure Webhook**
   - In Twilio Console, go to Messaging > Settings > WhatsApp Sandbox
   - Set the webhook URL to: `https://your-domain.com/webhook`
   - For local development, use ngrok: `ngrok http 8000`

## API Endpoints

### WhatsApp Webhook
- `POST /webhook` - Handle incoming WhatsApp messages

### Memory Management
- `POST /memories` - Create a new memory
- `GET /memories?query=<text>` - Search memories (uses Mem0 + local DB)
- `GET /memories/list` - List all memories (from local DB)

### Reminder Management
- `POST /reminders` - Create a new reminder
- `GET /reminders` - List all reminders
- `DELETE /reminders/{reminder_id}` - Cancel a reminder
- `POST /reminders/{reminder_id}/send-now` - Send reminder immediately (for testing)

### Analytics & Interactions
- `GET /interactions/recent?user_id=<id>&limit=<n>` - Get recent interactions (from local DB)
- `GET /analytics/summary?user_id=<id>` - Get analytics summary (from local DB)
- `GET /users/list` - List all users with memory/interaction counts

### Health Check
- `GET /health` - Health check endpoint
- `GET /` - Root endpoint for Twilio validation

## Usage Examples

### WhatsApp Commands

1. **Send a text message**: 
   - New memories: "I got a haircut today", "Meeting with John at 3pm"
   - Search queries: "What did I plan for dinner?", "Show me my recent photos"
   - Reminder requests: "Remind me to call mom tomorrow at 3pm"
2. **Send an image**: Images are processed and saved with user captions
3. **Send a voice note**: Audio is transcribed using Whisper and saved as text memory
4. **List memories**: `/list` - Shows your recent memories with type indicators

### API Examples

**Create a memory:**
```bash
curl -X POST "http://localhost:8000/memories" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Remember to buy groceries tomorrow",
    "memory_type": "text",
    "tags": ["reminder", "groceries"]
  }'
```

**Search memories:**
```bash
curl "http://localhost:8000/memories?query=grocery&limit=5"
```

**Create a reminder:**
```bash
curl -X POST "http://localhost:8000/reminders" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Call mom",
    "scheduled_time": "2025-09-04T15:00:00",
    "timezone": "UTC"
  }'
```

**Get recent interactions:**
```bash
curl "http://localhost:8000/interactions/recent?user_id=1&limit=10"
```

**Get analytics summary:**
```bash
curl "http://localhost:8000/analytics/summary?user_id=1"
```

**List all users:**
```bash
curl "http://localhost:8000/users/list"
```

## Recent Improvements

### Mem0 Integration Fixes
- **Optimized memory creation** for different content types (text, image, audio)
- **Removed problematic metadata** for image and audio memories to ensure successful Mem0 storage
- **Enhanced error handling** with better logging and fallback mechanisms
- **Content validation** to prevent sending empty or too-short content to Mem0

### Database Improvements
- **Better user management** with automatic user detection
- **Enhanced analytics** with memory and interaction counts per user
- **Improved deduplication** for media files and interactions
- **Memory update support** for existing memories with new content

### API Enhancements
- **User-friendly endpoints** that work with or without user_id parameters
- **Better error messages** for debugging and troubleshooting
- **Enhanced logging** for monitoring and debugging
- **Improved response formats** with consistent JSON structures

## Database Schema Details

### Users Table
- `id`: Primary key
- `whatsapp_id`: Unique WhatsApp identifier
- `created_at`: User creation timestamp
- `updated_at`: Last update timestamp

### Interactions Table
- `id`: Primary key
- `twilio_message_sid`: Unique Twilio message ID (for idempotency)
- `user_id`: Foreign key to users
- `interaction_type`: Type of interaction (text, image, audio, command, reminder)
- `content`: Message content
- `media_id`: Foreign key to media (if applicable)
- `transcript`: Audio transcript (for voice notes)
- `interaction_metadata`: JSON metadata
- `created_at`: Interaction timestamp

### Media Table
- `id`: Primary key
- `content_hash`: SHA256 hash for deduplication
- `media_type`: Type of media (image, audio, video)
- `file_path`: Local file path
- `file_size`: File size in bytes
- `mime_type`: MIME type
- `media_metadata`: JSON metadata
- `created_at`: Media creation timestamp

### Memories Table
- `id`: Primary key
- `mem0_id`: Mem0 memory ID (unique constraint)
- `user_id`: Foreign key to users
- `interaction_id`: Foreign key to interactions
- `content`: Memory content
- `memory_type`: Type of memory (text, image, audio)
- `tags`: JSON array of tags
- `created_at`: Memory creation timestamp

### Reminders Table
- `id`: Primary key
- `user_id`: Foreign key to users
- `interaction_id`: Foreign key to interactions
- `message`: Reminder message
- `scheduled_time`: When to send the reminder
- `timezone`: Timezone for the reminder
- `status`: Reminder status (pending, sent, cancelled)
- `reminder_type`: Type of reminder (message, recurring)
- `recurrence_pattern`: JSON pattern for recurring reminders
- `created_at`: Reminder creation timestamp
- `sent_at`: When the reminder was sent

## Development

### Running Tests
```bash
# Test reminder functionality
python test_reminders.py

# Add more tests to the project
pytest
```

### Database Migrations
```bash
# Using Alembic for database migrations
alembic init alembic
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

### Local Development with ngrok
```bash
# Option 1: Use the setup script (recommended)
python setup_ngrok.py

# Option 2: Manual setup
# Install ngrok
brew install ngrok  # macOS
# or download from https://ngrok.com/

# Start the application
python main.py

# In another terminal, start ngrok
ngrok http 8000

# Use the ngrok URL in Twilio webhook configuration
```

## Deployment

### Environment Variables
Ensure all required environment variables are set in production:
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE_NUMBER`
- `MEM0_API_KEY`
- `OPENAI_API_KEY`
- `DATABASE_URL`
- `SECRET_KEY`

### Production Database
For production, use PostgreSQL:
```env
DATABASE_URL=postgresql://username:password@host:port/database
```

### Docker Deployment
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["python", "main.py"]
```

## Troubleshooting

### Common Issues

1. **Twilio webhook not receiving messages**
   - Check ngrok URL is correct in Twilio console
   - Verify webhook URL is accessible

2. **Mem0 API errors**
   - Verify `MEM0_API_KEY` is correct
   - Check Mem0 service status
   - For image/audio memories, ensure metadata is not being sent (handled automatically)

3. **Audio transcription fails**
   - Ensure `OPENAI_API_KEY` is set
   - Check OpenAI API quota

4. **Reminders not being sent**
   - Check if reminder scheduler is running
   - Verify Twilio credentials are correct
   - Check database for pending reminders

5. **Database errors**
   - Verify database URL is correct
   - Check database permissions
   - Ensure database tables are created

6. **Empty analytics/interactions**
   - Check if you're using the correct user_id in API calls
   - Use `/users/list` to see available users and their data counts
   - Verify the user has actual data in the database

### Debugging Tips

- Check application logs for detailed error messages
- Use `/users/list` endpoint to verify user IDs and data counts
- Test individual API endpoints to isolate issues
- Monitor Mem0 API responses for memory creation issues
- Check database directly for data consistency