# Data Directory Template

This directory shows the structure for Seedkeeper's persistent data.
Copy this to `data/` and the bot will initialize the files as needed.

## Directory Structure

```
data/
├── memories/          # User conversation memories (created automatically)
├── birthdays.json     # Birthday tracking (created on first birthday set)
├── admins.json        # Garden Keeper permissions (created on first admin add)
├── bot_config.json    # Runtime configuration (created on startup)
├── model_voice.json   # AI-generated invocation/benediction (created on startup)
├── team_letters.txt   # Messages from team to AI (optional)
└── core_perspectives.json  # Tracking of essential perspectives (created on startup)
```

All files are created automatically when needed. Do not commit actual data files to git.