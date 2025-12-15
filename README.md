# User-Trajectory-Retriever

A comprehensive platform for recording, replaying, and annotating user trajectories for web interaction research. This system consists of a web-based annotation platform and a browser extension for data collection.

## Overview

This project is a comprehensive platform for recording, replaying, and annotating user trajectories for web interaction research. It consists of two main components:

1.  **Django Web Platform (`Platform`):** A monolithic application built with Python and the Django Web Framework. It serves as the backend for managing users, tasks, and collected data, and provides a web interface for replaying and annotating the recorded user sessions. The platform uses a SQLite database by default but is configured to support PostgreSQL for production. It includes a REST API built with Django Rest Framework for communication with the browser extension.
2.  **Chrome Browser Extension (`ManifestV3`):** A lightweight extension built with vanilla JavaScript that records user interaction data in real-time. It uses the `rrweb` library to capture DOM snapshots and interaction events. The extension communicates with the Django backend to send the recorded data and receive task information.

## Features

-   **Session Recording:** A lightweight browser extension captures detailed user interactions on any webpage, including mouse movements, clicks, scrolls, and DOM changes.
-   **Session Replay:** The web platform provides a high-fidelity replay of user sessions, accurately reproducing user actions and the state of the webpage at any given time.
-   **Task Management:** Researchers can create, assign, and manage tasks for users to complete, allowing for structured data collection in controlled studies.
-   **User Management:** A complete user system for authentication, profile management, and role-based access control (administrators, researchers, and participants).
-   **Data Annotation:** An intuitive interface for researchers to annotate key events or behaviors within a user's session, facilitating qualitative and quantitative analysis.
-   **Messaging System:** A private messaging system for administrators to communicate with users, send announcements, and provide support.
-   **Bulletin Notifications:** Automatic notifications are sent to all users via the private messaging system whenever a new bulletin is posted, ensuring timely communication.
-   **Discussion Forum:** A platform for users to ask questions, share insights, and engage in discussions related to their research and tasks, fostering a collaborative community.
-   **LLM Benchmarking & RAG Evaluation:** A comprehensive module for evaluating Large Language Models (LLMs) and Retrieval-Augmented Generation (RAG) systems. Includes features for:
    -   **Adhoc & Multi-turn Evaluation:** evaluating both single-turn and multi-turn interactions.
    -   **Vanilla LLM & RAG Pipelines:** supporting both direct LLM generation and RAG-based approaches.
    -   **LLM-as-a-Judge:** Automated evaluation using a stronger LLM to judge the quality of answers.
-   **Extension Version Management:** Administrators can manage different versions of the browser extension, view version history, and control which version is active.
-   **AJAX-powered Admin Page:** The admin page uses AJAX for filtering and sorting users and tasks, providing a seamless and responsive experience without page reloads.
-   **Advanced Data Analysis:** The admin dashboard features a comprehensive data analysis section with a variety of charts to visualize user and task data. These include:
    -   **User Demographics:** Distributions of gender, occupation, education, and proficiency levels.
    -   **User Activity:** New user signups and task creations over time.
    -   **Task Metrics:** Distributions for task familiarity, difficulty, effort, and completion times.
    -   **User Feedback:** Visualizations for user confidence, "aha moments", and reasons for task cancellation or reflection failures.
    -   **Behavioral Analysis:** Histograms and box plots for task and trial completion times, as well as dwell time on pages.
-   **API:** A REST API built with Django Rest Framework facilitates communication between the browser extension and the backend platform for data exchange and task management.

## Recent Updates

-   **Advanced Benchmarking & RAG:**
    -   **Chain of Thought (CoT):** Added support for CoT reasoning in LLM pipelines, with robust answer parsing.
    -   **Refactored Pipelines:** Unified benchmark models and pipelines for better maintainability and extensibility.
    -   **Multi-turn Improvements:** Enhanced RAG multi-turn pipelines with search result caching and improved source referencing.
    -   **UI Overhaul:** Refactored and improved the benchmarking UI, including centralized logic for configuration and session rendering.
-   **Codebase Modernization:**
    -   **Dashboard App:** The admin dashboard has been moved to a dedicated `dashboard` app for better modularity.
    -   **Centralized Logic:** Consolidated common JavaScript logic and LLM response handling to reduce duplication.
    -   **Browser Agent MCP Migration:** The browser agent has been refactored to use the Model Context Protocol (MCP) via `agentscope`, replacing the custom browser client with a standardized, more robust solution.
-   **New Features:**
    -   **Batch Operations:** Added functionality for batch deleting benchmark runs.
    -   **Data Export:** Implemented CSV export for benchmark results to facilitate offline analysis.



## System Architecture

-   **Frontend (Browser Extension):** Built as a Chrome Extension using Manifest V3 and vanilla JavaScript. It utilizes the `rrweb` library to capture DOM snapshots and interaction events.
-   **Backend (Web Platform):** A monolithic application built with Python and the Django Web Framework. It serves the user interface, manages the database (SQLite for development, configurable for production), and handles data processing and API requests.

## Prerequisites

Before you begin, ensure you have the following installed:

-   Python 3.8+
-   pip (Python package installer)
-   Conda (optional, but recommended for environment management)
-   Redis
-   PostgreSQL (optional, SQLite is used by default for development)

## Building and Running

To get the system up and running, you need to set up both the backend platform and the browser extension.

### Backend (Django Platform)

All commands should be run from the root of the project directory. The backend server is located in the `Platform/` directory.

1.  **Create a virtual environment and install dependencies:**

    **Using `conda` (Recommended):**
    ```bash
    conda create --name trajectory_env python=3.8
    conda activate trajectory_env
    pip install -r requirements.txt
    ```

    **Using `venv`:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

2.  **Configure environment variables:**
    Create a `.env` file in the `Platform/` directory by copying the `.env.example` file.
    ```bash
    cp Platform/.env.example Platform/.env
    ```
    Update the `.env` file with your configuration:
    -   **Email:** for password resets.
    -   **LLM:** `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` for benchmarking.
    -   **Search:** `SERPER_API_KEY` for RAG.
    -   **Database:** Set `DATABASE_TYPE=postgres` to use PostgreSQL (default is `sqlite`).

3.  **Apply database migrations:**
    *Note: The user prefers to run migrations manually. Notify the user when migrations are needed.*
    ```bash
    python Platform/manage.py migrate
    ```

4.  **Create a superuser:**
    ```bash
    python Platform/manage.py createsuperuser
    ```
    Follow the prompts to create an administrator account.

5.  **Start the development server:**
    ```bash
    python Platform/manage.py runserver
    ```
    The platform should now be running at `http://127.0.0.1:8000/`.

6.  **Running in Production (with Gunicorn):**
    For a more robust setup suitable for production, you can use Gunicorn. Make sure you have installed all the dependencies from `requirements.txt`.
    ```bash
    cd Platform
    gunicorn --config gunicorn.conf.py annotation_platform.wsgi
    ```
    This will start the server using the configuration specified in `gunicorn.conf.py`.

### Frontend (Chrome Extension)

The extension is located in the `ManifestV3/` directory.

1.  Open Google Chrome and navigate to `chrome://extensions`.
2.  Enable **Developer mode** using the toggle in the top-right corner.
3.  Click the **Load unpacked** button.
4.  Select the `ManifestV3` folder.
5.  The extension should now be installed and active in your browser.

## Usage

1.  Ensure the Django backend server is running.
2.  Make sure the Chrome extension is installed and enabled.
3.  Navigate to the web platform (e.g., `http://127.0.0.1:8000/`) to sign up and log in.
4.  The extension will automatically start recording user trajectories on specified websites once a task is initiated from the platform.
5.  After completing a task, the recorded data can be viewed and replayed from the user's dashboard on the web platform.

## Privacy and Incognito Mode

For the best experience and to ensure your privacy, we recommend using the extension in **Incognito Mode**. This helps isolate the recording session and prevents interference from other browser extensions or cached data.

**We respect your privacy.** The recording script, powered by `rrweb`, is configured to **exclude password inputs** and other sensitive fields. However, we still recommend that you avoid interacting with personal or sensitive information while the extension is active.

## Disabling the Extension When Not in Use

To protect your privacy, we strongly recommend that you **disable or uninstall the extension when you are not actively working on a task**.

You can manage the extension by following these steps:

1.  Open Google Chrome and navigate to `chrome://extensions`.
2.  Locate the **User-Trajectory-Retriever** extension.
3.  **To temporarily disable it** (recommended between tasks), toggle the switch to the off position.
4.  **To permanently remove it**, click the **Remove** button.

## Directory Structure

```
.
├── ManifestV3/       # Source code for the Chrome browser extension
├── Platform/         # Source code for the Django web platform
│   ├── annotation_platform/ # Core Django project configuration
│   ├── benchmark/    # LLM benchmarking and RAG evaluation app
│   ├── dashboard/    # Admin dashboard and data analysis
│   ├── discussion/   # Discussion forum app
│   ├── media/        # User uploaded content
│   ├── msg_system/   # Private messaging system app
│   ├── task_manager/ # Task management app
│   └── user_system/  # User management app
├── requirements.txt  # Python dependencies for the platform
└── README.md         # This file
```

## TODO

- [ ] Implement a questionnaire-style annotation interface (frontend and backend).
- [ ] Add cross-browser support for Firefox and Safari.
- [ ] Add support for iframes.

## Contributing

Contributions are welcome! If you'd like to contribute, please fork the repository and create a pull request. You can also open an issue if you have any suggestions or find any bugs.

## License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.

## Contact

If you have any questions, please feel free to contact me via [stevenzhangx@163.com](mailto:stevenzhangx@163.com) or open an issue on GitHub.

## Acknowledgement

This toolkit is built based on the prototype systems that were used in several previous work:
* [Mao, Jiaxin, et al. "When does relevance mean usefulness and user satisfaction in web search?" Proceedings of the 39th International ACM SIGIR conference on Research and Development in Information Retrieval. 2016.](http://www.thuir.org/group/~YQLiu/publications/sigir2016Mao.pdf)
* [Wu, Zhijing, et al. "The influence of image search intents on user behavior and satisfaction." Proceedings of the Twelfth ACM International Conference on Web Search and Data Mining. 2019.](http://www.thuir.org/group/~YQLiu/publications/WSDM19Wu.pdf)
* [Zhang, Fan, et al. "Models versus satisfaction: Towards a better understanding of evaluation metrics." Proceedings of the 43rd International ACM SIGIR Conference on Research and Development in Information Retrieval. 2020.](https://static.aminer.cn/upload/pdf/1982/1327/2004/5f0277e911dc830562231df7_0.pdf)
* [Zhang, Fan, et al. "Cascade or recency: Constructing better evaluation metrics for session search." Proceedings of the 43rd International ACM SIGIR Conference on Research and Development in Information Retrieval. 2020.](http://www.thuir.cn/group/~mzhang/publications/SIGIR2020-ZhangFan1.pdf)
* [Chen, Jia, et al. "Towards a Better Understanding of Query Reformulation Behavior in Web Search." Proceedings of the Web Conference 2021.](https://dl.acm.org/doi/10.1145/3442381.3449916)

We thank the authors for their great work.