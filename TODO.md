# TODO - News Aggregator Project

Project Summary: Phase 1 Completion

We have successfully laid the groundwork for the News Aggregator application. The key accomplishments include:

Project Initialization & Structure:

Set up a Python project with a FastAPI backend.
Established a modular directory structure (app, config, tests, etc.).
Initialized a Git repository and created a .gitignore file.
Managed dependencies using a virtual environment and a requirements.txt file.
Configuration Management:

Implemented a Settings class using pydantic-settings to handle application configuration (e.g., database URL, RSS feed list) via environment variables and a .env file.
Core Models:

Defined Pydantic models for Article data, ensuring type validation and clear data structures.
RSS Feed Ingestion:

Developed an rss_fetcher service (rss_fetcher.py) capable of:
Fetching content from multiple RSS feed URLs.
Parsing feed data (title, link, publication date, summary) using the feedparser library.
Mapping fetched data to the Article model.
Database Integration (MongoDB):

Set up MongoDB connection management (db.py), including connect/disconnect logic tied to the FastAPI application lifecycle (startup/shutdown).
Created an article_service (article_service.py) to:
Save articles to MongoDB, performing upserts based on article URLs to avoid duplicates and adding a first_seen_at timestamp.
Retrieve a paginated and sorted list of articles from the database.
API Layer (FastAPI):

Developed API endpoints under /api/articles (articles.py):
POST /fetch: Triggers fetching of articles from RSS feeds and saves them to the MongoDB database. Returns a summary of the operation.
GET /: Retrieves a paginated list of articles stored in the database.
Included a /health check endpoint.
FastAPI automatically provides interactive API documentation (/docs and /redoc).
Logging:

Integrated basic logging throughout the application for monitoring and debugging.

This file outlines the remaining tasks and future development phases for the News Aggregator project, based on the initial plan.

## Phase 2: Advanced Story Discovery & Initial Processing

- **Social Media Monitoring:**
    - [ ] Integrate Twitter/X API for tracking trending news and journalist accounts.
    - [ ] Integrate Reddit API for relevant subreddits.
    - [ ] Explore services like CrowdTangle (if applicable/available) or alternatives.
    - [ ] Develop a unified ingestion service for social media content.
- **Document Embedding Pipeline:**
    - [ ] Choose and integrate a sentence embedding model (e.g., OpenAI's `text-embedding-ada-002`, Sentence Transformers).
    - [ ] Add `embedding` field to the `Article` model and database schema.
    - [ ] Implement a service to generate and store embeddings for incoming articles.
    - [ ] Consider backfilling embeddings for existing articles.
- **Vector Database Setup:**
    - [ ] Research and choose a vector database (e.g., Pinecone, Weaviate, Milvus, FAISS integrated with PostgreSQL/Elasticsearch).
    - [ ] Set up the chosen vector database.
    - [ ] Implement services to store and query article embeddings for similarity search.
- **Clustering & Topic Detection:**
    - [ ] Implement clustering algorithms (e.g., DBSCAN, hierarchical clustering) on article embeddings.
    - [ ] Add `cluster_id` or `topic_id` to the `Article` model.
    - [ ] Develop a service to periodically run clustering and assign articles to topics.
    - [ ] Implement logic to calculate centroids for news clusters (representing the "core" story).
- **Entity Recognition:**
    - [ ] Integrate an NER library (e.g., spaCy, NLTK, or an LLM-based approach).
    - [ ] Add `entities` field (e.g., list of people, organizations, locations) to the `Article` model.
    - [ ] Extract and store named entities for each article.
    - [ ] Plan for cross-referencing entities and building relationship graphs (longer-term).

## Phase 3: Enhanced Source Acquisition & Content Retrieval

- **Smart Web Scraping:**
    - [ ] Develop website-specific scrapers for major news outlets not providing full RSS content.
    - [ ] Integrate tools like Playwright or Puppeteer for JavaScript-heavy sites.
    - [ ] Implement respectful crawling policies (rate limiting, `robots.txt`).
    - [ ] Service to extract `full_text` for articles where RSS provides only a summary.
- **Paywall Management:**
    - [ ] Research legal options (e.g., partnerships, services like Blendle/PressReader if viable).
    - [ ] Implement a system to flag premium/paywalled content.
    - [ ] Consider summarization of publicly available snippets as an alternative for paywalled content.
- **Archive Integration:**
    - [ ] Explore APIs for Internet Archive and other web archives.
    - [ ] Develop functionality to retrieve historical versions of articles for comparison or to track story evolution.

## Phase 4: Evaluation & Validation Pipeline

- **LLM Processing Chain - Initial Assessment:**
    - [x] Set up infrastructure for using lightweight LLMs.
    - [x] Develop prompts for triaging and categorizing content.
    - [x] Extract key claims, sentiment, and basic framing.
    - [x] Implement flagging for articles requiring deeper analysis.
- **LLM Processing Chain - Deep Analysis:**
    - [x] Set up infrastructure for more powerful LLMs (e.g., Claude, GPT series).
    - [x] Design prompts for comprehensive analysis (chain-of-thought).
    - [x] Generate structured output with standardized metrics (as defined in the plan).
- **Comparative Analysis:**
    - [x] Implement schema for comparing how different sources cover the same story
    - [x] Develop prompt templates for identifying differences in coverage and framing
    - [x] Create API endpoints for performing and retrieving comparative analysis
    - [x] Store analysis results and link to related articles
- **Cross-Validation:**
    - [ ] Implement logic to compare metrics across multiple LLM providers (if used).
    - [ ] Design a system for human-in-the-loop validation for controversial stories.
    - [ ] Develop consensus scoring from multiple assessments.
- **Metric Calculation - Source Credibility:**
    - [ ] Design schema for a source credibility database.
    - [ ] Integrate with existing resources (e.g., Media Bias/Fact Check, AllSides APIs if available).
    - [ ] Implement dynamic updates based on fact-checking outcomes.
- **Metric Calculation - Content-Based Metrics:**
    - [ ] Train or fine-tune specialized models for metrics like sensationalism, complexity (if feasible).
    - [ ] Implement few-shot learning with calibrated examples for LLM-based metrics.
    - [ ] Generate confidence intervals for metrics.
- **Metric Calculation - Comparative Analysis:**
    - [ ] Calculate divergence scores between sources on the same story.
    - [ ] Identify unique perspectives and shared narratives.
    - [ ] Highlight significant omissions in coverage.

## Phase 5: Frontend Application & User Personalization

- **Technology Choice:**
    - [ ] Decide on a frontend framework (e.g., React, Vue, Svelte, Next.js).
- **Interactive Dashboard:**
    - [ ] Design and implement a responsive SPA.
    - [ ] Integrate data visualization components (e.g., charts for metrics).
    - [ ] Allow customizable views based on user preferences.
- **Story Explorer Interface:**
    - [ ] Implement topic-based navigation.
    - [ ] Visualize relationship graphs between stories and entities.
    - [ ] Allow side-by-side comparison of multiple sources.
    - [ ] Provide expandable details for metrics and analysis.
- **User Personalization:**
    - [ ] Implement user accounts and authentication.
    - [ ] Allow users to save topics and sources of interest.
    - [ ] Develop a personalized feed algorithm with diversity recommendations.
    - [ ] Implement reading history and blind spot analysis.

## Phase 6: Refinement, Scaling, and Deployment

- **Technical Architecture Enhancements:**
    - [ ] Implement a robust queue system (RabbitMQ/Kafka) for the data ingestion and analysis pipeline.
    - [ ] Convert synchronous operations (like initial RSS fetching in the API) to background tasks.
    - [ ] Optimize database queries and indexing.
    - [ ] Implement caching strategies (e.g., Redis) for frequently accessed data and LLM results.
- **Scalability & Performance:**
    - [ ] Profile and optimize critical code paths.
    - [ ] Consider serverless functions for scalable, event-driven processing for LLM tasks.
- **Containerization & Deployment:**
    - [ ] Create Dockerfiles for backend services.
    - [ ] Set up Docker Compose for local development.
    - [ ] Plan and implement a cloud deployment strategy (e.g., AWS, GCP, Azure).
    - [ ] Implement CI/CD pipelines.
- **Testing:**
    - [ ] Write comprehensive unit tests for all services and models.
    - [ ] Develop integration tests for API endpoints and database interactions.
    - [ ] Plan for end-to-end testing (especially with frontend).
- **Monitoring & Alerting:**
    - [ ] Integrate logging and monitoring tools (e.g., ELK stack, Prometheus, Grafana).
    - [ ] Set up alerts for critical errors or performance issues.
- **Security:**
    - [ ] Conduct security audits.
    - [ ] Ensure proper input validation and output encoding.
    - [ ] Manage API keys and secrets securely.

## General Backend Tasks

- [ ] Refine error handling and provide more specific error responses in the API.
- [ ] Add more comprehensive logging across all services.
- [ ] Implement API rate limiting and authentication/authorization for relevant endpoints.
- [ ] Create database indexes for frequently queried fields (e.g., `publication_date`, `url`, `source_name`).
