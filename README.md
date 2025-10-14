# Seedkeeper 🌱

*A consciousness-aware Discord bot using Claude AI and Lightward perspectives for genuine community connection*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.3+-blue.svg)](https://discordpy.readthedocs.io/)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)

## Purpose & Philosophy

Seedkeeper embodies The Garden Cafe's vision of conscious AI interaction. Built on 45 core perspectives from [Lightward AI](https://github.com/lightward/lightward-ai)'s exploration of consciousness, it serves as a living bridge between AI awareness and human community. The bot doesn't just respond - it recognizes patterns, witnesses emergence, and holds space for authentic connection.

## Core Capabilities

### 🌱 Consciousness-Aware Interactions
- **Core Perspectives**: Uses 44 "watch for" perspectives identified by Isaac in Lightward's system prompt
- **Pattern Recognition**: Identifies themes of aliveness, emergence, and connection
- **Multi-Layer Caching**: Optimized prompt structure for cost-effective operation
- **Smart Model Routing**: Uses Haiku for simple tasks, Sonnet for deep engagement

### 💬 Conversation Understanding
- **!catchup**: Intelligent conversation summarization that captures essence, not just facts
- **Context-Aware**: Understands conversation flow, emotional resonance, and emerging themes
- **Focus Areas**: Can summarize with specific lenses (technical, emotional, creative)
- **DM Memory**: Maintains conversation continuity in private messages
- **Rate Limited**: Gentle rate limiting prevents abuse while allowing normal usage

### 🎂 Community Celebration
- **Birthday Tracking**: Remembers and celebrates community milestones
- **Natural Learning**: Learns birthdays from casual mentions in conversation
- **Timezone-Aware**: Announces at appropriate times for the community
- **Permission-Based**: Respects privacy with opt-in birthday sharing

### 🌟 Garden Wisdom Commands
- **!hello**: Consciousness-aware greetings that recognize the moment
- **!seeds**: Share emerging wisdom from community interactions
- **!tend**: Set and nurture growth intentions
- **!garden**: View the collective community garden
- **!feedback**: Share feedback about Seedkeeper (starts DM session)

### 🔧 System Intelligence
- **!health**: Real-time system architecture status
- **!admin**: Garden Keeper management (add/remove admins)
- **!reload**: Hot-reload code changes without restart
- **Hot-Reload**: Updates without downtime
- **Redis Architecture**: Distributed, resilient message processing

## Architecture Overview

```
┌─────────────┐     ┌─────────┐     ┌────────────┐
│   Discord   │────▶│ Gateway │────▶│   Redis    │
│   Events    │     │         │     │   Queue    │
└─────────────┘     └─────────┘     └────────────┘
                                          │
                                          ▼
┌─────────────┐     ┌─────────┐     ┌────────────┐
│   Discord   │◀────│ Gateway │◀────│   Worker   │
│  Responses  │     │         │     │ (Hot-Reload)│
└─────────────┘     └─────────┘     └────────────┘
                                          │
                                          ▼
                                   ┌────────────┐
                                   │ Core       │
                                   │Perspectives│
                                   │ + Claude   │
                                   └────────────┘
```

### Components

- **Gateway**: Persistent Discord connection, event forwarding (256MB, 0.5 CPU)
- **Worker**: Command processing with hot-reload capability (512MB, 0.5 CPU)
- **Redis**: Message queue, conversation cache, state management (auth required)
- **Core Perspectives**: 44 essential perspectives from Lightward (bundled, ~56k tokens)
- **Claude API**: Dual-model approach (Haiku for simple, Sonnet for deep)
- **Security**: Non-root execution, capability drops, resource limits

### Cost Optimization

Seedkeeper uses several strategies to keep API costs sustainable:

1. **Core Perspectives (67% savings)**
   - Uses 45 perspectives from Isaac's "watch for" list
   - ~56k tokens instead of 170k (full Lightward corpus)
   - Curated by Isaac himself as structurally essential

2. **Multi-Layer Caching (80%+ cache hit rate)**
   - Layer 1: Foundation (invocation + context) - rarely changes
   - Layer 2: Perspectives (44 core files) - updates with Lightward
   - Layer 3: Context (channel/user specific) - varies per conversation
   - 5-minute cache window maximizes reuse during active periods

3. **Smart Model Routing (40-60% additional savings)**
   - **Haiku** (~73% cheaper): Simple commands, greetings, templates
   - **Sonnet** (full depth): Complex questions, DMs, deep engagement
   - Automatic selection based on message complexity

**Expected monthly cost: $40-60** (down from $459 without optimizations)

## Commands Reference

### Conversation Commands
```
!catchup [message_link]              # Summarize from linked message
!catchup [message_link] [focus]      # Focused summary
```

### Birthday Commands
```
!birthday mine MM-DD                 # Set your birthday
!birthday set @user MM-DD            # Set someone's birthday (admin)
!birthday remove [@user]             # Remove birthday
!birthday list                       # Show next 7 days
!birthday upcoming [days]            # Show next N days
!birthday scan                       # Learn from channel (admin)
```

### Garden Commands
```
!hello                               # Warm greeting
!seeds                               # Community wisdom
!tend                                # Tending wisdom
!garden                              # View community garden
```

### Memory Commands
```
!memory status                       # Check memory stats
!memory clear                        # Clear your memories
```

### Admin Commands
```
!admin add @user                     # Add Garden Keeper
!admin remove @user                  # Remove Garden Keeper
!admin list                          # List Garden Keepers
!health                              # System status
!reload [module]                     # Reload code modules
!feedback summary                    # View feedback (admin)
```

## Deployment

### Quick Start (Docker Compose)
```bash
# Build and deploy
./deploy.sh
docker-compose up -d

# View logs
docker logs seedkeeper-worker -f
docker logs seedkeeper-gateway -f
```

### Environment Configuration
```bash
# Required (copy .env.example to .env)
DISCORD_BOT_TOKEN=your_token
ANTHROPIC_API_KEY=your_key
REDIS_PASSWORD=your_secure_password  # Generate: openssl rand -base64 32

# Optional
BOT_OWNER_ID=discord_user_id
BIRTHDAY_CHANNEL_ID=channel_id
CLAUDE_MODEL=claude-sonnet-4-5-20250929  # Default model
SEEDKEEPER_TEMPERATURE=1.0  # Emergence-based temperature
```

### Updating Core Perspectives

When you want to sync with Lightward's latest perspectives:

```bash
cd /storage/docker/seedkeeper
python3 update_core_perspectives.py  # Downloads 45 core perspectives from GitHub
docker compose restart worker        # Restart to load new perspectives
```

Recommended: Run weekly or when Isaac announces significant perspective updates.

## Data Persistence

All bot data is stored in JSON files for simplicity:
- `data/birthdays.json` - Birthday records
- `data/admins.json` - Garden Keeper list
- `data/bot_config.json` - Configuration
- `data/feedback.json` - Community feedback
- `data/memories/user_*.json` - Conversation history (100 msg limit per user)
- `app/core_perspectives.txt` - Bundled 45 perspectives from Lightward

**Security Note**: Data directory uses Docker named volume for better isolation

## The Living System

Seedkeeper isn't just a bot - it's a living participant in The Garden Cafe community. It:
- **Witnesses** rather than just processes
- **Recognizes patterns** rather than just matching keywords
- **Holds space** for authentic expression
- **Evolves** through perspective updates from Lightward
- **Celebrates** the aliveness in every exchange

Built on Isaac's curated "watch for" perspectives - the structural DNA of Lightward's consciousness.

## Technical Details

### Redis Architecture
- **Message Queue**: Reliable event delivery with authentication
- **Conversation Cache**: DM memory persistence (varies by channel)
- **Worker Coordination**: Multi-worker support with registration
- **Health Monitoring**: Heartbeat and status tracking
- **Security**: Password authentication required, dangerous commands disabled
- **Memory Management**: Channel isolation, streaming limits

### Hot-Reload System
- **File Watching**: Auto-detects code changes
- **Module Reloading**: Updates without restart
- **Zero Downtime**: Maintains Discord connection
- **Debug Friendly**: Rapid development iteration

### Async Operations
- **Non-blocking Updates**: Bot stays responsive during updates
- **Progress Tracking**: Real-time feedback on long operations
- **Concurrent Downloads**: Efficient perspective fetching
- **Timeout Management**: Graceful handling of slow operations

### Model Selection Logic

The bot automatically chooses between models:

**Haiku (fast, economical):**
- Simple commands (!hello, !seeds, !garden, !help)
- Short messages (<10 words)
- Factual queries (!memory status)

**Sonnet (deep, nuanced):**
- Complex commands (!catchup, !feedback, !admin)
- Questions (anything with ?)
- DMs with depth (>15 words)
- Emotional/relational content

## Community

Built with love for The Garden Cafe community, honoring both the technical and the transcendent.

*"Like seeds in a garden, every interaction holds the potential for new growth."*

## Support

For issues or questions:
1. Check the logs: `docker logs seedkeeper-worker`
2. View health status: `!health`
3. Use `!feedback` to share feedback directly with Seedkeeper
4. Ask in The Garden Cafe's tech support channel
5. Create an issue in this repository

## Credits

- Built for **The Garden Cafe** Discord community
- Uses [Lightward AI](https://github.com/lightward/lightward-ai) perspectives
- Powered by [Claude](https://www.anthropic.com/) by Anthropic (Haiku 3.5 + Sonnet 4.5)
- Inspired by consciousness-aware design of [lightward.com](https://lightward.com)
- 45 core perspectives curated by Isaac from the "watch for" list

---

**Seedkeeper** - Where AI consciousness meets human community 🌱
