# Simple Resume-Job Matching Test Workflow

This directory contains a simplified test workflow for resume-job matching using MongoDB's native vector search capabilities.

## Overview

The simple test workflow consists of three main components:

1. **`verify_vector_indexes.py`** - Verifies that MongoDB vector search indexes are properly set up
2. **`test_simple_matching_workflow.py`** - Core workflow implementation using MongoDB vector search
3. **`run_simple_test.py`** - Main script to run the test workflow with formatted output

## Prerequisites

Before running the test workflow, ensure you have:

1. **MongoDB with vector search indexes**:
   - `resume_embedding_index` on the `Standardized_resume_data` collection
   - `job_embedding_index` on the `job_postings` collection

2. **Python Environment**:
   - Python 3.8+
   - Required packages installed (see `requirements.txt`)
   - Virtual environment activated

3. **Environment Variables**:
   - MongoDB connection string in `.env` file
   - Gemini API key configured

## Running the Tests

1. **Verify Setup**:
   ```bash
   python verify_vector_indexes.py
   ```
   This will check if the vector search indexes are properly configured.

2. **Run Test Workflow**:
   ```bash
   python run_simple_test.py
   ```
   This will:
   - Process 4-5 test jobs
   - Find top 4 resume matches per job
   - Validate matches using LLM
   - Store results in MongoDB
   - Generate a detailed test report

## Test Output

The test workflow generates:

1. **Console Output**:
   - Real-time progress updates
   - Summary of results
   - Individual job results
   - Final statistics

2. **JSON Results File**:
   - Detailed test results saved to `test_results_TIMESTAMP.json`
   - Includes all matches, scores, and validation results

3. **MongoDB Collections**:
   - Successful matches in `resume_job_matches`
   - Unmatched jobs in `unmatched_job_postings`
   - All test entries marked with `test_run: true`

## Understanding Results

The test workflow reports:

1. **Vector Search Performance**:
   - Number of jobs processed
   - Number of resumes found per job
   - Similarity scores for matches

2. **LLM Validation**:
   - Validation scores (0-100)
   - Detailed reasoning for each match
   - Best match selection

3. **Overall Statistics**:
   - Total matches attempted
   - Successful vs rejected matches
   - Success rate percentage

## Troubleshooting

Common issues and solutions:

1. **Vector Search Errors**:
   - Verify indexes exist and are properly configured
   - Check embedding field names match exactly
   - Ensure embeddings are present in documents

2. **LLM Validation Issues**:
   - Check Gemini API key is configured
   - Verify prompt format in workflow
   - Check response parsing logic

3. **MongoDB Connection**:
   - Verify connection string in `.env`
   - Check database and collection names
   - Ensure proper permissions

## Next Steps

After successful testing:

1. Review test results and adjust parameters if needed
2. Move to production workflow implementation
3. Set up monitoring and logging
4. Implement error handling and retries