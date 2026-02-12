# Job Scraping Module (JobSpy)

This module integrates the `jobspy` library to scrape job postings from platforms like Indeed and LinkedIn, cleans the data, saves it to MongoDB, and automatically generates embeddings using Gemini.

## ⚠️ Attribution & Credits
This script was developed based on the work in this repository:
[https://github.com/Adhil-Payingalil/Job_scrapper](https://github.com/Adhil-Payingalil/Job_scrapper)

## Setup

### 1. Install Requirements
You need to install the `python-jobspy` library:
```bash
pip install python-jobspy pandas python-dotenv
```

### 2. Configuration
Edit `config.py` to set your search parameters:
- **SEARCH_TERMS**: List of job titles.
- **LOCATIONS**: List of cities/regions.
- **RESULTS_WANTED**: Jobs per search term.
- **SITE_NAME**: Platforms to scrape (e.g., `["indeed", "linkedin"]`).

## Usage

To run the scraper manually (development/testing mode):

```bash
python phase_3_workflow_job_matching/jobspy_scraper/run_scraper_test.py
```

## How It Works

1.  **Scrape**: `JobScraperIntegration.scrape_jobs_from_platforms` calls `jobspy` to get raw data.
2.  **Clean**: `clean_and_transform_job_data` normalizes columns and removes duplicates.
3.  **Save**: `save_jobs_to_mongodb` inserts new jobs into the `job_postings` collection (checking for duplicates).
4.  **Embed**: `_generate_embeddings_for_new_jobs` calls the Gemini API to create vector embeddings for the new jobs.