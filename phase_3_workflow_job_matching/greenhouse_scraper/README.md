# Greenhouse Job Scraper

This module provides tools to scrape job postings from Greenhouse and enrich them with detailed job descriptions using Jina AI.

## Architecture

*   **`job_scraper.py`**: Main scraper using Playwright and AgentQL to navigate Greenhouse and extract job listings.
*   **`description_extractor.py`**: Enriches job listings by fetching full descriptions via Jina AI.
*   **`config.py`**: Centralized configuration.

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install playwright agentql pymongo python-dotenv
    playwright install chromium
    ```

2.  **Environment Variables**:
    Ensure your `.env` file contains:
    ```
    MONGODB_URI=...
    AGENTQL_API_KEY=...
    JINAAI_API_KEY=...
    ```

## Usage

### 1. Scrape Job Listings
Run the main scraper to find new jobs:
```bash
python phase_3_workflow_job_matching/greenhouse_scraper/job_scraper.py
```

### 2. Extract Descriptions
Run the extractor to fetch details for scraped jobs:
```bash
python phase_3_workflow_job_matching/greenhouse_scraper/description_extractor.py
```