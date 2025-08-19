# Batch Embedding Modules

Scripts to generate vector embeddings for resumes and job postings stored in MongoDB.

## What These Modules Do

- **`batch_resume_embedding.py`** - Adds embeddings to existing resumes in the database
- **`batch_job_embedding.py`** - Adds embeddings to existing job postings in the database

## Quick Start

### 1. Setup (one-time)
```bash
cd libs
python setup_embedding_cache.py
```

### 2. Process Existing Resumes
```bash
cd "Phase 3 Workflow - Job Matching"
python batch_resume_embedding.py
```

### 3. Process Existing Jobs
```bash
cd "Phase 3 Workflow - Job Matching"
python batch_job_embedding.py
```

## What Happens

1. **Content Extraction** - Pulls key information from resumes/jobs (skills, experience, requirements)
2. **Embedding Generation** - Uses Gemini API to create semantic vectors
3. **Database Update** - Stores embeddings back in MongoDB documents
4. **Caching** - Saves API costs by reusing identical embeddings

## Configuration

Set these environment variables:
- `GEMINI_API_KEY` - Required for embedding generation
- `MONGODB_URI` - Required for database access

## Output

- Resumes get a `text_embedding` field
- Jobs get a `jd_embedding` field
- All embeddings are cached to avoid duplicate API calls

## Notes

- New resumes and jobs are automatically processed when added
- Batch processing handles existing documents
- Content is limited to 8000 characters for optimal embedding quality
- Includes progress tracking and error handling
