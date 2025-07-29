# Phase 2.1: Job Scraping and MongoDB Integration

This module handles job data scraping from multiple platforms and stores the data in MongoDB for the resume audit study.

## Overview

The job scraping workflow consists of:
1. **Job Scraping**: Using the `jobspy` library to scrape jobs from Indeed, LinkedIn, and other platforms
2. **Data Cleaning**: Standardizing and cleaning the scraped data
3. **MongoDB Storage**: Saving cleaned job data to a new `job_postings` collection
4. **Deduplication**: Preventing duplicate job entries
5. **Status Tracking**: Tracking the processing status of each job

## Setup

### 1. Install Dependencies

```bash
pip install python-jobspy
```

### 2. Environment Variables

Ensure your `.env` file contains:
```
MONGODB_URI=your_mongodb_connection_string
```

### 3. Database Schema

The `job_postings` collection uses the following schema:

```json
{
  "_id": "ObjectId",
  "job_link": "String (unique)",
  "job_title": "String",
  "company_name": "String", 
  "job_description_raw": "String",
  "scraped_at": "DateTime",
  "source_platform": "String",
  "status": "String (PENDING/EMBEDDED/MATCHED/NO_MATCHES)",
  "city": "String",
  "state": "String", 
  "country": "String",
  "industry_sector": "String (to be populated)",
  "employer_size": "String (to be populated)",
  "search_term": "String",
  "search_location": "String"
}
```

## Usage

### Basic Usage

```python
from job_scraper_integration import JobScraperIntegration

# Initialize scraper
scraper = JobScraperIntegration()

# Define search parameters
search_terms = ["data analyst", "software engineer"]
locations = ["Toronto, ON", "Vancouver, BC"]

# Scrape jobs
jobs_df = scraper.scrape_jobs_from_platforms(
    search_terms=search_terms,
    locations=locations,
    results_per_search=50,
    platforms=["indeed", "linkedin"]
)

# Clean and save
cleaned_df = scraper.clean_and_transform_job_data(jobs_df)
saved_count = scraper.save_jobs_to_mongodb(cleaned_df)
print(f"Saved {saved_count} jobs to MongoDB")
```

### Testing

Run the test script to verify everything works:

```bash
cd "Phase 2.1 Workflow - Job Matching"
python test_job_scraping.py
```

### Getting Statistics

```python
# Get job statistics
stats = scraper.get_job_statistics()
print(stats)

# Get pending jobs for processing
pending_jobs = scraper.get_pending_jobs(limit=100)
```

## Features

### 1. Multi-Platform Scraping
- **Indeed**: Primary job board with good coverage
- **LinkedIn**: Professional networking platform
- **Glassdoor**: Company reviews and job postings
- **ZipRecruiter**: Additional job sources

### 2. Data Cleaning
- Standardizes column names
- Removes duplicates based on job URLs
- Validates required fields
- Adds metadata for tracking

### 3. MongoDB Integration
- Creates proper indexes for performance
- Handles duplicate prevention
- Tracks job processing status
- Provides statistics and monitoring

### 4. Error Handling
- Graceful handling of scraping failures
- Logging of all operations
- Continues processing even if some jobs fail

## Configuration

### Search Parameters

```python
# Customize your search
scraper.scrape_jobs_from_platforms(
    search_terms=["data analyst", "business analyst"],
    locations=["Toronto, ON", "Montreal, QC"],
    platforms=["indeed"],  # Focus on one platform
    results_per_search=25,  # Smaller batch
    hours_old=72,  # Jobs posted in last 3 days
    country_indeed='Canada'  # Focus on Canadian jobs
)
```

### Rate Limiting

The `jobspy` library handles rate limiting automatically, but you can control the pace:

```python
# Add delays between requests
import time

for search_term in search_terms:
    jobs_df = scraper.scrape_jobs_from_platforms(
        search_terms=[search_term],
        locations=locations
    )
    time.sleep(5)  # Wait 5 seconds between searches
```

## Troubleshooting

### Common Issues

1. **Import Error**: `jobspy` library not found
   ```bash
   pip install python-jobspy
   ```

2. **No Jobs Scraped**: 
   - Check network connectivity
   - Verify search terms and locations
   - Try different platforms
   - Check for rate limiting

3. **MongoDB Connection Error**:
   - Verify `MONGODB_URI` in `.env`
   - Check MongoDB server status
   - Ensure proper permissions

4. **Duplicate Key Error**:
   - The system automatically handles duplicates
   - Check if job URLs are being properly extracted

### Debugging

Enable detailed logging by checking the logs in your console output. The system logs:
- Scraping progress
- Data cleaning steps
- MongoDB operations
- Error details

## Next Steps

After successful job scraping, the next phase involves:
1. **Embedding Generation**: Creating vector embeddings for job descriptions
2. **Resume Matching**: Matching resumes to jobs using vector similarity
3. **LLM Evaluation**: Using AI to evaluate match quality

## Files

- `job_scraper_integration.py`: Main scraping functionality
- `test_job_scraping.py`: Test script for verification
- `README.md`: This documentation file 