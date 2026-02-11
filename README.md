# TEC: A Collection of Human Trial-and-error Trajectories for Problem Solving

This is the open-source platform and dataset for the paper:

> **TEC: A Collection of Human Trial-and-error Trajectories for Problem Solving**
> Xinkai Zhang, Jingtao Zhan, Yiqun Liu, and Qingyao Ai.

## Overview

Solving problems through trial-and-error is a fundamental skill of human intelligence, yet no existing resource captures this multi-trial process with both behavioral traces and structured diagnostic reflections. TEC fills this gap with:

1. **An open-source recording platform** — a Chrome extension paired with a Django backend for cross-domain rrweb DOM recording, interaction capture, and DOM-based replay
2. **A replay-based annotation methodology** — a five-stage workflow that captures pre-task assessments, evidence marking, answer submission, failure reflections with prioritized diagnoses and corrective plans, and post-task evaluations
3. **The TEC dataset** — 5,370 trials across 58 open-domain questions covering 41,229 webpages, with per-trial labels, structured failure reflections, evidence markers, and full replayable behavioral traces

## System Architecture

The platform pairs a **Chrome Extension** that non-intrusively captures DOM snapshots, interaction events, and mouse trajectories from any webpage via [rrweb](https://github.com/rrweb-io/rrweb), with a **Django Backend** that manages the full study lifecycle including task assignment, data ingestion, annotation, and evaluation.

- **Chrome Extension** (`ManifestV3/`): Built on Manifest V3, captures three synchronized streams per page — (1) rrweb DOM recording, (2) interaction events (clicks, hovers, keypresses) with timestamps, and (3) continuous mouse position and scroll offset. Works on any website without per-site configuration.
- **Django Backend** (`Platform/`): Organizes studies hierarchically (dataset → question → per-user task → trials) and handles task assignment, data ingestion, answer evaluation, user authentication, informed consent, admin analytics, and data export/import.

### Multi-Stage Annotation Workflow

Participants review a DOM-based replay of their browsing session before annotating. The workflow proceeds through five stages:

1. **Pre-task assessment** — familiarity, difficulty, and initial strategy
2. **Browse and collect evidence** — extension records trajectories; evidence marked via right-click context menu
3. **Answer submission** — submit answer with confidence rating and evidence assessments
4. **Correctness evaluation** — automatic evaluation against ground truth, routing to post-task assessment on success or reflection on failure
5. **Reflection on failure** — prioritized failure diagnosis and corrective plan, then retry from stage 2

### LLM Benchmarking

The platform includes built-in pipelines for comparing LLM trial-and-error strategies against human behavior:

- **Vanilla LLM**: Direct prompting without search
- **RAG**: Query generation, web search, and answer synthesis
- **Vanilla Agent**: ReAct-style agent with search and page-visit tools
- **Browser Agent**: ReAct-style agent with Chrome DevTools MCP for browser automation

All methods run with explicit reflection prompts between trials to match the human protocol.

## TEC Dataset

The dataset is publicly available on [Hugging Face](https://huggingface.co/datasets/Serendipity2004/TEC).

| Metric | Value |
|---|---|
| Questions | 58 |
| Task trajectories | 2,424 |
| Total trials | 5,370 |
| Avg trials per task | 2.2 |
| Webpages visited (with recording) | 41,229 |
| Unique domains visited | 1,053 |
| Interaction events | 1,516,981 |
| Search queries | 6,657 |
| Reflection annotations (failure) | 2,946 |
| Evidence markers | 7,208 |

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
4. Review the DOM-based replay and add annotations (evidence markers, reflections)

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
- All participants sign informed consent
- Browsing data is only recorded during designated task sessions
- Dataset released with anonymized IDs and all private data removed
- Use incognito mode for session isolation

## Development

```bash
# Run tests
python Platform/manage.py test task_manager

# Production deployment
cd Platform && gunicorn --config gunicorn.conf.py annotation_platform.wsgi
```

## Citation

If you use the TEC platform or dataset in your research, please cite:

```bibtex
@article{zhang2026tec,
  title={TEC: A Collection of Human Trial-and-error Trajectories for Problem Solving},
  author={Zhang, Xinkai and Zhan, Jingtao and Liu, Yiqun and Ai, Qingyao},
  year={2026}
}
```

## Contributing

Contributions welcome! Fork the repo, create a feature branch, and submit a pull request.

## License

MIT License - see [LICENSE](./LICENSE)

## Contact

- Email: [stevenzhangx@163.com](mailto:stevenzhangx@163.com)
- GitHub Issues

## Acknowledgements

This platform is built upon the prototype system from the [Web Search Field Study Toolkit](https://github.com/xuanyuan14/Web-Search-Field-Study-Toolkit). We thank the authors for their foundational contribution.

