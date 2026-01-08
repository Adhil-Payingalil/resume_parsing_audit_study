# Greenhouse Job Description Restoration Script

This script restores the accidentally deleted `job_description` field in the `Job_postings_greenhouse` collection by looking up descriptions from the greenhouse match collections.

## Problem
The `job_description` field was accidentally deleted from the `Job_postings_greenhouse` collection, but the descriptions still exist in:
- `greenhouse_resume_job_matches` collection
- `greenhouse_unmatched_job_postings` collection

## Solution
This script:
1. Builds a mapping of `job_posting_id` → `job_description` from both match collections
2. Finds all documents in `Job_postings_greenhouse` that are missing `job_description`
3. Updates them with the found descriptions
4. Leaves blank if no description is found (likely `jd_extraction=false` documents)

## Usage

### 1. Activate Virtual Environment
```bash
# Navigate to project root
cd ../..
# Activate virtual environment 
.venv\Scripts\activate  # On Windows
```

### 2. Run Dry Run First (Recommended)
```bash
cd "Adhoc analysis/restore_greenhouse_job_descriptions"
python restore_job_descriptions.py
```

### 3. Run Actual Restoration
Edit the script and set `DRY_RUN = False`, then run:
```bash
python restore_job_descriptions.py
```

## How It Works

### Data Source Priority
1. **Primary**: `greenhouse_resume_job_matches` collection
2. **Secondary**: `greenhouse_unmatched_job_postings` collection (only if not found in primary)

### Matching Logic
- Uses `job_posting_id` to match documents
- In `Job_postings_greenhouse`, the `_id` field IS the `job_posting_id`
- Looks for non-empty, non-null `job_description` values

### Safety Features
- **Dry Run Mode**: Default mode shows what would be updated without making changes
- **Batch Processing**: Processes documents in batches of 100
- **Error Handling**: Continues processing even if individual documents fail
- **Logging**: Comprehensive logging of all operations
- **Statistics**: Shows detailed statistics of the restoration process
- **Results File**: Saves results to a JSON file with timestamp

## Expected Results
- **Found descriptions**: Documents with matching job descriptions will be updated
- **Missing descriptions**: Documents without matches will be left unchanged (likely `jd_extraction=false`)
- **Statistics**: Complete breakdown of processed, updated, and skipped documents

## Output
The script will:
- Show progress in the console
- Create a results file: `restoration_results_YYYYMMDD_HHMMSS.json`
- Log all operations and any errors encountered

## Collections Involved
- **Source Collections**:
  - `greenhouse_resume_job_matches` (primary source)
  - `greenhouse_unmatched_job_postings` (secondary source)
- **Target Collection**:
  - `Job_postings_greenhouse` (documents to be updated)

## Fields Added/Updated
- `job_description`: The restored job description text
- `job_description_restored_at`: Timestamp of when this field was restored
