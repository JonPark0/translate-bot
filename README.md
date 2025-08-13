# Key Translation Bot 🌐

Multi-language real-time Discord translation bot powered by Google Gemini API.

> 🇰🇷 **한국어 문서**: [README.ko.md](README.ko.md)를 참조하세요.

## Features

- ✨ **Real-time Translation**: Automatically translates messages between Korean, English, Japanese, and Chinese channels
- 🖼️ **Image & File Support**: Shares images and files across all language channels
- 😊 **Emoji & Sticker Support**: Discord custom emojis and stickers are shared without translation
- 🔗 **Link & Embed Preservation**: Maintains Discord embeds and links across translations
- 🛡️ **Mention Safety**: Prevents @everyone and @here from propagating across channels
- 💰 **Cost Monitoring**: Built-in API cost tracking and limits
- ⚡ **Rate Limiting**: Configurable request limits to prevent API abuse
- 🏥 **Health Monitoring**: HTTP health endpoints for monitoring bot status
- 🗑️ **Message Synchronization**: Automatically deletes translated messages when original is deleted
- ✏️ **Edit Synchronization**: Updates translated messages in place when original is edited
- 💬 **Reply Support**: Maintains reply chains across language channels

## Quick Start

### 1. Discord Bot Setup

**Create and Configure Bot:**
1. Go to [Discord Developer Portal](https://discord.com/developers/applications/)
2. Create a new application → Add Bot
3. Copy the Bot Token for your `.env` file
4. Enable **Message Content Intent** under "Privileged Gateway Intents"

**Generate Bot Invite URL:**
1. Go to **OAuth2** → **URL Generator**
2. Select **Scopes:**
   - ✅ `bot`
   - ✅ `applications.commands`
3. Select **Bot Permissions:**
   - ✅ Send Messages
   - ✅ Read Messages
   - ✅ Read Message History
   - ✅ Attach Files
   - ✅ Embed Links
   - ✅ Use Slash Commands
   - ✅ **Use External Emojis** (Critical for emoji support)
   - ✅ **Use External Stickers** (Critical for sticker support)
4. Copy the generated URL and invite bot to your server

### 2. Project Setup

**Clone and Configure:**
```bash
git clone <repository-url>
cd key
cp .env.example .env
# Edit .env with your Discord bot token and Gemini API key
```

**Run with Docker Compose:**
```bash
docker-compose up -d
```

**Check Status:**
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
- `/test_logging` - Test all logging levels (Admin only)

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
│   ├── cost_monitor.py    # API cost tracking
│   └── message_tracker.py # Message relationship tracking
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
7. **Message Tracking**: Records relationships between original and translated messages
8. **Synchronization**: Handles message deletions, edits, and reply chains across channels

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

#### 3. Emojis and Stickers Not Displaying Properly
```
Message shows: "Username: :emoji_name:" instead of actual emoji
```

**Problem**: Bot lacks proper permissions to use emojis and stickers.

**Solution**: Update bot permissions in Discord Developer Portal:
1. Go to **OAuth2** → **URL Generator**
2. Regenerate invite URL with these additional permissions:
   - ✅ **Use External Emojis**
   - ✅ **Use External Stickers**
3. Re-invite bot to server with new permissions

**Alternative**: Manually grant permissions in server:
- Server Settings → Roles → Bot Role
- Enable "Use External Emojis" and "Use External Stickers"

#### 4. Animated Stickers Not Displaying
```
Animated stickers appear as static images or broken links
```

**Problem**: Discord CDN URL format varies for animated stickers.

**Solution**: The bot automatically tries multiple URL formats:
- Primary: `https://cdn.discordapp.com/stickers/{id}.gif`
- Fallbacks: `.webp`, `.png`, alternative CDN paths
- Check logs for URL testing results with DEBUG level logging

#### 5. Gemini Model Not Found Error
```
404 models/gemini-pro is not found for API version v1beta
```

**Solution**: Update to latest Gemini model in `bot/translator.py`:
```python
self.model = genai.GenerativeModel('gemini-2.0-flash')
```

#### 6. Bot Not Visible in Discord Server
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