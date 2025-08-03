# Simple Resume-Job Matching Test Workflow

This directory contains a test workflow for resume-job matching using MongoDB's vector search capabilities and Gemini Pro for validation.

## Overview

The workflow implements a two-stage matching process:
1. **Vector Search**: Find semantically similar resumes using MongoDB vector search
2. **LLM Validation**: Batch validate matches using Gemini Pro with comparative ranking

Results are stored in two collections:
- `resume_job_matches`: Valid matches (score ≥ 70)
- `unmatched_job_postings`: Rejected jobs with potential matches

## Prerequisites

Before running the test workflow, ensure you have:

1. **MongoDB Atlas Setup**:
   - Vector search enabled cluster
   - Vector search indexes:
     - `resume_embedding_index` on `Standardized_resume_data`
     - `job_embedding_index` on `job_postings`
   - Proper connection string in `.env`

2. **Python Environment**:
   - Python 3.8+
   - Required packages installed
   - Virtual environment activated

3. **API Keys**:
   - Gemini API key configured
   - MongoDB connection string in `.env`

## Running the Tests

```bash
python test_simple_matching_workflow.py
```

This will:
1. Load test jobs with embeddings
2. Find top 4 similar resumes per job
3. Perform batch LLM validation
4. Store results based on match quality

## Understanding Results

### 1. Vector Search Results
For each job, the system finds the top 4 similar resumes using:
- Cosine similarity on embeddings
- Initial filter: similarity score ≥ 0.3
- Normalized scores (0-1 range)

### 2. LLM Validation
The system sends all candidates to Gemini Pro for:
- Individual scoring (0-100)
- Comparative ranking
- Match quality summaries
- Best match selection

### 3. Storage Model

**Valid Matches** (score ≥ 70):
```json
{
    "job_posting_id": "...",
    "resume_id": "...",
    "title": "Senior Business Analyst",
    "company": "Amanst Inc",
    "description": "...",
    
    "file_id": "resume_123.pdf",
    "resume_data": {...},
    "key_metrics": {...},
    
    "semantic_similarity": 0.85,
    "match_score": 85,
    "match_summary": "Strong experience...",
    
    "matched_resumes": [
        {
            "file_id": "resume_123.pdf",
            "similarity_score": 0.85,
            "llm_score": 85,
            "rank": 1,
            "summary": "Strong match..."
        }
    ],
    
    "match_status": "TEST_VALIDATED"
}
```

**Unmatched Jobs** (score < 70):
```json
{
    "job_posting_id": "...",
    "title": "Senior SQL DBA",
    "company": "Realign",
    "description": "...",
    
    "matched_resumes": [
        {
            "file_id": "resume_456.pdf",
            "similarity_score": 0.75,
            "llm_score": 65,
            "rank": 1,
            "summary": "Lacks senior experience..."
        }
    ],
    
    "match_status": "TEST_REJECTED"
}
```

## Troubleshooting

### Vector Search Issues
1. **Index Missing**:
   ```bash
   # Check indexes
   db.Standardized_resume_data.getIndexes()
   db.job_postings.getIndexes()
   ```

2. **Embedding Issues**:
   - Verify embedding field names match exactly
   - Check embedding dimensions (should be 768)
   - Ensure embeddings are arrays of floats

### LLM Validation Issues
1. **API Errors**:
   - Check Gemini API key
   - Verify API quota/limits
   - Check response format

2. **Validation Logic**:
   - Review prompt structure
   - Check score thresholds
   - Verify JSON parsing

### MongoDB Connection
1. **Connection String**:
   - Check `.env` file
   - Verify cluster access
   - Check network connectivity

2. **Permissions**:
   - Verify read/write access
   - Check collection permissions
   - Verify vector search enabled

## Monitoring Results

1. **Console Output**:
   - Real-time progress
   - Match statistics
   - Error reporting

2. **MongoDB Queries**:
   ```javascript
   // Check valid matches
   db.resume_job_matches.find({"test_run": true})
   
   // Check unmatched jobs
   db.unmatched_job_postings.find({"test_run": true})
   
   // Get statistics
   db.resume_job_matches.countDocuments({"test_run": true})
   ```

## Next Steps

1. **Fine-tuning**:
   - Adjust similarity threshold
   - Tune LLM scoring criteria
   - Optimize batch sizes

2. **Production Setup**:
   - Set up monitoring
   - Implement error handling
   - Add cleanup procedures

3. **Enhancements**:
   - Add more validation criteria
   - Implement caching
   - Add statistical reporting