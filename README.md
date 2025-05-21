# News Aggregator

This project is a news aggregator application designed to discover, analyze, and present news from various sources.

## Phases

1.  ~~**Core Infrastructure & Basic RSS Ingestion**~~
2.  **Advanced Story Discovery & Initial Processing**
3.  **Enhanced Source Acquisition & Content Retrieval**
4.  **Evaluation & Validation Pipeline**
5.  **Frontend Application & User Personalization**
6.  **Refinement, Scaling, and Deployment**

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

*   Python 3.8+
*   MongoDB instance (running locally or accessible remotely)
*   Git

#### MongoDB Setup

This project requires a running MongoDB instance. You can:
*   **Install MongoDB Locally:** Download and install MongoDB Community Server from the [official MongoDB website](https://www.mongodb.com/try/download/community). Follow the installation instructions for your operating system.
*   **Use a Cloud-Hosted MongoDB Service:** Services like MongoDB Atlas offer free tiers that are suitable for development.
*   **Run MongoDB with Docker:** If you have Docker installed, you can run MongoDB in a container:
    ```bash
    docker run -d -p 27017:27017 --name news-aggregator-mongo mongo:latest
    ```
    This command starts a MongoDB instance named `news-aggregator-mongo` and maps port `27017` on your host to the container's port `27017`.

Ensure your MongoDB instance is running before starting the application.

### Installation & Setup

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/marianbasti/news-aggregator
    cd news-aggregator
    ```

2.  **Create and activate a virtual environment:**

    *   On macOS and Linux:
        ```bash
        python3 -m venv .venv
        source .venv/bin/activate
        ```
    *   On Windows:
        ```bash
        python -m venv .venv
        .venv\\Scripts\\activate
        ```

3.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure environment variables:**

    Create a `.env` file in the root directory of the project by copying the example or creating a new one.
    This file will store your application's configuration.


### Running the Application

Once the setup is complete, you can run the FastAPI application using Uvicorn:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

This command will start the development server:
*   `app.main:app`: Points to the FastAPI application instance (`app`) located in `app/main.py`.
*   `--reload`: Enables auto-reload, so the server restarts automatically when code changes are detected.
*   `--host 0.0.0.0`: Makes the server accessible from your local network (not just `localhost`).
*   `--port 8000`: Specifies the port on which the server will listen.

You should see output similar to this in your terminal:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using StatReload
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Accessing the API

Once the server is running, you can access:

*   **API Endpoints:** The main API is available at `http://localhost:8000/api/articles/`
    *   `POST /api/articles/fetch`: To trigger fetching and saving of articles.
    *   `GET /api/articles/`: To retrieve paginated articles.
*   **Interactive API Documentation (Swagger UI):** `http://localhost:8000/docs`
*   **Alternative API Documentation (ReDoc):** `http://localhost:8000/redoc`
*   **Health Check:** `http://localhost:8000/health`

These documentation interfaces allow you to interact with the API directly from your browser, view schemas, and test endpoints.

## News Analysis Features

### Article Triage Analysis

The system performs an initial triage analysis on all fetched articles, which includes:

- Category classification (e.g., Science, Technology, Politics)
- Sentiment analysis with nuanced categories
- Key claim extraction
- Entity identification (people, organizations, locations, events)
- Keywords extraction
- Narrative focus and source style characterization

### Deep Analysis

For articles flagged as requiring deeper analysis, the system can perform:

- Political leaning and bias detection
- Information quality assessment
- Source approach analysis (reporting style, perspective diversity)
- Framing analysis (metaphors, emphasis techniques)
- Comparative indicators (unique perspectives, potential omissions)

### Comparative Analysis

The system can compare how different sources cover the same news event:

- Identifies core facts agreed upon across all sources
- Analyzes source-specific differences in coverage
- Detects information gaps between sources
- Compares framing and language across sources
- Identifies potential source interests and motivations

## API Endpoints

### Article Management

- `POST /api/articles/fetch`: Fetch articles from RSS feeds
- `GET /api/articles/`: List articles with pagination
- `POST /api/articles/triage`: Run triage analysis on new articles

### Analysis Endpoints

- `POST /api/articles/{article_id}/analyze-deeply`: Perform deep analysis on a specific article
- `GET /api/articles/{article_id}/related`: Get articles related to the same news story
- `POST /api/articles/{article_id}/comparative-analysis`: Perform comparative analysis on related articles
- `GET /api/articles/{article_id}/comparative-analysis`: Get previously generated comparative analysis results