# Phase 3: Job Matching Workflow

This directory contains the tools and workflows for **embedding** job descriptions and **matching** them to resumes. This workflow is the direct follow-up to the **Greenhouse Scraper** (`greenhouse_scraper/`).

## Workflow Overview

After scraping jobs using the tools in `greenhouse_scraper/`, you must run the following two scripts in order to generate matches.

### Step 1: Generate Embeddings
**Script:** `run_greenhouse_embedding.py`

*   **Purpose:** Converts the text descriptions of scraped jobs into vector embeddings using the configured model. These embeddings are essential for the semantic matching process.
*   **Action:**
    *   Reads jobs from MongoDB (filtered by Cycle).
    *   Generates embeddings for the `job_description` field.
    *   Updates the job document with the vector data.
*   **Usage:**
    ```bash
    python run_greenhouse_embedding.py
    ```
    *Prompts for Cycle Number upon execution.*

### Step 2: Run Matching
**Script:** `run_greenhouse_matching.py`

*   **Purpose:** Matches existing resumes (from Phase 2) against the newly embedded job postings.
*   **Action:**
    *   Loads resumes and job embeddings.
    *   Calculates similarity scores.
    *   Applies threshold logic to determine valid matches.
    *   Updates MongoDB with match results.
*   **Usage:**
    ```bash
    python run_greenhouse_matching.py [--cycle X.X] [--limit N] [--industry PREFIX] [--force]
    ```
*   **Arguments:**
    *   `--cycle`: Filter jobs by a specific cycle number (e.g., `8.1`). If omitted, you will be prompted or can choose to process all.
    *   `--limit`: Restrict the number of jobs to process (useful for testing).
    *   `--industry`: Filter by industry prefix (e.g., `ITC`, `FIN`).
    *   `--force`: Reprocess jobs that have already been matched (overwrites existing results).
    *   `--skip-processed`: Skip jobs that have already been processed (default behavior).

## Directory Structure

*   `src/embeddings/`: Core logic for generating vector embeddings.
*   `src/matching/`: Core logic for matching algorithms.
*   `configs/`: Configuration files for thresholds and model parameters.
*   `greenhouse_scraper/`: (See separate README) The precursor step for finding jobs.
