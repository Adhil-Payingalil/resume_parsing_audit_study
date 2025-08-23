# Job Fields Update Script

This script adds missing job fields to existing documents in the `resume_job_matches` collection.

## What it does

- Adds `location` and `date_posted` fields to existing `resume_job_matches` documents
- Looks up the complete job data from `job_postings` collection using `job_posting_id`
- Updates all existing documents in batches
- Provides detailed progress tracking and error reporting

## Fields Added

- **`location`**: Job location from job_postings (defaults to "Not specified" if missing)
- **`date_posted`**: When the job was posted (defaults to null if missing)
- **`_last_updated`**: Timestamp of when this update was performed
- **`_update_source`**: Identifier for this update operation

## Prerequisites

- MongoDB connection (credentials in `.env` file in root directory)
- Python virtual environment activated
- Required Python packages installed

## Usage

1. **Activate your virtual environment:**
   ```bash
   # Navigate to root directory first
   cd /path/to/resume_parsing_audit_study
   
   # Activate virtual environment (adjust path as needed)
   .venv\Scripts\activate  # Windows
   # or
   source .venv/bin/activate  # Linux/Mac
   ```

2. **Run the script:**
   ```bash
   cd "Adhoc analysis/update_job_fields"
   python update_job_fields.py
   ```

3. **Review the summary and confirm:**
   - The script will show you what fields are available in `job_postings`
   - It will check if fields already exist in `resume_job_matches`
   - Confirm the update by typing `y` when prompted

## What happens during execution

1. **Analysis Phase**: 
   - Connects to MongoDB
   - Analyzes field availability in `job_postings`
   - Checks current structure of `resume_job_matches`
   - Shows summary of what will be updated

2. **Update Phase**:
   - Processes documents in batches of 50
   - For each document:
     - Looks up the job using `job_posting_id`
     - Extracts `location` and `date_posted` fields
     - Updates the document with new fields
   - Provides progress updates every 10 documents

3. **Results Summary**:
   - Shows total documents processed
   - Counts successful updates, errors, and skipped documents
   - Displays success rate

## Error Handling

- **Missing job_posting_id**: Document skipped, error logged
- **Job not found**: Document skipped, error logged
- **Invalid ObjectId**: Document skipped, error logged
- **Database connection issues**: Script stops with error message

## Safety Features

- **Batch processing**: Prevents overwhelming the database
- **Progress tracking**: Shows real-time progress
- **Error isolation**: One document error doesn't stop the entire process
- **Metadata tracking**: Records when and how updates were performed
- **Confirmation prompt**: Requires user confirmation before proceeding

## After running

Once completed, all existing `resume_job_matches` documents will have:
- `location` field populated from `job_postings`
- `date_posted` field populated from `job_postings`
- `_last_updated` timestamp
- `_update_source` identifier

## Next steps

After running this script, you can update your main workflow (`resume_job_matching_workflow.py`) to include these fields for future job processing runs.

