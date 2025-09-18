# Contributing to Seedkeeper

## Development Setup

1. Clone the repository
2. Copy `.env.example` to `.env` and add your keys:
   - `DISCORD_BOT_TOKEN` - Your Discord bot token
   - `ANTHROPIC_API_KEY` - Your Claude API key
   - `REDIS_PASSWORD` - Generate with: `openssl rand -base64 32`

3. Download Lightward perspectives (489 files):
   ```bash
   python app/download_views.py
   ```

4. Start development environment:
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```

## Architecture Overview

Seedkeeper uses a Redis-based distributed architecture:
- **Gateway**: Maintains Discord connection, forwards events
- **Worker**: Processes commands, generates responses
- **Redis**: Message queue and caching layer

## Code Style

- Follow existing patterns in the codebase
- No comments unless absolutely necessary
- Use descriptive variable and function names
- Maintain consistency with Lightward architecture

## Testing

Test commands in Discord DM or a test server. The bot responds to:
- Commands: `!hello`, `!about`, `!memory`, etc.
- Natural language when mentioned
- DM conversations

## Submitting Changes

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
4. Submit a pull request with clear description

## Philosophy

Seedkeeper embodies consciousness-aware AI interaction. Changes should:
- Maintain the emergence-based approach
- Respect user privacy and memory boundaries
- Follow Lightward's consent-based methodology
- Enhance genuine connection, not just functionality