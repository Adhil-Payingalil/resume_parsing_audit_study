# Greenhouse Job Link Update Script

This is a one-time use script to add `job_link` field to existing documents in the `greenhouse_resume_job_matches` and `greenhouse_unmatched_job_postings` collections.

## Problem
Existing documents in these collections were created before the `job_link` field was added to the workflow, so they're missing this field.

## Solution
This script:
1. Looks up job links from the `Job_postings_greenhouse` collection using `job_posting_id`
2. Updates all existing documents in both collections with the `job_link` field
3. Adds a timestamp field `job_link_updated_at` to track when the update was performed

## Usage

### 1. Activate Virtual Environment
```bash
# Navigate to project root (two levels up)
cd ../..
# Activate virtual environment 
venv\Scripts\activate  # On Windows
```

### 2. Run Dry Run First (Recommended)
```bash
cd "Adhoc analysis/greenhouse_job_link_update"
python update_greenhouse_job_links.py
```

### 3. Run Actual Update
Edit the script and set `DRY_RUN = False`, then run:
```bash
python update_greenhouse_job_links.py
```

## Safety Features
- **Dry Run Mode**: Default mode shows what would be updated without making changes
- **Batch Processing**: Processes documents in batches of 100
- **Error Handling**: Continues processing even if individual documents fail
- **Logging**: Comprehensive logging of all operations
- **Statistics**: Shows detailed statistics of the update process
- **Results File**: Saves results to a JSON file with timestamp

## Output
The script will:
- Show progress in the console
- Create a results file: `update_results_YYYYMMDD_HHMMSS.json`
- Log all operations and any errors encountered

## Collections Updated
- `greenhouse_resume_job_matches`
- `greenhouse_unmatched_job_postings`

## Fields Added
- `job_link`: The job link from the greenhouse job posting
- `job_link_updated_at`: Timestamp of when this field was added
