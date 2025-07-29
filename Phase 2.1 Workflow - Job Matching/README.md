# Phase 2.1 Workflow - Job Matching

This directory contains the job matching and embedding system for the resume parsing audit study. The system is organized into two main components: job scraping and batch processing.

## 📁 Directory Structure

```
Phase 2.1 Workflow - Job Matching/
├── Job Scraping Modules/          # Job scraping and data collection
├── Batch Processing Modules/      # Embedding generation and processing
├── data/                         # Data storage and cache
└── test_job_embedding_and_search.py  # Main testing script
```

## 🎯 System Overview

### Job Scraping Modules
- **job_scraper_integration.py**: Main job scraping integration script
- **config_job_scraper.py**: Configuration for job scraping
- **test_job_scraping.py**: Testing script for job scraping functionality
- **README.md**: Documentation for job scraping modules

### Batch Processing Modules
- **batch_job_embedding.py**: Batch processing for job embeddings
- **batch_resume_embedding.py**: Batch processing for resume embeddings
- **EMBEDDING_SYSTEM_DOCUMENTATION.md**: Detailed embedding system documentation

## 🚀 Quick Start

### 1. Test the System
```bash
python test_job_embedding_and_search.py
```

### 2. Generate Resume Embeddings
```bash
cd "Batch Processing Modules"
python batch_resume_embedding.py
```

### 3. Generate Job Embeddings
```bash
cd "Batch Processing Modules"
python batch_job_embedding.py
```

## 📊 Current Status

- **Resumes**: 254 total, 254 with embeddings (100% coverage)
- **Jobs**: 187 total, processing embeddings in batches
- **Embedding Model**: Gemini embedding-001 (768 dimensions)
- **Task Types**: 
  - Resumes: `RETRIEVAL_DOCUMENT`
  - Jobs: `RETRIEVAL_QUERY`

## 🔧 Key Features

- **Semantic Search**: Cosine similarity-based job-resume matching
- **Caching System**: MongoDB-based embedding cache to avoid duplicate API calls
- **Batch Processing**: Configurable batch sizes with rate limiting
- **Content Extraction**: Intelligent extraction of relevant content for embeddings
- **Error Handling**: Robust error handling and logging

## 📈 Performance Metrics

- **Embedding Generation**: ~8-10 seconds per document
- **Cache Hit Rate**: High efficiency for duplicate content
- **Similarity Scores**: Range 0.55-0.61 for relevant matches
- **API Usage**: Optimized with caching and batch processing

## 🎯 Use Cases

1. **Job-Resume Matching**: Find the best candidates for job postings
2. **Semantic Search**: Search resumes by job requirements
3. **Batch Processing**: Process large datasets efficiently
4. **Research Analysis**: Support correspondence studies on immigrant employment

## 📝 Notes

- All embeddings are 768-dimensional vectors from Gemini embedding-001
- Content extraction focuses on requirements, skills, and responsibilities
- System supports both individual testing and batch processing
- MongoDB integration for persistent storage and caching

## 🔗 Related Files

- **libs/gemini_processor.py**: Core embedding generation functionality
- **libs/text_extraction.py**: Content extraction utilities
- **libs/mongodb.py**: Database operations and caching 