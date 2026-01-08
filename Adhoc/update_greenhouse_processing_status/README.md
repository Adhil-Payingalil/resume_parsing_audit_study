# Update Greenhouse Processing Status

This script updates the `Job_postings_greenhouse` collection with a `processing_status` field that indicates whether each job has been processed by the matching workflow.

## What it does

For all jobs matching the filter from `greenhouse_config`, the script sets:
- **`processing_status: "matched"`** - Job is in `greenhouse_resume_job_matches` collection
- **`processing_status: "unmatched"`** - Job is in `greenhouse_unmatched_job_postings` collection  
- **`processing_status: "not processed"`** - Job matches the filter but hasn't been processed yet

Also adds `processing_status_updated_at` timestamp field.

## Filter Used

The script uses the same filter as `greenhouse_config`:
- `jd_extraction: True`
- `cycle: 6`
- `jd_embedding: { $exists: true, $ne: null }`

## Usage

### Dry Run (default - safe, no changes)
```bash
python update_greenhouse_processing_status.py
```

### Actually Update Database
```bash
python update_greenhouse_processing_status.py --force
```

## Output

The script:
1. Logs progress and statistics to console
2. Saves results to `update_results_YYYYMMDD_HHMMSS.json` file

## Example Output

```
=== UPDATE SUMMARY ===
Mode: DRY RUN
Duration: 0:00:05.123456
Total jobs matching filter: 163
Matched jobs found in collections: 81
Unmatched jobs found in collections: 31
Updated with 'matched' status: 81
Updated with 'unmatched' status: 31
Updated with 'not processed' status: 51
Skipped (already updated): 0
Errors: 0
```

## Notes

- By default, runs in **DRY RUN** mode - no database changes are made
- Use `--force` flag to actually update the database
- The script processes jobs in batches of 100 for efficiency
- Skips jobs that already have the correct status to avoid unnecessary updates

