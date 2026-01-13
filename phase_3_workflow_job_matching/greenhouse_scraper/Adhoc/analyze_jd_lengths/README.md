# Job Description Length Analysis

This folder contains scripts to analyze job description lengths in the `Job_postings_greenhouse` MongoDB collection and update quality flags based on the analysis.

## Scripts Overview

### 1. `analyze_jd_lengths.py`
**Main analysis script** that:
- Analyzes all job descriptions in the MongoDB collection
- Calculates word counts and character counts for each job description
- Adds `jd_word_count`, `jd_char_count`, and `jd_length_analyzed_at` fields to the collection
- Categorizes jobs by length (very short, short, medium, long)
- Identifies potentially low-quality descriptions
- Generates detailed reports and statistics

### 2. `update_jd_extraction_flags.py`
**Flag update script** that:
- Finds jobs with low-quality descriptions based on length thresholds
- Updates the `jd_extraction` flag to `False` for jobs that don't meet quality standards
- Supports both dry-run (preview) and live-update modes
- Generates reports of all changes made

## Usage

### Step 1: Run the Analysis
```bash
cd Adhoc/analyze_jd_lengths
python analyze_jd_lengths.py
```

This will:
- Analyze all job descriptions in your MongoDB collection
- Add length fields (`jd_word_count`, `jd_char_count`) to each job document
- Generate summary statistics and detailed CSV reports
- Identify jobs with potentially low-quality descriptions

### Step 2: Review the Results
Check the generated files:
- `jd_length_analysis_YYYYMMDD_HHMMSS.csv` - Detailed data for all jobs
- `jd_analysis_summary_YYYYMMDD_HHMMSS.json` - Summary statistics
- `low_quality_jobs_YYYYMMDD_HHMMSS.csv` - Jobs identified as low quality

### Step 3: Preview Flag Updates (Optional)
```bash
python update_jd_extraction_flags.py
```

This runs in **dry-run mode** by default and shows you what would be updated without making changes.

### Step 4: Update Flags for Low-Quality Descriptions
```bash
python update_jd_extraction_flags.py --live-update
```

This will actually update the `jd_extraction` flag to `False` for jobs with low-quality descriptions.

## Configuration Options

### Analysis Thresholds (built into analyze_jd_lengths.py)
- **Very Short**: < 50 words or < 200 characters
- **Short**: 50-99 words or 200-499 characters  
- **Medium**: 100-299 words or 500-1499 characters
- **Long**: 300+ words or 1500+ characters

### Update Thresholds (customizable in update_jd_extraction_flags.py)
```bash
# Custom thresholds
python update_jd_extraction_flags.py --word-threshold 30 --char-threshold 150

# Live update with custom thresholds
python update_jd_extraction_flags.py --word-threshold 30 --char-threshold 150 --live-update
```

## Output Files

### From analyze_jd_lengths.py:
- `jd_length_analysis_YYYYMMDD_HHMMSS.csv` - Complete job data with length metrics
- `jd_analysis_summary_YYYYMMDD_HHMMSS.json` - Statistical summary
- `low_quality_jobs_YYYYMMDD_HHMMSS.csv` - Jobs flagged as potentially low quality

### From update_jd_extraction_flags.py:
- `jd_extraction_update_report_[mode]_YYYYMMDD_HHMMSS.csv` - Detailed update report
- `jd_extraction_update_summary_[mode]_YYYYMMDD_HHMMSS.json` - Update summary

## MongoDB Fields Added

The scripts add these new fields to your job documents:

### Length Analysis Fields (from analyze_jd_lengths.py):
- `jd_word_count` (int) - Number of words in the job description
- `jd_char_count` (int) - Number of characters in the job description  
- `jd_length_analyzed_at` (datetime) - When the length analysis was performed

### Update Tracking Fields (from update_jd_extraction_flags.py):
- `jd_extraction_updated_at` (datetime) - When the jd_extraction flag was last updated
- `jd_extraction_update_reason` (string) - Reason for the update (e.g., "Low quality: 25 words, 150 chars")

## Example Workflow

1. **Initial Analysis**:
   ```bash
   python analyze_jd_lengths.py
   ```
   
2. **Review Results**: Check the generated CSV and JSON files to understand your data quality

3. **Preview Updates**:
   ```bash
   python update_jd_extraction_flags.py
   ```
   
4. **Apply Updates**:
   ```bash
   python update_jd_extraction_flags.py --live-update
   ```

## Safety Features

- **Dry Run by Default**: The update script previews changes before making them
- **Detailed Logging**: All operations are logged to `../../logs/`
- **Comprehensive Reports**: Every operation generates detailed reports
- **Error Handling**: Robust error handling with detailed error messages
- **Connection Management**: Proper MongoDB connection handling

## Quality Criteria

Jobs are considered low quality if they have:
- **Word count < 50** (default threshold)
- **Character count < 200** (default threshold)

These thresholds can be customized based on your specific needs and data analysis results.

## Logs

All operations are logged to:
- `../../logs/analyze_jd_lengths.log`
- `../../logs/update_jd_extraction_flags.log`

Check these files for detailed operation history and any errors encountered.

