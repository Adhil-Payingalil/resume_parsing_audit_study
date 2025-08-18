# Resume-Job Matching Workflow

A production-ready system for matching resumes to job postings using MongoDB vector search and LLM validation. **Simplified configuration** with just 3 essential filters. Designed for research projects and production use.

## 🚀 Quick Start

### 1. Test the System
```bash
python test_production_workflow.py
```

### 2. Run Production Workflow
```bash
python run_production_workflow.py
```

### 3. Use Custom Configuration
```python
from config import Config
from resume_job_matching_workflow import ResumeJobMatchingWorkflow

# Create custom configuration
config = Config()
config.industry_prefixes = ["tech", "health"]
config.search_terms = ["python", "data analyst"]

# Run workflow
with ResumeJobMatchingWorkflow(config) as workflow:
    results = workflow.run_workflow(max_jobs=100)
```

## 🔧 Key Features

- **Two-Stage Filtering**: Fast industry filtering + optimized vector search for maximum performance
- **Simple Filtering**: Just set industry prefixes and search terms - no complex configuration needed
- **MongoDB Vector Search**: Fast semantic similarity matching using native MongoDB indexes
- **LLM Validation**: AI-powered match quality assessment using Gemini Pro
- **Performance Optimized**: MongoDB indexes for lightning-fast filtering and early exit
- **Easy to Use**: Process all jobs or limit by number - your choice
- **Research Ready**: Perfect for correspondence studies and research projects

## 📁 Files

- **`config.py`**: Configuration management with filtering options
- **`resume_job_matching_workflow.py`**: Main production workflow class
- **`run_production_workflow.py`**: Production runner with example scenarios
- **`test_production_workflow.py`**: Test script to verify functionality


## ⚙️ Configuration Options

The configuration is **super simple** - just three main options:

### 1. Industry Prefixes (Optional)
```python
# Filter resumes by industry prefix from Standardized_resume_data
config.industry_prefixes = ["tech", "health", "finance"]

# Leave empty to include all industries
```

### 2. Search Terms (Optional)
```python
# Filter jobs by predefined search_term field values
config.search_terms = ["Data Analyst", "Software Engineer", "Project Manager"]

# Leave empty to include all jobs
```

### 3. Job Limit (Optional)
```python
# Limit number of jobs to process
config.max_jobs = 100

# Leave as None to process all matching jobs
```

### Complete Example
```python
from config import Config

# Focus on tech industry, Software Engineer jobs, max 50 jobs
config = Config()
config.industry_prefixes = ["tech"]
config.search_terms = ["Software Engineer", "Full Stack Developer"]
config.max_jobs = 50
```

## 🎯 Use Cases

1. **Research Projects**: Focus on specific industries or job types for correspondence studies
2. **Industry Analysis**: Analyze job-resume matches within specific sectors  
3. **Keyword Studies**: Study matches by specific job requirements or skills
4. **Sample Limiting**: Process a subset of jobs for testing or analysis
5. **Full Dataset**: Process all job postings with no filters

## 📊 Output

The workflow generates:
- **Valid Matches**: Stored in `resume_job_matches` collection
- **Unmatched Jobs**: Stored in `unmatched_job_postings` collection
- **Detailed Results**: JSON files with comprehensive matching data
- **Statistics**: Workflow performance and database metrics

## 🔍 Example Scenarios

### Research Scenario
```python
from config import get_research_config

config = get_research_config()
# Focuses on Technology, Healthcare, Finance
# Engineering and data science roles
# Mid to senior experience levels
```

### Broad Matching
```python
from config import get_broad_matching_config

config = get_broad_matching_config()
# Processes all industries
# Lower thresholds for broader matching
# Higher candidate counts
```

### Custom Configuration
```python
from config import Config

config = Config()
config.industry_prefixes = ["tech", "finance"]
config.search_terms = ["Data Analyst", "Business Analyst"]
config.max_jobs = 100
```

## 🚨 Requirements

- MongoDB with vector search indexes
- Gemini API access
- Python 3.8+
- Required packages: `pymongo`, `google-genai`

## 📝 Notes

- All embeddings must be pre-generated using the embedding system
- Vector search indexes must be created in MongoDB
- LLM validation uses Gemini Pro for match quality assessment
- Results are automatically saved to MongoDB collections
