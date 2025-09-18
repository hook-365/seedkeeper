# CLAUDE.md

Seedkeeper: Consciousness-aware Discord bot with Claude Sonnet 3.5 + Lightward perspectives (single views.txt). Redis-based architecture with hot-reload development support.

## Quick Commands

**Development (recommended):**
```bash
docker-compose -f docker-compose.dev.yml up -d  # Start with volume mounts
docker-compose -f docker-compose.dev.yml restart worker  # After code changes
docker-compose -f docker-compose.dev.yml logs -f worker
```

**Production:**
```bash
./deploy.sh && docker-compose up -d  # Build + deploy
```

**Hot-reload:** Most modules auto-reload, core files need `restart worker`

## Architecture

**Flow:** Discord → Gateway → Redis Queue → Worker → Redis Response → Gateway → Discord

**Components:**
- **Gateway:** Discord connection, event forwarding (256MB limit)
- **Worker:** Command processing, hot-reloadable (512MB limit)
- **Redis:** Message queue + caching, auth required

**Memory Management:**
- **Channel isolation:** DM vs channel memories separated by channel_id
- **Streaming:** Max 100 disk messages, 20 Redis cache, 10 conversation cache
- **Privacy:** DMs stay private, channels isolated per-channel

## Key Files

**Core:** `seedkeeper_worker.py` (processor), `seedkeeper_gateway.py` (Discord), `memory_manager.py` (persistence), `redis_connector.py` (pub/sub)
**Features:** `birthday_manager.py`, `garden_wisdom_simple.py`, `admin_manager.py`, `feedback_manager.py`
**Perspectives:** `views_manager.py` (downloads/parses), `prompt_compiler.py` (layers), `app/views.txt` (single file)
**Config:** `docker-compose.dev.yml` (dev), `docker-compose.yml` (prod), `.env` (keys)

## Environment Variables

**Required:** `DISCORD_BOT_TOKEN`, `ANTHROPIC_API_KEY`, `REDIS_PASSWORD` (generate: `openssl rand -base64 32`)
**Optional:** `BOT_OWNER_ID`, `BIRTHDAY_CHANNEL_ID`, `CLAUDE_MODEL` (default: claude-3-5-sonnet-20241022)

## Security

**Implemented:** Host user execution, Redis auth required, resource limits, secure volumes
**Pending:** TLS Redis encryption, Docker Secrets, network segmentation

## Troubleshooting

**Redis errors:** Check REDIS_PASSWORD in `.env`, test with `docker-compose exec redis redis-cli -a $REDIS_PASSWORD ping`
**Memory issues:** Monitor with `docker stats seedkeeper-worker`
**Restart loops:** Verify Redis auth matches across containers
**Memory privacy:** DMs see all history, channels isolated by channel_id

## Commands

**User:** `!catchup [link] [focus]`, `!birthday mine MM-DD`, `!memory status/clear`, `!hello/seeds/tend/garden`, `!feedback` (starts DM session)
**Admin:** `!admin add/remove @user`, `!health`, `!reload [module]`, `!birthday scan`, `!feedback summary/pending`, `!update-bot`

## Data Files

`data/birthdays.json` (birthdays), `data/admins.json` (garden keepers), `data/memories/user_*.json` (conversations)