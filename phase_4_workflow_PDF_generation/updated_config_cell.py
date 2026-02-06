# Configuration Settings
# =====================

# Treatment Configuration
TREATMENT_TYPES = ['control', 'Type_I', 'Type_II', 'Type_III']

# Reprocessing Configuration
REPROCESS_ALREADY_PROCESSED = False  # Set to True to reprocess already processed files

# MongoDB Configuration
MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = "Resume_study"
COLLECTION_NAME = "n8n_resume_render_log"

# API Configuration - Load from .env file only
TEST_WEBHOOK_URL = os.getenv('TEST_WEBHOOK_URL')
PRODUCTION_WEBHOOK_URL = os.getenv('PRODUCTION_WEBHOOK_URL')
WEBHOOK_USERNAME = os.getenv('WEBHOOK_USERNAME')
WEBHOOK_PASSWORD = os.getenv('WEBHOOK_PASSWORD')

# Validate that all required environment variables are set
required_env_vars = {
    'TEST_WEBHOOK_URL': TEST_WEBHOOK_URL,
    'PRODUCTION_WEBHOOK_URL': PRODUCTION_WEBHOOK_URL,
    'WEBHOOK_USERNAME': WEBHOOK_USERNAME,
    'WEBHOOK_PASSWORD': WEBHOOK_PASSWORD,
    'MONGODB_URI': MONGODB_URI
}

missing_vars = [var for var, value in required_env_vars.items() if not value]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {missing_vars}")

AUTHORIZATION = (WEBHOOK_USERNAME, WEBHOOK_PASSWORD)

# Template Configuration
TEMPLATE_ASSIGNMENTS = {
    'control': {'template_id': '72b77b23d48f366e', 'markdown_template': 1},
    'Type_I': {'template_id': '73677b23d4896786', 'markdown_template': 2},
    'Type_II': {'template_id': '2ee77b23de5fc78e', 'markdown_template': 2},
    'Type_III': {'template_id': 'ca277b23d48328b0', 'markdown_template': 1}
}

print("Configuration Loaded:")
print(f"- Reprocess Already Processed: {REPROCESS_ALREADY_PROCESSED}")
print(f"- Treatment Types: {TREATMENT_TYPES}")
print(f"- MongoDB: {DB_NAME}.{COLLECTION_NAME}")
print(f"- Templates Configured: {len(TEMPLATE_ASSIGNMENTS)}")
print(f"- API Configuration: ✅ Loaded from .env file")
