# Key Translation Bot 🌐

Multi-language real-time Discord translation bot powered by Google Gemini API.

## Features

- ✨ **Real-time Translation**: Automatically translates messages between Korean, English, Japanese, and Chinese channels
- 🖼️ **Image & File Support**: Shares images and files across all language channels
- 😊 **Emoji & Sticker Support**: Discord custom emojis and stickers are shared without translation
- 🔗 **Link & Embed Preservation**: Maintains Discord embeds and links across translations
- 🛡️ **Mention Safety**: Prevents @everyone and @here from propagating across channels
- 💰 **Cost Monitoring**: Built-in API cost tracking and limits
- ⚡ **Rate Limiting**: Configurable request limits to prevent API abuse
- 🏥 **Health Monitoring**: HTTP health endpoints for monitoring bot status

## Quick Start

1. **Clone and Setup**
   ```bash
   git clone <repository-url>
   cd key
   cp .env.example .env
   # Edit .env with your credentials
   ```

2. **Run with Docker Compose**
   ```bash
   docker-compose up -d
   ```

3. **Check Status**
   ```bash
   curl http://localhost:8080/health
   ```

## Configuration

Configure the bot using environment variables in `.env`:

```env
# Discord Bot Configuration
DISCORD_TOKEN=your_discord_bot_token

# Google Gemini API Configuration  
GEMINI_API_KEY=your_gemini_api_key

# Discord Server Configuration
SERVER_ID=your_server_id
KOREAN_CHANNEL_ID=korean_channel_id
ENGLISH_CHANNEL_ID=english_channel_id
JAPANESE_CHANNEL_ID=japanese_channel_id
CHINESE_CHANNEL_ID=chinese_channel_id

# Rate Limiting (optional)
RATE_LIMIT_PER_MINUTE=30
MAX_DAILY_REQUESTS=1000

# Cost Monitoring (optional)
MAX_MONTHLY_COST_USD=10.0
COST_ALERT_THRESHOLD_USD=8.0

# Logging (optional)
LOG_LEVEL=INFO
```

## Docker Commands

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Rebuild after code changes
docker-compose up -d --build
```

## Bot Commands

- `/status` - Check bot status, rate limits, and cost monitoring
- `/help` - Show help information

## Monitoring

The bot exposes several HTTP endpoints for monitoring:

- `GET /health` - Health check endpoint
- `GET /status` - Detailed bot status
- `GET /metrics` - Prometheus-compatible metrics

## Architecture

```
key/
├── main.py                 # Bot entry point
├── bot/
│   ├── translation_bot.py  # Main bot class
│   ├── translator.py       # Gemini API integration
│   ├── image_handler.py    # File/image processing
│   └── health_server.py    # HTTP monitoring server
├── utils/
│   ├── logger.py          # Logging setup
│   ├── rate_limiter.py    # Rate limiting logic
│   └── cost_monitor.py    # API cost tracking
├── docker-compose.yml     # Docker composition
├── Dockerfile            # Container definition
└── requirements.txt      # Python dependencies
```

## Translation Logic

1. **Message Analysis**: Determines message type (text, emoji-only, sticker, attachment, embed)
2. **Skip Translation**: Discord emojis (`<:name:id>`) and stickers are shared directly without translation
3. **Language Detection**: Automatically detects source language for text content
4. **Content Processing**: Cleans mentions and special Discord syntax before translation
5. **Translation**: Uses Gemini 2.0 Flash to translate text to target languages
6. **Post-processing**: Restores Discord formatting and sends to appropriate channels

## Safety Features

- **Mention Prevention**: @everyone, @here, and user mentions are converted to safe text
- **Rate Limiting**: Configurable per-minute and daily request limits
- **Cost Monitoring**: Tracks API usage and prevents exceeding budget limits
- **Error Handling**: Graceful error handling with comprehensive logging

## Troubleshooting

### Common Issues and Solutions

#### 1. Privileged Intents Error
```
discord.errors.PrivilegedIntentsRequired: Shard ID None is requesting privileged intents
```

**Solution**: Enable Message Content Intent in Discord Developer Portal:
1. Go to https://discord.com/developers/applications/
2. Select your bot application
3. Navigate to "Bot" section
4. Enable "Message Content Intent" under "Privileged Gateway Intents"

#### 2. Permission Denied for Log Files
```
Fatal error: [Errno 13] Permission denied: '/app/logs/key_bot.log'
```

**Solution Options**:
- **Option A**: Use named volumes (recommended)
  ```yaml
  volumes:
    - key_logs:/app/logs
    - key_data:/app/data
  ```
- **Option B**: Fix host directory permissions
  ```bash
  sudo chown -R 1000:1000 ./logs ./data
  chmod -R 755 ./logs ./data
  ```

#### 3. Gemini Model Not Found Error
```
404 models/gemini-pro is not found for API version v1beta
```

**Solution**: Update to latest Gemini model in `bot/translator.py`:
```python
self.model = genai.GenerativeModel('gemini-2.0-flash')
```

#### 4. Bot Not Visible in Discord Server
- Ensure bot is properly invited with correct permissions:
  - Send Messages
  - Read Messages
  - Read Message History
  - Attach Files
  - Embed Links
  - Use Slash Commands
- Check bot is online in member list
- Verify bot has access to the configured language channels

### Debugging Options

#### Log Levels
Configure logging verbosity via environment variable:
```env
# Available options: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=DEBUG  # Most verbose
LOG_LEVEL=INFO   # Default
LOG_LEVEL=ERROR  # Minimal
```

#### View Container Logs
```bash
# View live logs
docker-compose logs -f key-bot

# View recent logs
docker logs key-discord-bot

# View logs with timestamps
docker logs -t key-discord-bot
```

#### Health Check Endpoints
Monitor bot status via HTTP endpoints:
```bash
# Basic health check
curl http://localhost:8080/health

# Detailed status
curl http://localhost:8080/status

# Prometheus metrics
curl http://localhost:8080/metrics
```

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run directly (development)
python main.py

# Run with debug logging
LOG_LEVEL=DEBUG python main.py

# Test specific components
python -c "from bot.translator import GeminiTranslator; print('Translator OK')"
```

## License

This project is licensed under the MIT License.