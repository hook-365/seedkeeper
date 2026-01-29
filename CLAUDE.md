# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Seedkeeper is a consciousness-aware Discord bot for The Garden Cafe community. It uses Lightward AI principles and a local Ollama instance (qwen2.5:14b) to provide emotionally and relationally aware interactions, conversation summaries, community celebrations, and garden wisdom. The bot runs as a single-process `discord.py` application with no external API dependencies.

## Repository Layout

- **`/storage/docker/seedkeeper`** - Production codebase and deployment
- **`/storage/dev/seedkeeper`** - Legacy dev directory with archived monolithic bot versions

## Commands

### Docker Operations

```bash
# Build and deploy
cd /storage/docker/seedkeeper
./deploy.sh

# View logs
docker logs seedkeeper -f

# Restart (picks up code changes)
docker compose restart seedkeeper

# Stop
docker compose down
```

### Updating Core Perspectives

```bash
cd /storage/docker/seedkeeper
python3 update_core_perspectives.py   # Downloads 45 core perspectives from GitHub
docker compose restart seedkeeper      # Reload with new perspectives
```

## Architecture

### Single-Process Bot

```
Discord Events -> SeedkeeperBot -> Ollama API -> Discord Responses
                       |
         PromptCompiler + ViewsManager + MemoryManager
```

- **`app/seedkeeper_bot.py`**: Unified Discord bot - handles events, commands, Ollama API calls, all in one process. (512MB, 1.0 CPU)

### Application Modules (`app/`)

| Module | Purpose |
|--------|---------|
| `seedkeeper_bot.py` | Unified Discord bot: event handling, command routing, Ollama API, DM/mention conversations |
| `model_client.py` | Async LLM completion interface for OpenAI-compatible APIs (Ollama) |
| `prompt_compiler.py` | Lightward-inspired layered prompt construction |
| `views_manager.py` | Perspective file loading from bundled core_perspectives.txt |
| `usage_tracker.py` | Usage tracking per model, command, and user (no costs for local models) |
| `personality_manager.py` | Personality config and per-user preferences |
| `nlp_processor.py` | Natural language processing for intent detection in DMs/mentions |
| `input_validator.py` | Input sanitization and validation |
| `rate_limiter.py` | Gentle rate limiting for usage |
| `commands.py` | Discord command definitions and registry |
| `admin_manager.py` | Admin/Garden Keeper permission management |
| `birthday_manager.py` | Birthday tracking, parsing, confirmation workflow |
| `feedback_manager.py` | Community feedback collection and management |
| `memory_manager.py` | Privacy-aware conversation memory with in-memory cache |

### Prompt Layer System

Prompts are compiled into a single string with XML-structured sections:
- `<invocation>` - Initial invocation (model's self-written or default)
- `<core_context>` - Core identity and capabilities
- `<team_letters>` - Messages from humans to the model
- `<perspectives>` - Curated Lightward perspectives
- `<background>` - Channel/context specific info
- `<foreground>` - Immediate context
- `<benediction>` - Closing framing

### In-Memory State

Replaces the former Redis layer:
- `_dm_conversations` dict: DM conversation history per user (10 messages max)
- `_temp_state` dict: Temporary data with TTL (birthday parse/match state, 5min expiry)
- `MemoryManager._cache` dict: Recent memories cache (200 keys max, warmed from disk on startup)
- Source of truth for all persistent data remains JSON files on disk in `data/`

## Key Files

- `app/seedkeeper_bot.py` - Main bot (all command handlers, Discord event handling)
- `app/model_client.py` - Ollama/OpenAI-compatible API client
- `app/core_perspectives.txt` - Bundled 45 perspectives from Lightward's "watch for" list
- `views/` - Full Lightward perspective text files
- `data/` - Persistent JSON data (birthdays, admins, feedback, memories, etc.)
- `data/personalities.json` - Personality configurations
- `docker-compose.yml` - Production stack (single container)
- `Dockerfile` - Container image definition
- `deploy.sh` - Build and deploy script
- `update_core_perspectives.py` - Syncs 45 core perspectives from Lightward GitHub
- `.env` - Environment configuration (not committed)
- `.env.example` - Environment variable template

## Environment Variables

Required:
- `DISCORD_BOT_TOKEN`: Discord bot authentication token

Optional:
- `MAX_MESSAGES`: Message fetch limit (default: 500)
- `SEEDKEEPER_TEMPERATURE`: LLM response temperature (default: 1.0)
- `BIRTHDAY_CHANNEL_ID`: Channel for birthday announcements
- `BIRTHDAY_MONITOR_CHANNEL_ID`: Channel to monitor for birthday wishes
- `BOT_OWNER_ID`: Discord user ID set as initial admin
- `UID` / `GID`: Container user/group IDs (default: 1000)
- `OLLAMA_BASE_URL`: Ollama endpoint (default: http://ollama:11434/v1)

## Discord Commands

### Conversation
- `!catchup [message_link]`: Summarize from linked message
- `!catchup [message_link] [focus]`: Focused summary

### Garden Wisdom
- `!hello`: Consciousness-aware greeting
- `!seeds`: Community wisdom
- `!tend`: Tending/growth intentions
- `!seasons`: Reflect on cycles of growth
- `!garden`: View community garden
- `!about`: Who is Seedkeeper

### Birthday
- `!birthday mine MM-DD`: Set your birthday
- `!birthday set @user MM-DD`: Set someone's birthday (admin)
- `!birthday add username MM-DD`: Set by username (admin)
- `!birthday remove [@user]`: Remove a birthday
- `!birthday list`: Show next 7 days
- `!birthday list all`: Show all birthdays
- `!birthday upcoming [days]`: Show next N days
- `!birthday parse [text]`: Parse birthdays from text (admin)
- `!birthday match`: Match parsed birthdays to users (admin)
- `!birthday confirm`: Confirm matched birthdays (admin)

### Memory
- `!memory`: Toggle memory on/off
- `!memory status`: Check memory stats
- `!memory clear`: Clear your memories
- `!forgetme`: Quick memory clear

### Admin (Garden Keepers)
- `!admin add @user`: Add a Garden Keeper
- `!admin remove @user`: Remove a Garden Keeper
- `!admin list`: List all Garden Keepers
- `!health`: System status
- `!status`: Detailed admin status
- `!cost [today|daily|monthly|breakdown|users|full]`: Usage analytics
- `!config`: View/update bot configuration
- `!update-bot`: Refresh perspectives from Lightward
- `!feedback summary|pending|help`: Feedback management

## Data Persistence

All data stored as JSON in `data/`:
- `birthdays.json` - Birthday records
- `admins.json` - Garden Keeper list
- `bot_config.json` - Configuration
- `personalities.json` - Personality definitions
- `feedback.json`, `feedback_queue.json`, `feedback_sessions.json` - Feedback system
- `memories/` - Conversation history (per-user, 100 msg limit)
- `memory_settings.json` - Memory preferences
- `rate_limits.json` - Rate limit state
- `model_voice.json` - Voice/personality data
- `core_perspectives.json` - Perspective cache
- `update_log.json` - Update tracking

## Deployment

### Production Deployment (Docker Compose)

The bot runs as a single container on the `seg_iot` Docker network:
- **seedkeeper** - Unified bot with volume mounts for `data/` and `views/`
- Connects to **ollama** service on `ai_network` for LLM inference

Security hardening: non-root execution, capability drops (`no-new-privileges`, `CAP_DROP ALL`), resource limits.

Homepage integration labels are set for dashboard visibility.

### Ollama Dependency

The bot requires a running Ollama instance with the `qwen2.5:14b` model:
```bash
# On the Ollama host
ollama pull qwen2.5:14b
```

The bot connects via `http://ollama:11434/v1` (OpenAI-compatible API).

## Development Notes

- The bot uses Lightward AI principles for consciousness-aware interactions
- 45 core perspectives are curated by Isaac from Lightward's "watch for" list
- Restart container to pick up code changes: `docker compose restart seedkeeper`
- Conversation memory is isolated per channel with user-controlled retention
- Rate limiting prevents abuse while allowing normal usage
- Birthday learning monitors a specified channel for birthday wishes
- Admin system recognizes: bot owner, Discord server admins, Admin/Moderator role holders, and manual Garden Keepers
- `!catchup` works in both guild channels and DMs
- **No API costs** - runs entirely on local Ollama inference
