# Greenhouse Job Scraper

This directory contains the core scraping and data verification scripts for Phase 3 of the resume parsing audit study. The workflow is designed to sequentially find job listings, verify their application requirements, and extract detailed descriptions using AI.

## Workflow Overview

The process consists of 3 sequential steps. It is critical to run them in the specified order to ensure data integrity.

### Step 1: Job Discovery
**Script:** `job_scraper.py`

*   **Purpose:** Navigates Greenhouse job boards to discover and index job listings.
*   **Key Features:**
    *   Uses **Playwright** and **AgentQL** for robust navigation and selector-free extraction.
    *   Handles "See more jobs" pagination automatically (configurable limit).
    *   Filters jobs by "Date posted" (default: 30 days) and location.
    *   Saves discovered job links and basic metadata (title, company, location) to MongoDB.
    *   Prevents duplicates using a unique index on `job_link`.
*   **Usage:**
    ```bash
    python job_scraper.py
    ```

### Step 2: Requirement Verification
**Script:** `verify_required_fields.py`

*   **Purpose:** Visits each discovered job link to audit the application form for unsupported fields.
*   **Key Features:**
    *   Scans for specific "deal-breaker" required fields that make a job unsuitable for the study (e.g., "portfolio password", "transcript", "video").
    *   Updates the MongoDB document with `input_field_labels` and `unsupported_input_fields` flags.
    *   Supports resuming from where it left off (skips already processed jobs by default).
    *   Can verify specific "Cycles" of data to keep batches organized.
*   **Usage:**
    ```bash
    python verify_required_fields.py
    ```
    *Prompts for Cycle Number and limit upon execution.*

### Step 3: Description Extraction
**Script:** `description_extractor_optimized.py`

*   **Purpose:** Fetches the full textual content of the job description for valid jobs.
*   **Key Features:**
    *   Uses **Jina AI Reader API** to convert HTML job pages into clean, readable markdown/text.
    *   **Optimized Performance**: Runs asynchronously using `aiohttp` and `asyncio` for high-throughput processing.
    *   Includes robust error handling for API rate limits (429) and timeouts.
    *   Extracts content using heuristics (regex, start/end markers) to isolate the job description from headers/footers.
    *   Updates MongoDB with the cleaned `job_description` and extraction status (`jd_extraction`).
*   **Usage:**
    ```bash
    python description_extractor_optimized.py
    ```
    *Prompts for Cycle Number, batch size, and processing limit.*

## Configuration

Shared settings (API keys, database URIs, timeouts) are managed in `config.py` and environment variables. Ensure your `.env` file is properly configured with:
*   `MONGODB_URI`
*   `JINAAI_API_KEY`
*   `AGENTQL_API_KEY`
*   `GREENHOUSE_URL` / `JOBS_URL`

## Logs

Logs for each script are generated in the `logs/` directory, separated by script name (e.g., `job_scraper.log`, `verify_required_fields.log`).