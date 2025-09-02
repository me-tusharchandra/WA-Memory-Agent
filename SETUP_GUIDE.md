# WhatsApp Memory Assistant - Setup Guide

This guide will help you set up and test the WhatsApp Memory Assistant project with detailed debugging information.

## 🚀 Quick Start

### 1. Prerequisites

Before starting, make sure you have:
- Python 3.8+ installed
- A Twilio account with WhatsApp Sandbox access
- A Mem0 API key
- An OpenAI API key (for audio transcription)

### 2. Environment Setup

1. **Clone and navigate to the project:**
   ```bash
   cd /Users/tusharchandra/workspace/repos/WA-Memory-Agent
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create environment file:**
   ```bash
   cp .env.example .env
   ```

4. **Edit `.env` with your credentials:**
   ```env
   # Twilio Configuration
   TWILIO_ACCOUNT_SID=your_twilio_account_sid
   TWILIO_AUTH_TOKEN=your_twilio_auth_token
   TWILIO_PHONE_NUMBER=whatsapp:+1234567890

   # Mem0 Configuration
   MEM0_API_KEY=your_mem0_api_key
   MEM0_ORG_ID=your_org_id  # Optional
   MEM0_PROJECT_ID=your_project_id  # Optional

   # Database Configuration
   DATABASE_URL=sqlite:///./whatsapp_memory.db

   # OpenAI Configuration (for Whisper transcription)
   OPENAI_API_KEY=your_openai_api_key

   # Application Configuration
   SECRET_KEY=your-secret-key-change-this
   DEBUG=true
   HOST=0.0.0.0
   PORT=8000
   ```

### 3. Get Required API Keys

#### Twilio Setup
1. Go to [Twilio Console](https://console.twilio.com/)
2. Navigate to Messaging > Try it out > Send a WhatsApp message
3. Follow instructions to join your sandbox
4. Copy your Account SID and Auth Token

#### Mem0 Setup
1. Go to [Mem0](https://mem0.ai/)
2. Create an account and get your API key
3. Optionally set up an organization and project

#### OpenAI Setup
1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Create an API key for Whisper transcription

### 4. Start the Application

#### Option 1: Direct Start (for testing)
```bash
python main.py
```

#### Option 2: With ngrok (for WhatsApp integration)
```bash
# Terminal 1: Start the app
python main.py

# Terminal 2: Start ngrok
python setup_ngrok.py
# OR manually: ngrok http 8000
```

### 5. Configure Twilio Webhook

1. In Twilio Console, go to Messaging > Settings > WhatsApp Sandbox
2. Set webhook URL to your ngrok URL + `/webhook`
   - Example: `https://abc123.ngrok.io/webhook`

## 🧪 Testing the Application

### 1. Health Check
```bash
curl http://localhost:8000/health
```
Expected response: `{"message": "WhatsApp Memory Assistant API", "status": "running"}`

### 2. Test API Endpoints

#### Create a Memory
```bash
curl -X POST "http://localhost:8000/memories" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Remember to buy groceries tomorrow",
    "memory_type": "text",
    "tags": ["reminder", "groceries"]
  }'
```

#### Search Memories
```bash
curl "http://localhost:8000/memories?query=grocery&limit=5"
```

#### List All Memories
```bash
curl "http://localhost:8000/memories/list?limit=10"
```

#### Get Analytics
```bash
curl "http://localhost:8000/analytics/summary"
```

### 3. Test WhatsApp Integration

1. **Send a text message** to your Twilio WhatsApp number
2. **Send an image** to test media processing
3. **Send a voice note** to test audio transcription
4. **Send `/list`** to see your memories

## 🔍 Debug Information

The application now includes comprehensive logging. You'll see:

### Startup Logs
```
🚀 Starting WhatsApp Memory Assistant...
📊 Database URL: sqlite:///./whatsapp_memory.db
🔧 Debug mode: True
🌐 Host: 0.0.0.0:8000
✅ Database tables created successfully
✅ Application startup complete
```

### Webhook Processing Logs
```
📱 Received webhook from Twilio
👤 Processing message for user: +1234567890
✅ User ID: 1
💬 Processing text message...
💾 Creating interaction for text message...
✅ Created interaction ID: 1
🧠 Creating memory in Mem0...
✅ Created memory ID: 1 (Mem0 ID: mem_abc123)
📤 Sending response: I've saved your text message as a memory!...
```

### Media Processing Logs
```
📷 Processing media message...
⬇️ Downloading media from: https://api.twilio.com/...
✅ Downloaded media: 1024000 bytes
🖼️ Processing image...
✅ Processed image: 1920x1080, format: JPEG
📊 Getting media metadata...
💾 Creating or getting media entry...
✅ Media ID: 1
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Database Errors
```
❌ Failed to create database tables: ...
```
**Solution:** Check if you have write permissions in the project directory

#### 2. Mem0 API Errors
```
❌ Failed to create memory in Mem0: ...
```
**Solution:** Verify your Mem0 API key is correct and has proper permissions

#### 3. Twilio Webhook Not Receiving Messages
```
📱 No webhook logs appearing
```
**Solution:** 
- Check ngrok URL is accessible
- Verify webhook URL in Twilio console
- Check ngrok tunnel is running

#### 4. Audio Transcription Fails
```
❌ Whisper model not available
```
**Solution:** Set your OpenAI API key in the `.env` file

#### 5. Media Download Fails
```
❌ Failed to download media: ...
```
**Solution:** Check your Twilio credentials are correct

### Debug Commands

#### Check Database
```bash
# View SQLite database
sqlite3 whatsapp_memory.db
.tables
SELECT * FROM users;
SELECT * FROM interactions;
SELECT * FROM memories;
```

#### Check Logs
The application logs to stdout. Look for:
- ✅ Success messages
- ❌ Error messages  
- 🔍 Debug information
- 📊 Processing details

#### Test Individual Components

**Test Mem0 Connection:**
```bash
python -c "
import asyncio
from app.mem0_client import mem0_client
async def test():
    try:
        result = await mem0_client.list_memories(limit=1)
        print('✅ Mem0 connection successful')
    except Exception as e:
        print(f'❌ Mem0 connection failed: {e}')
asyncio.run(test())
"
```

**Test Media Processing:**
```bash
python -c "
import asyncio
from app.media_processor import media_processor
async def test():
    try:
        metadata = await media_processor.get_media_metadata(b'test', 'text/plain')
        print('✅ Media processor working')
    except Exception as e:
        print(f'❌ Media processor failed: {e}')
asyncio.run(test())
"
```

## 📱 WhatsApp Testing Workflow

1. **Start the application** with debug logging
2. **Set up ngrok** tunnel
3. **Configure Twilio webhook** with ngrok URL
4. **Send test messages**:
   - Text: "Hello, this is a test message"
   - Image: Send any image
   - Audio: Send a voice note
   - Command: Send "/list"
5. **Monitor logs** for processing details
6. **Check database** for stored data

## 🔧 Development Tips

### Adding More Debug Information
The application uses Python's `logging` module. To add more debug info:

```python
import logging
logger = logging.getLogger(__name__)

logger.debug("Detailed debug info")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error message")
```

### Database Inspection
```bash
# Install SQLite browser for GUI
brew install db-browser-for-sqlite
db-browser-for-sqlite whatsapp_memory.db
```

### API Documentation
Once running, visit: `http://localhost:8000/docs` for interactive API documentation.

## 🎯 Next Steps

After successful setup:
1. Test all message types (text, image, audio)
2. Verify memories are stored in both local DB and Mem0
3. Test the `/list` command
4. Try searching memories via API
5. Check analytics endpoint
6. Consider production deployment

## 📞 Support

If you encounter issues:
1. Check the debug logs for specific error messages
2. Verify all API keys are correct
3. Ensure all dependencies are installed
4. Check network connectivity for external APIs
5. Review the troubleshooting section above
