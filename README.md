A comprehensive platform for recording, replaying, and annotating user trajectories for web interaction research. This system consists of a web-based annotation platform and a browser extension for data collection.

## Overview

User-Trajectory-Retriever is a powerful tool designed for researchers studying user behavior on the web. It allows for the detailed recording of user interactions—such as mouse movements, clicks, and scrolls—during specific tasks. The collected data can then be visualized, replayed, and annotated through a dedicated web platform, providing valuable insights into user engagement and decision-making processes.

The system is composed of two main parts:
1.  **A Chrome Browser Extension (`ManifestV3`):** Records user interaction data in real-time using the `rrweb` library.
2.  **A Django Web Platform (`Platform`):** Manages users, tasks, and collected data, and provides an interface for replaying and annotating the recorded user sessions.

## Features

- **Session Recording:** A lightweight browser extension captures detailed user interactions on any webpage.
- **Session Replay:** The web platform provides a high-fidelity replay of user sessions, accurately reproducing mouse movements, clicks, and DOM changes.
- **Task Management:** Researchers can create and manage tasks for users to complete.
- **User Management:** A complete user system for authentication and profile management.
- **Data Annotation:** An interface for researchers to annotate key events or behaviors within a user's session.
- **Messaging System:** A private messaging system for administrators to communicate with users.
- **Bulletin Notifications:** Automatic notifications are sent to all users via the private messaging system whenever a new bulletin is posted.
- **Discussion Forum:** A platform for users to ask questions, share insights, and engage in discussions related to their research and tasks.
- **Extension Version Management:** Admins can add new extension versions, view version history, and revert to the latest version.
- **AJAX-powered Admin Page:** The admin page now uses AJAX for filtering and sorting users and tasks, providing a smoother experience without page reloads.

## Recent Updates

- **UI Modernization and Responsiveness:** The entire user interface has been overhauled with a more modern aesthetic, improved layouts, and significantly enhanced responsiveness for mobile and tablet devices.
- **Enhanced Admin Dashboard:** The administrator dashboard is now more powerful and user-friendly, featuring collapsible filter sections and dropdown menus for a cleaner experience.
- **Benchmarking as Django Commands:** The performance benchmarking scripts have been refactored into Django management commands (`pressure_test` and `llm_judge_benchmark`) for easier and more integrated execution.
- **UI Enhancements:** The user interface has been updated to include a new messaging dropdown in the navigation bar, providing easy access to unread messages.
- **Messaging System:** A new private messaging system has been integrated, replacing the previous reliance on Django's built-in messaging framework.
- **Discussion Forum:** A new discussion forum has been added to the platform, allowing users to interact with each other, ask questions, and share their findings.
- **UI Enhancements:** The user interface has been updated for a more modern look and feel, including the addition of a dark mode.
- **Performance Improvements:** The rrweb player is now lazy-loaded, improving the initial page load time.

## System Architecture

- **Frontend (Browser Extension):** Built as a Chrome Extension using Manifest V3 and vanilla JavaScript. It utilizes the `rrweb` library to capture DOM snapshots and interaction events.
- **Backend (Web Platform):** A monolithic application built with Python and the Django Web Framework. It serves the user interface, manages the database, and handles data processing.

## Prerequisites

Before you begin, ensure you have the following installed:
- Python 3.8+
- pip (Python package installer)
- virtualenv (optional, but recommended)
- Redis

## Building and Running

To get the system up and running, you need to set up both the backend platform and the browser extension.

### Backend (Django Platform)

All commands should be run from the root of the project directory.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/User-Trajectory-Retriever.git
    cd User-Trajectory-Retriever
    ```

2.  **Create a virtual environment and install dependencies:**
    It is recommended to use a virtual environment.
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

3.  **Configure environment variables:**
    ```bash
    cp Platform/.env.example Platform/.env
    ```
    Open the `Platform/.env` file and add your email server configuration.

4.  **Apply database migrations:**
    ```bash
    python Platform/manage.py migrate
    ```

5.  **Create a superuser:**
    ```bash
    python Platform/manage.py createsuperuser
    ```
    Follow the prompts to create an administrator account.

6.  **Start the development server:**
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
4.  Select the `ManifestV3` folder from the cloned repository.
5.  The extension should now be installed and active in your browser.

## Usage

1.  Ensure the Django backend server is running.
2.  Make sure the Chrome extension is installed and enabled.
3.  Navigate to the web platform (e.g., `http://127.0.0.1:8000/`) to sign up and log in.
4.  The extension will automatically start recording user trajectories on specified websites once a task is initiated from the platform.
5.  After completing a task, the recorded data can be viewed and replayed from the user's dashboard on the web platform.

## Directory Structure

```
.
├── ManifestV3/       # Source code for the Chrome browser extension
├── Platform/         # Source code for the Django web platform
│   ├── discussion/   # Discussion forum app
│   ├── msg_system/   # Private messaging system app
│   ├── task_manager/ # Task management app
│   └── user_system/  # User management app
├── requirements.txt  # Python dependencies for the platform
└── README.md         # This file
```

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue if you have any suggestions or find any bugs.

## License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.

## Contact
If you have any questions, please feel free to contact me via [stevenzhangx@163.com]() or open an issue.

## Acknowledgement
This toolkit is built based on the prototype systems that were used in several previous work: 
* [Mao, Jiaxin, et al. "When does relevance mean usefulness and user satisfaction in web search?" Proceedings of the 39th International ACM SIGIR conference on Research and Development in Information Retrieval. 2016.](http://www.thuir.org/group/~YQLiu/publications/sigir2016Mao.pdf)
* [Wu, Zhijing, et al. "The influence of image search intents on user behavior and satisfaction." Proceedings of the Twelfth ACM International Conference on Web Search and Data Mining. 2019.](http://www.thuir.org/group/~YQLiu/publications/WSDM19Wu.pdf)
* [Zhang, Fan, et al. "Models versus satisfaction: Towards a better understanding of evaluation metrics." Proceedings of the 43rd International ACM SIGIR Conference on Research and Development in Information Retrieval. 2020.](https://static.aminer.cn/upload/pdf/1982/1327/2004/5f0277e911dc830562231df7_0.pdf)
* [Zhang, Fan, et al. "Cascade or recency: Constructing better evaluation metrics for session search." Proceedings of the 43rd International ACM SIGIR Conference on Research and Development in Information Retrieval. 2020.](http://www.thuir.cn/group/~mzhang/publications/SIGIR2020-ZhangFan1.pdf)
* [Chen, Jia, et al. "Towards a Better Understanding of Query Reformulation Behavior in Web Search." Proceedings of the Web Conference 2021.](https://dl.acm.org/doi/10.1145/3442381.3449916)

We thank the authors for their great work.