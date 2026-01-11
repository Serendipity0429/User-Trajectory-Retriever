# User-Trajectory-Retriever

A research platform for recording, replaying, and annotating user web trajectories. Built for web interaction research with optional LLM evaluation capabilities.

## Overview

This project enables researchers to collect and analyze how users interact with websites. It consists of:

- **Django Web Platform** (`Platform/`): Backend for user management, task orchestration, session replay, and annotation
- **Chrome Extension** (`ManifestV3/`): Records user interactions in real-time using [rrweb](https://github.com/rrweb-io/rrweb)

## Features

### Core: Trajectory Collection
- **Session Recording**: Captures mouse movements, clicks, scrolls, keyboard input, and DOM changes
- **High-Fidelity Replay**: Reproduces recorded sessions with timeline controls
- **Task Management**: Create and assign research tasks with structured workflows
- **Data Annotation**: Mark and annotate key events within sessions

### Platform
- **User System**: Authentication with role-based access (admin, researcher, participant)
- **Discussion Forum**: Community space for research discussions
- **Private Messaging**: Direct communication between users and admins
- **Admin Dashboard**: Analytics and data visualization

### Optional: LLM Benchmarking
- Multi-turn evaluation pipelines (Vanilla LLM, RAG, Agent-based)
- LLM-as-a-Judge automated evaluation
- Real-time streaming with trace visualization

## Prerequisites

- Python 3.8+
- Redis (required for benchmarking features)
- Google Chrome (for the extension)
- Node.js 18+ (only for agent pipelines)

## Quick Start

### 1. Setup Environment

```bash
# Using conda (recommended)
conda create --name trajectory_env python=3.10
conda activate trajectory_env
pip install -r requirements.txt

# Or using venv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp Platform/.env.example Platform/.env
# Edit Platform/.env with your settings
```

Key settings in `.env`:
- `DJANGO_SECRET_KEY`: Required for Django
- `LLM_*`: For benchmarking features
- `SERPER_API_KEY`: For RAG pipeline web search

### 3. Initialize Database

```bash
python Platform/manage.py migrate
python Platform/manage.py createsuperuser
```

### 4. Run

```bash
python Platform/manage.py runserver
```

Visit `http://127.0.0.1:8000/`

### 5. Install Chrome Extension

1. Navigate to `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked** and select `ManifestV3/`

## Usage

1. Log in to the platform and create/start a task
2. The extension automatically records your browsing session
3. Complete the task and end recording via the extension popup
4. View replay and add annotations in the platform

## Directory Structure

```
├── ManifestV3/           # Chrome extension (rrweb-based recording)
├── Platform/             # Django backend
│   ├── task_manager/     # Trajectory and task management
│   ├── user_system/      # Authentication and profiles
│   ├── benchmark/        # LLM evaluation pipelines
│   ├── dashboard/        # Admin analytics
│   ├── discussion/       # Forum system
│   └── msg_system/       # Private messaging
├── requirements.txt
└── README.md
```

## Privacy

- Password inputs are excluded from recording
- Use incognito mode for session isolation
- Disable the extension when not recording

## Development

```bash
# Run tests
python Platform/manage.py test task_manager

# Production deployment
cd Platform && gunicorn --config gunicorn.conf.py annotation_platform.wsgi
```

## Contributing

Contributions welcome! Fork the repo, create a feature branch, and submit a pull request.

## License

MIT License - see [LICENSE](./LICENSE)

## Contact

- Email: [stevenzhangx@163.com](mailto:stevenzhangx@163.com)
- GitHub Issues

## Acknowledgements

Built on prototypes from prior research on user behavior and search evaluation:
- [Mao et al., SIGIR 2016](http://www.thuir.org/group/~YQLiu/publications/sigir2016Mao.pdf)
- [Wu et al., WSDM 2019](http://www.thuir.org/group/~YQLiu/publications/WSDM19Wu.pdf)
- [Zhang et al., SIGIR 2020](https://static.aminer.cn/upload/pdf/1982/1327/2004/5f0277e911dc830562231df7_0.pdf)
- [Chen et al., WWW 2021](https://dl.acm.org/doi/10.1145/3442381.3449916)
