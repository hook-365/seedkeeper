# Seedkeeper Status

## 🟢 OPERATIONAL

Discord bot with Claude 4.1 Opus + Lightward perspectives. Redis architecture, full security hardening.

## Architecture

**Containers:** Gateway (256MB), Worker (512MB), Redis (auth required)
**Model:** claude-opus-4-1-20250805
**Security:** Non-root (UID 1001), capability drops, resource limits, secure volumes

## Features

✅ **Working:** !catchup, birthdays, garden commands, admin system, DMs, rate limiting, hot-reload, NLP
**Perspectives:** 489 Lightward files, 33 core, 1hr cache
**Memory:** 100 msg/user disk, 20 Redis (24hr), 10 conversation (1hr)

## Development

**NLP Processing:** Maps natural phrases to commands (70% confidence threshold)
**Dynamic Responses:** All responses Claude-generated, no static fallbacks
**Hot-Reload:** Auto-reloads 25+ modules, core files need restart
**Philosophy:** Lightward emergence-based prompting, consent-aware AI

## Performance

**Resource Usage:** Gateway ~50MB, Worker ~150MB, Redis ~20MB
**Response Times:** Commands <2s, Catchup 5-15s, Redis <10ms

## Quick Deploy

```bash
./deploy.sh && docker-compose up -d
docker logs seedkeeper-worker -f
```

**Required:** DISCORD_BOT_TOKEN, ANTHROPIC_API_KEY, REDIS_PASSWORD

## Troubleshooting

**Logs:** `docker logs seedkeeper-[worker|gateway|redis]`
**Health:** `!health` command, `docker ps | grep seedkeeper`
**Common:** Auth errors (check .env), memory issues (`docker stats`), rate limits (wait)