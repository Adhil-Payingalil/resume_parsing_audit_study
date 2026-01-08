# Greenhouse Job Status Update Script

This script updates documents in the `Job_postings_greenhouse` collection with their processing status based on whether they have been processed by the resume-job matching workflow.

## Purpose

The script adds a `processing_status` field to job postings to track whether they have been processed and whether a match was found:
- **"matched"**: Job has been processed and has a resume match (job ID exists in `greenhouse_resume_job_matches`)
- **"unmatched"**: Job has been processed but no resume match was found (job ID exists in `greenhouse_unmatched_job_postings`)
- Jobs that haven't been processed yet are left unchanged

The script also adds a `processing_status_updated_at` timestamp field for reference.

## Usage

### 1. Activate Virtual Environment
```bash
# Navigate to project root (two levels up)
cd ../..
# Activate virtual environment 
.venv\Scripts\activate  # On Windows
```

### 2. Run Dry Run First (Recommended)
```bash
cd "Adhoc analysis/update_greenhouse_job_status"
python update_greenhouse_job_status.py
```

### 3. Run Actual Update
Edit the script and set `DRY_RUN = False`, then run:
```bash
python update_greenhouse_job_status.py
```

## Safety Features
- **Dry Run Mode**: Default mode shows what would be updated without making changes
- **Batch Processing**: Processes documents in batches of 100
- **Error Handling**: Continues processing even if individual documents fail
- **Logging**: Comprehensive logging of all operations
- **Statistics**: Shows detailed statistics of the update process
- **Results File**: Saves results to a JSON file with timestamp
- **Skip Already Updated**: Skips documents that already have the correct status

## Output
The script will:
- Show progress in the console
- Create a results file: `update_results_YYYYMMDD_HHMMSS.json`
- Log all operations and any errors encountered

## Collection Updated
- `Job_postings_greenhouse`

## Fields Added/Updated
- `processing_status`: Status of the job ("matched" or "unmatched")
- `processing_status_updated_at`: Timestamp of when this field was last updated

## Source Collections
The script reads from:
- `greenhouse_resume_job_matches`: To find jobs with matches (using `job_posting_id` field)
- `greenhouse_unmatched_job_postings`: To find jobs without matches (using `job_posting_id` field)


