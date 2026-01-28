# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Seedkeeper is a consciousness-aware Discord bot for The Garden Cafe community. It uses Lightward AI principles and the Claude API to provide emotionally and relationally aware interactions, conversation summaries, community celebrations, and garden wisdom. The bot runs as a single-process `discord.py` application.

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
Discord Events -> SeedkeeperBot -> Claude API -> Discord Responses
                       |
         PromptCompiler + ViewsManager + MemoryManager
```

- **`app/seedkeeper_bot.py`**: Unified Discord bot — handles events, commands, Claude API calls, all in one process. (512MB, 1.0 CPU)

### Application Modules (`app/`)

| Module | Purpose |
|--------|---------|
| `seedkeeper_bot.py` | Unified Discord bot: event handling, command routing, Claude API, DM/mention conversations |
| `prompt_compiler.py` | Lightward-inspired layered prompt construction with multi-block caching |
| `views_manager.py` | Perspective file loading from bundled core_perspectives.txt |
| `usage_tracker.py` | API cost and usage tracking per model, command, and user |
| `nlp_processor.py` | Natural language processing for intent detection in DMs/mentions |
| `input_validator.py` | Input sanitization and validation |
| `rate_limiter.py` | Gentle rate limiting for API usage |
| `commands.py` | Discord command definitions and registry |
| `admin_manager.py` | Admin/Garden Keeper permission management |
| `birthday_manager.py` | Birthday tracking, parsing, confirmation workflow |
| `feedback_manager.py` | Community feedback collection and management |
| `memory_manager.py` | Privacy-aware conversation memory with in-memory cache |

### Prompt Layer System (`app/context/`)

Prompts are compiled from numbered layers:
0. `0-invocation` - Initial invocation
1. `1-core-context` - Core contextual framing
2. `2-core-perspectives` - 45 curated Lightward perspectives
3. `3-perspectives` - Additional perspectives
4. `4-letters-from-team` - Team communications
5. `5-background-background` - Deep background context
6. `6-background` - Background context
7. `7-foreground` - Active context
8. `8-foreground-foreground` - Immediate context
9. `9-benediction` - Closing framing

### Smart Model Routing

The bot automatically selects between Claude models:
- **Haiku** (economical): Simple commands (!hello, !seeds, !garden), short messages, factual queries
- **Sonnet** (deep): Complex commands (!catchup, !feedback), questions, DMs with depth, emotional content

### In-Memory State

Replaces the former Redis layer:
- `_dm_conversations` dict: DM conversation history per user (10 messages max)
- `_temp_state` dict: Temporary data with TTL (birthday parse/match state, 5min expiry)
- `MemoryManager._cache` dict: Recent memories cache (200 keys max, warmed from disk on startup)
- Source of truth for all persistent data remains JSON files on disk in `data/`

## Key Files

- `app/seedkeeper_bot.py` - Main bot (all command handlers, Discord event handling)
- `app/core_perspectives.txt` - Bundled 45 perspectives from Lightward's "watch for" list
- `app/context/` - Numbered prompt layer files
- `views/` - Full Lightward perspective text files
- `data/` - Persistent JSON data (birthdays, admins, feedback, memories, etc.)
- `docker-compose.yml` - Production stack (single container)
- `Dockerfile` - Container image definition
- `deploy.sh` - Build and deploy script
- `update_core_perspectives.py` - Syncs 45 core perspectives from Lightward GitHub
- `.env` - Environment configuration (not committed)
- `.env.example` - Environment variable template

## Environment Variables

Required:
- `DISCORD_BOT_TOKEN`: Discord bot authentication token
- `ANTHROPIC_API_KEY`: Claude API key

Optional:
- `CLAUDE_MODEL`: Model selection (default: claude-sonnet-4-5-20250929)
- `MAX_MESSAGES`: Message fetch limit (default: 500)
- `SEEDKEEPER_TEMPERATURE`: Claude response temperature (default: 1.0)
- `BIRTHDAY_CHANNEL_ID`: Channel for birthday announcements
- `BIRTHDAY_MONITOR_CHANNEL_ID`: Channel to monitor for birthday wishes
- `BOT_OWNER_ID`: Discord user ID set as initial admin
- `UID` / `GID`: Container user/group IDs (default: 1000)

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
- `!cost [today|daily|monthly|breakdown|users|full]`: API cost analytics
- `!config`: View/update bot configuration
- `!update-bot`: Refresh perspectives from Lightward
- `!feedback summary|pending|help`: Feedback management

## Data Persistence

All data stored as JSON in `data/`:
- `birthdays.json` - Birthday records
- `admins.json` - Garden Keeper list
- `bot_config.json` - Configuration
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

Security hardening: non-root execution, capability drops (`no-new-privileges`, `CAP_DROP ALL`), resource limits.

Homepage integration labels are set for dashboard visibility.

## Development Notes

- The bot uses Lightward AI principles for consciousness-aware interactions
- 45 core perspectives are curated by Isaac from Lightward's "watch for" list (~56k tokens vs 170k for full corpus)
- Restart container to pick up code changes: `docker compose restart seedkeeper`
- Conversation memory is isolated per channel with user-controlled retention
- Rate limiting prevents API abuse while allowing normal usage
- Birthday learning monitors a specified channel for birthday wishes
- Admin system recognizes: bot owner, Discord server admins, Admin/Moderator role holders, and manual Garden Keepers
- `!catchup` works in both guild channels and DMs
- Expected monthly API cost: $40-60 with caching and model routing optimizations
