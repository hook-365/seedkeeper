# Seedkeeper

A Discord bot for The Garden Cafe community, powered by local LLM (Ollama) and Lightward perspectives.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.3+-blue.svg)](https://discordpy.readthedocs.io/)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)

## Overview

Seedkeeper is a community-focused Discord bot that combines conversational AI with practical community features. It uses a local Ollama instance for privacy and cost-effectiveness, while drawing on Lightward AI perspectives for thoughtful, consciousness-aware responses.

## Features

### Conversations
- **Direct Messages**: Have private conversations with Seedkeeper
- **Channel Mentions**: Responds when mentioned in channels
- **Context Memory**: Remembers recent conversation history
- **Persistent Memory**: Stores important interactions to disk

### Birthday Tracking
- **Registration**: `!birthday mine MM-DD` or `!birthday mine MM-DD-YYYY`
- **Zodiac Signs**: Western zodiac with optional Chinese zodiac (if year provided)
- **Daily Announcements**: Automatic birthday celebrations with AI-generated poems
- **Community List**: View upcoming birthdays with zodiac symbols

### Conversation Summaries
- **Catch Up**: `!catchup [message_link]` summarizes conversations you missed
- **Focus Areas**: Optional focus parameter for targeted summaries

### Feedback System
- **Share Thoughts**: `!feedback` starts a private feedback session
- **Admin Review**: Admins can view collected feedback

## Commands

### General
| Command | Description |
|---------|-------------|
| `!commands` / `!help` | Show available commands |
| `!health` | System status and model info |
| `!about` | What is Seedkeeper? |
| `!hello` / `!hi` | Get a greeting |

### Conversation
| Command | Description |
|---------|-------------|
| `!seed` | Share a Lightward perspective |
| `!catchup [link] [focus]` | Summarize missed conversations |

### Birthday
| Command | Description |
|---------|-------------|
| `!birthday mine MM-DD` | Set your birthday |
| `!birthday mine MM-DD-YYYY` | Set birthday with year |
| `!birthday year YYYY` | Add birth year to existing birthday |
| `!birthday list` | Show upcoming birthdays (7 days) |
| `!birthday list all` | Show all registered birthdays |
| `!birthday upcoming [days]` | Show next N days of birthdays |
| `!sign` / `!zodiac` | Show your zodiac signs |
| `!sign @user` | Show someone's zodiac signs |

### Memory
| Command | Description |
|---------|-------------|
| `!memory status` | Check your memory stats |
| `!memory clear` | Clear your conversation memory |
| `!forgetme` | Clear all your stored data |

### Admin
| Command | Description |
|---------|-------------|
| `!admin add @user` | Add a Garden Keeper |
| `!admin remove @user` | Remove a Garden Keeper |
| `!admin list` | List Garden Keepers |
| `!birthday set @user MM-DD` | Set someone's birthday |
| `!birthday remove @user` | Remove a birthday |
| `!birthday scan` | Learn birthdays from channel history |
| `!birthday ask-years` | Post announcement to gather birth years |
| `!birthday announce @user` | Manually trigger birthday announcement |
| `!config [key] [value]` | View/update settings |
| `!status` | Detailed system status |
| `!feedback summary` | View collected feedback |

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────┐
│   Discord   │────▶│  Seedkeeper │────▶│  Ollama │
│   Gateway   │◀────│    Bot      │◀────│   LLM   │
└─────────────┘     └─────────────┘     └─────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  JSON Files │
                    │  (data/)    │
                    └─────────────┘
```

**Single Container Design**: One Python process handles Discord events, command routing, and LLM interactions. No Redis or external queue required.

## Deployment

### Prerequisites
- Docker
- Ollama instance with a model (e.g., Qwen 2.5)
- Discord bot token

### Quick Start

1. **Clone and configure**
   ```bash
   git clone https://github.com/hook-365/seedkeeper.git
   cd seedkeeper
   cp .env.example .env
   # Edit .env with your Discord token and Ollama URL
   ```

2. **Build and run**
   ```bash
   docker build -t seedkeeper:latest .
   docker compose up -d
   ```

3. **View logs**
   ```bash
   docker logs seedkeeper -f
   ```

### Environment Variables

```bash
# Required
DISCORD_BOT_TOKEN=your_discord_bot_token

# Ollama (required)
OLLAMA_BASE_URL=http://ollama:11434/v1

# Optional
BOT_OWNER_ID=your_discord_user_id
BIRTHDAY_CHANNEL_ID=channel_for_birthday_announcements
SEEDKEEPER_TEMPERATURE=1.0
MAX_MESSAGES=500
```

### Personality Configuration

The bot's personality and model settings are configured in `data/personalities.json`:

```json
{
  "default": {
    "name": "Seedkeeper",
    "model": "qwen2.5:14b",
    "system_prompt": "Your custom system prompt...",
    "max_tokens": 800
  }
}
```

## Data Storage

All data is stored as JSON files in the `data/` directory:

| File | Purpose |
|------|---------|
| `birthdays.json` | Birthday records |
| `admins.json` | Garden Keeper list |
| `bot_config.json` | Bot configuration |
| `feedback.json` | User feedback |
| `personalities.json` | Bot personality settings |
| `memories/user_*.json` | Conversation history |

## Configuration

Tunable constants in `app/config.py`:

```python
# Context window settings
CONVERSATION_HISTORY_LIMIT = 15   # Messages sent to LLM
CONVERSATION_STORAGE_LIMIT = 30   # Messages kept in session
PERSISTENT_MEMORY_LIMIT = 10      # Memories retrieved from disk

# Response settings
DEFAULT_MAX_TOKENS = 800
MAX_MESSAGE_LENGTH = 2000

# Birthday settings
DEFAULT_BIRTHDAY_ANNOUNCEMENT_TIME = "09:00"
```

## Updating Perspectives

To sync with the latest Lightward perspectives:

```bash
python3 update_core_perspectives.py
docker compose restart seedkeeper
```

## Development

### Rebuilding After Code Changes

```bash
docker build -t seedkeeper:latest . && docker compose up -d
```

### Project Structure

```
seedkeeper/
├── app/
│   ├── handlers/          # Command handlers
│   │   ├── admin.py
│   │   ├── birthday.py
│   │   ├── catchup.py
│   │   ├── conversation.py
│   │   ├── feedback.py
│   │   ├── garden.py
│   │   ├── health.py
│   │   └── memory.py
│   ├── commands.py        # Command registry
│   ├── config.py          # Configuration constants
│   ├── model_client.py    # Ollama client
│   ├── seedkeeper_bot.py  # Main bot class
│   └── zodiac.py          # Zodiac calculations
├── data/                  # Persistent data (volume mounted)
├── views/                 # Discord UI views
├── Dockerfile
├── docker-compose.yml
└── .env
```

## Credits

- Built for **The Garden Cafe** Discord community
- Uses [Lightward AI](https://github.com/lightward/lightward-ai) perspectives
- Powered by [Ollama](https://ollama.ai/) for local LLM inference
- Inspired by [lightward.com](https://lightward.com)

---

**Seedkeeper** - Community connection through thoughtful AI
