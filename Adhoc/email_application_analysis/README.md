# Email Application Analysis

This adhoc analysis identifies job postings that accept applications via email using vector search with pre-trained queries.

## Overview

The analysis uses MongoDB vector search to find job descriptions similar to common email application phrases. It leverages existing job embeddings (`jd_embedding` field) to perform semantic similarity matching.

## Features

- **Vector Search**: Uses 20 pre-defined email application query phrases
- **Similarity Scoring**: Ranks matches by semantic similarity
- **Comprehensive Results**: Includes job details, similarity scores, and matching queries
- **Platform Analysis**: Breaks down results by job platform (Indeed, LinkedIn, etc.)
- **CSV Export**: Detailed results in CSV format for further analysis

## Files

- `email_application_analysis.py` - Main analysis script
- `config_email_analysis.py` - Configuration settings
- `README.md` - This documentation
- `output/` - Results folder (created automatically)
  - `email_application_analysis_results.csv` - Detailed results
  - `email_analysis_summary.txt` - Summary statistics

## Prerequisites

- MongoDB connection (credentials in `.env` file in root directory)
- Python virtual environment activated
- Google Generative AI API key (GEMINI_API_KEY in `.env`)
- Required Python packages installed

## Usage

1. **Activate your virtual environment:**
   ```bash
   # Navigate to root directory first
   cd /path/to/resume_parsing_audit_study
   
   # Activate virtual environment
   .venv\Scripts\activate  # Windows
   # or
   source .venv/bin/activate  # Linux/Mac
   ```

2. **Run the analysis:**
   ```bash
   cd "Adhoc analysis/email_application_analysis"
   python email_application_analysis.py
   ```

3. **Review results:**
   - Check console output for summary statistics
   - Examine `output/email_application_analysis_results.csv` for detailed results
   - Read `output/email_analysis_summary.txt` for analysis summary

## Configuration

### Email Application Queries

The analysis uses 20 pre-defined phrases that commonly indicate email applications:

- "send resume via email"
- "email your application to"
- "apply by sending email"
- "submit application by email"
- "email applications accepted"
- And 15 more variations...

### Search Settings

- **Similarity Threshold**: 0.30 (minimum similarity score for matches)
- **Max Results per Query**: 100 (maximum matches per email query)
- **Vector Search Index**: "resume_embeddings" (MongoDB index name)

### Output Settings

- **Include Job Description**: Yes (full job description in results)
- **Include Confidence Scores**: Yes (similarity scores for each query)
- **Sample Size**: None (analyze all jobs)

## Results Format

### CSV Output Columns

- `job_id` - MongoDB document ID
- `job_title` - Job title
- `company_name` - Company name
- `source_platform` - Job platform (Indeed, LinkedIn, etc.)
- `search_term` - Job type classification
- `location` - Job location (city, state, country)
- `max_similarity_score` - Highest similarity score across all queries
- `matching_queries` - Queries that matched this job
- `num_matching_queries` - Number of matching queries
- `scraped_at` - When job was scraped
- `status` - Job processing status
- `job_description` - Full job description (if enabled)
- `query_scores` - JSON of individual query scores (if enabled)

### Summary Output

- Total jobs analyzed
- Jobs with email applications (count and percentage)
- Platform distribution
- Search term distribution
- Query performance statistics

## How It Works

1. **Query Embedding Generation**: Converts 20 email application phrases to vector embeddings
2. **Vector Search**: Searches job embeddings for semantic similarity to each query
3. **Similarity Filtering**: Filters results by minimum similarity threshold
4. **Deduplication**: Removes duplicate jobs found by multiple queries
5. **Result Collection**: Gathers detailed information for each unique match
6. **Analysis**: Generates statistics and summary information
7. **Export**: Saves results to CSV and summary files

## Performance

- **Speed**: Fast vector search using existing MongoDB indexes
- **Accuracy**: Semantic similarity matching captures various phrasings
- **Scalability**: Can process thousands of jobs efficiently
- **Cost**: Minimal API costs (only for query embedding generation)

## Limitations

- **Semantic Matching**: May miss jobs with very different phrasings
- **Threshold Sensitivity**: Results depend on similarity threshold setting
- **False Positives**: May include jobs that mention email but don't accept applications
- **Context Awareness**: Limited understanding of context vs. exact phrase matching

## Next Steps

After running this analysis, you can:

1. **Review Results**: Examine the CSV file to understand what was found
2. **Adjust Threshold**: Modify similarity threshold in config if needed
3. **Add Queries**: Include additional email application phrases
4. **Manual Validation**: Spot-check results for accuracy
5. **Gemini Analysis**: Use LLM analysis on promising candidates for validation

## Troubleshooting

### Common Issues

1. **MongoDB Connection Error**:
   - Verify `MONGODB_URI` in `.env` file
   - Check MongoDB server status

2. **Google AI API Error**:
   - Verify `GEMINI_API_KEY` in `.env` file
   - Check API key permissions and quotas

3. **No Results Found**:
   - Lower similarity threshold in config
   - Add more email application queries
   - Check if job embeddings exist

4. **Import Errors**:
   - Ensure virtual environment is activated
   - Install required packages: `pip install google-generativeai python-dotenv`

### Debugging

Enable detailed logging by checking console output. The script logs:
- Database connection status
- Embedding generation progress
- Vector search results
- Error details and stack traces

