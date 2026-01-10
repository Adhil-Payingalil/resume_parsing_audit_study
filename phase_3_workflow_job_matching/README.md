# Phase 3: Job Matching Workflow

This directory contains the tools and workflows for matching resumes to job postings. The logic is divided into **Embeddings** (preparing data) and **Matching** (finding matches).

## Directory Structure

*   `src/embeddings/`: Scripts to generate vector embeddings for jobs and resumes.
    *   `batch_job_embedder.py`: Embeds standard scraped jobs.
    *   `batch_resume_embedder.py`: Embeds standardized resumes.
    *   `greenhouse_job_embedder.py`: Embeds Greenhouse job postings.
*   `src/matching/`: Core matching logic.
    *   `standard_matcher.py`: Generalized matching workflow.
    *   `greenhouse_matcher.py`: Specialized workflow for Greenhouse data.
*   `configs/`: Configuration files for each workflow.
*   `docs/`: Legacy documentation.
*   `tests/`: Test scripts.

## Usage

### 1. Job Matching (Production)

To run the **Greenhouse** matching workflow (recommended for current operations):
```bash
python run_greenhouse_matching.py
```
This script replicates the functionality of the old `run_greenhouse_workflow.py`.

To run the **Standard** matching workflow:
```bash
python run_standard_matching.py
```

### 2. Embedding Generation (Batch)

To update embeddings for jobs or resumes, run the scripts in `src/embeddings/` directly (or creating a runner if needed).
Example:
```bash
python src/embeddings/batch_job_embedder.py
```

## Configuration

Edit `configs/greenhouse_config.py` or `configs/config.py` to adjust thresholds, batch sizes, and model parameters.
