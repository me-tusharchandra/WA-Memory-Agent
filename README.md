# WhatsApp Memory Assistant

A WhatsApp chatbot using Twilio's WhatsApp API and Mem0's memory layer to ingest and recall images, audio, and text as memories. The bot supports natural language queries and provides persistent memory storage with database analytics.

## Features

- **Multimodal Ingestion**: Accept and process images, voice notes, and text messages
- **Persistent Memory**: Store entries in Mem0 with metadata and embeddings for fast, semantic retrieval
- **Database Persistence**: Capture user interactions and memories with idempotent ingestion and media deduplication
- **Interactive Chat**: Handle conversational queries using context awareness
- **Memory Listing**: `/list` command to enumerate all user memories
- **Analytics**: Database-backed queries and analytics summary
- **Timezone-aware**: Support for timezone-aware queries and filtering

## Architecture

### Database Schema

The application uses a custom database schema with the following entities:

- **Users**: WhatsApp user identities
- **Interactions**: Inbound messages (text, image, audio) with metadata
- **Media**: Media files with content-based deduplication
- **Memories**: Links to Mem0 memories with local metadata

### Key Features

- **Idempotent Ingestion**: Processing the same Twilio message twice won't create duplicates
- **Media Deduplication**: Identical media stored once and re-referenced
- **Memory Linkage**: Each memory traceable to its originating interaction
- **Timezone Support**: Queries support user timezone context

## Setup Instructions

### Prerequisites

- Python 3.8+
- Twilio Account with WhatsApp Sandbox
- Mem0 API Key
- OpenAI API Key (for Whisper transcription)

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
   
   # OpenAI Configuration (for Whisper transcription)
   OPENAI_API_KEY=your_openai_api_key
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
- `GET /memories?query=<text>` - Search memories
- `GET /memories/list` - List all memories

### Analytics
- `GET /interactions/recent?limit=<n>` - Get recent interactions
- `GET /analytics/summary` - Get analytics summary

### Health Check
- `GET /` - Health check endpoint

## Usage Examples

### WhatsApp Commands

1. **Send a text message**: Any text message will be saved as a memory
2. **Send an image**: Images are processed and saved with metadata
3. **Send a voice note**: Audio is transcribed and saved as text memory
4. **List memories**: Send `/list` to see your recent memories

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

**Get recent interactions:**
```bash
curl "http://localhost:8000/interactions/recent?limit=10"
```

**Get analytics summary:**
```bash
curl "http://localhost:8000/analytics/summary"
```

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
- `interaction_type`: Type of interaction (text, image, audio, command)
- `content`: Message content
- `media_id`: Foreign key to media (if applicable)
- `transcript`: Audio transcript (for voice notes)
- `metadata`: JSON metadata
- `created_at`: Interaction timestamp

### Media Table
- `id`: Primary key
- `content_hash`: SHA256 hash for deduplication
- `media_type`: Type of media (image, audio, video)
- `file_path`: Local file path
- `file_size`: File size in bytes
- `mime_type`: MIME type
- `metadata`: JSON metadata
- `created_at`: Media creation timestamp

### Memories Table
- `id`: Primary key
- `mem0_id`: Mem0 memory ID
- `user_id`: Foreign key to users
- `interaction_id`: Foreign key to interactions
- `content`: Memory content
- `memory_type`: Type of memory (text, image, audio)
- `tags`: JSON array of tags
- `created_at`: Memory creation timestamp

## Development

### Running Tests
```bash
# Add tests to the project
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

3. **Audio transcription fails**
   - Ensure `OPENAI_API_KEY` is set
   - Check OpenAI API quota

4. **Database errors**
   - Verify database URL is correct
   - Check database permissions

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License.
