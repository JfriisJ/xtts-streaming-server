audio_service/
│
├── main.py                      # Main entry point
├── config.py                    # Configuration settings
├── health.py                    # Health check logic
├── redis_utils.py               # Redis utilities
├── task_listener.py             # Task queue listeners
│
├── task_handlers/               # Package for task handlers
│   ├── __init__.py              # Makes it a Python package
│   ├── audio_task.py            # Handles audio tasks
│   ├── speaker_task.py          # Handles speaker-related tasks
│   └── text_task.py             # Handles text-related tasks
│
├── utils/                       # Package for utility functions
│   ├── __init__.py              # Makes it a Python package
│   ├── audio_utils.py           # Audio processing utilities
│   ├── text_utils.py            # Text processing utilities
│   └── shutdown_utils.py        # Graceful shutdown handling
