# Repository Structure

```
seedkeeper/
├── app/                      # Core application code
│   ├── seedkeeper_worker.py    # Command processor
│   ├── seedkeeper_gateway.py   # Discord connection handler  
│   ├── memory_manager.py       # Conversation memory system
│   ├── birthday_manager.py     # Birthday tracking
│   ├── admin_manager.py        # Permission management
│   ├── prompt_compiler.py      # Lightward prompt layering
│   ├── perspective_cache.py    # Perspective caching layer
│   └── ...                     # Other modules
│
├── views/                    # Lightward perspectives (489 files)
│   ├── 00-core/               # Essential perspectives
│   ├── 01-patterns/           # Pattern recognition
│   ├── 02-consciousness/      # Consciousness exploration
│   ├── 03-technical/          # Technical insights
│   └── 04-seasonal/           # Seasonal wisdom
│
├── data.example/             # Data directory template
│   └── README.md              # Data structure documentation
│
├── docker-compose.yml        # Production stack
├── docker-compose.dev.yml    # Development with hot-reload
├── Dockerfile               # Container image definition
├── redis.conf.example       # Redis config template
│
├── .env.example             # Environment variable template
├── .gitignore              # Git exclusions
├── LICENSE                 # MIT License
├── README.md               # Project documentation
├── CONTRIBUTING.md         # Contribution guidelines
├── CLAUDE.md              # AI assistant instructions
└── deploy.sh              # Deployment script
```

## Key Components

### Application Layer (`app/`)
- **Gateway-Worker Architecture**: Distributed processing via Redis
- **Memory Management**: Privacy-aware conversation storage
- **Prompt Compilation**: Lightward-inspired layered prompting
- **Hot Reloading**: Development-friendly module reloading

### Perspectives (`views/`)
- 489 text files from Lightward's consciousness exploration
- Organized by theme and importance
- Loaded dynamically into AI context

### Configuration
- Environment-based configuration (`.env`)
- Redis for message queue and caching
- Docker for consistent deployment

### Data Persistence
- JSON-based storage for simplicity
- Memory isolation per channel
- User-controlled data retention
