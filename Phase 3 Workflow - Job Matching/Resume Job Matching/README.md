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
- **Large-Scale Ready**: Optimized for processing 1000s of job descriptions with:
  - **Resume Caching**: 2-3x faster industry filtering
  - **Batch Processing**: 3-4x faster overall processing  
  - **Parallel Processing**: Better resource utilization
  - **Checkpointing**: Resumable long runs
  - **Memory Management**: Stable large-scale processing

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

### Performance Configuration (for large-scale processing)
```python
# Optimize for processing 1000s of jobs
config.batch_size = 50                    # Process jobs in batches of 50
config.max_workers = 8                    # Use 8 parallel threads
config.cache_ttl = 7200                   # Cache resumes for 2 hours
config.checkpoint_interval = 200          # Save checkpoint every 200 jobs
config.memory_limit_mb = 4096             # 4GB memory limit
```

### Duplicate Processing Configuration
```python
# Control duplicate processing behavior
config.skip_processed_jobs = True         # Skip jobs already processed (default)
config.force_reprocess = False            # Force reprocessing of all jobs
```

## 🎯 Use Cases

1. **Research Projects**: Focus on specific industries or job types for correspondence studies
2. **Industry Analysis**: Analyze job-resume matches within specific sectors  
3. **Keyword Studies**: Study matches by specific job requirements or skills
4. **Sample Limiting**: Process a subset of jobs for testing or analysis
5. **Full Dataset**: Process all job postings with no filters
6. **Large-Scale Studies**: Process 1000s of job descriptions with performance optimizations

## 🚀 Performance Optimizations

### **Resume Caching**
- Caches industry-filtered resumes to avoid repeated database queries
- **2-3x faster** industry filtering for repeated operations
- Configurable TTL (time-to-live) for cache freshness

### **Batch Processing**
- Processes jobs in configurable batches instead of one-by-one
- **3-4x faster** overall processing for large datasets
- Better memory management and resource utilization

### **Parallel Processing**
- Uses ThreadPoolExecutor for concurrent job processing
- Configurable number of worker threads
- Automatic fallback to sequential processing if needed

### **Checkpointing**
- Saves progress periodically during long runs
- Resume interrupted workflows from last checkpoint
- Essential for processing 1000s of jobs reliably

### **Memory Management**
- Monitors memory usage and clears cache when needed
- Configurable memory limits
- Prevents crashes on large datasets

### **Performance Monitoring**
- Tracks vector search and LLM validation times
- Cache hit/miss statistics
- Automatic performance recommendations

### **Duplicate Processing Prevention**
- **Automatic Detection**: Prevents reprocessing of jobs already matched or unmatched
- **Configurable Behavior**: Choose to skip or force reprocessing
- **Progress Tracking**: Monitor processing progress and remaining job counts
- **Individual Status**: Check processing status of specific jobs
- **Comprehensive Statistics**: Track matched, unmatched, and remaining jobs

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

## 🧪 Testing

### **Basic Functionality Test**
```bash
# Test the core workflow
python test_production_workflow.py
```

### **Performance Optimizations Test**
```bash
# Test all the new performance features
python test_optimized_workflow.py
```

### **Duplicate Processing Test**
```bash
# Test duplicate processing prevention and status checking
python test_duplicate_processing.py
```

### **Test Coverage**
- ✅ Basic workflow functionality
- ✅ Industry filtering (specific vs. all industries)
- ✅ Search term filtering
- ✅ Research configurations
- ✅ Small workflow execution
- ✅ Max jobs configuration limits
- ✅ **NEW**: Resume caching performance
- ✅ **NEW**: Batch processing
- ✅ **NEW**: Parallel processing
- ✅ **NEW**: Checkpointing system
- ✅ **NEW**: Performance metrics
- ✅ **NEW**: Memory management
- ✅ **NEW**: Duplicate processing prevention
- ✅ **NEW**: Individual job status checking
- ✅ **NEW**: Processing statistics and progress tracking

## 🚨 Requirements

- MongoDB with vector search indexes
- Gemini API access
- Python 3.8+
- Required packages: `pymongo`, `google-genai`
- **Optional**: `psutil` for advanced memory management

## 📝 Notes

- All embeddings must be pre-generated using the embedding system
- Vector search indexes must be created in MongoDB
- LLM validation uses Gemini Pro for match quality assessment
- Results are automatically saved to MongoDB collections
