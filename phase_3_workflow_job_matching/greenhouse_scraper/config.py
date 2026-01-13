import os
from pathlib import Path
from dotenv import load_dotenv

# Calculate Project Root (3 levels up from this file)
# File is in: phase_3_workflow_job_matching/greenhouse_scraper/config.py
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables from Root .env
load_dotenv(BASE_DIR / ".env", override=True)

# Centralized Paths
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = DATA_DIR / "logs" / "greenhouse_scraper"
SCRAPED_DATA_DIR = DATA_DIR / "scraped_jobs"
CONTEXT_DIR = DATA_DIR / "browser_context"

# Ensure directories exist
LOGS_DIR.mkdir(parents=True, exist_ok=True)
SCRAPED_DATA_DIR.mkdir(parents=True, exist_ok=True)
CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

# General Configuration
CONTEXT_FILE = CONTEXT_DIR / "greenhouse_context.json"

# Jina AI Configuration (for Description Extraction)
JINAAI_API_KEY = os.getenv("JINAAI_API_KEY")
JINA_BASE_URL = "https://r.jina.ai/"
RATE_LIMIT_DELAY = 0.5
BATCH_SIZE = 10
MAX_RETRIES = 4
TIMEOUT = 60

# AgentQL / Playwright Configuration (for Listing Scraping)
AGENTQL_API_KEY = os.getenv("AGENTQL_API_KEY")
if AGENTQL_API_KEY:
    os.environ["AGENTQL_API_KEY"] = AGENTQL_API_KEY

GREENHOUSE_URL = "https://my.greenhouse.io"
JOBS_URL = "https://my.greenhouse.io/jobs"
MAX_SEE_MORE_CLICKS = 60

# MongoDB Configuration
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "Resume_study")
MONGODB_COLLECTION = "Job_postings_greenhouse"

# Job Filter for description_extractor.py
DEFAULT_JOB_FILTER = {
    "cycle": 0,
    "link_type": "greenhouse",
    "unsupported_input_fields": False
}

# Job Filter for verify_required_fields.py
DEFAULT_VERIFICATION_FILTER = {
    "cycle": 0,
    "link_type": "greenhouse"
}
