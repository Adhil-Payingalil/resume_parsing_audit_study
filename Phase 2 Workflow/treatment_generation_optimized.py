# treatment_generation_script.py - OPTIMIZED VERSION
#
# Description:
# This script automates the process of generating treated resumes for a correspondence study.
# It reads standardized "control" resumes from a MongoDB collection, applies various
# treatments (Canadian Education, Canadian Work Experience), validates the output using
# cosine similarity, and saves the final, treated resumes to a new collection.
#
# Workflow for each source resume:
# 1. Fetch a standardized resume from the 'Standardized_resume_data' collection.
# 2. Randomly select two Canadian Education (CEC) and two Canadian Work (CWE) treatment.
# 3. Generate 4 versions of the resume:
#    - Control (rephrased summary/highlights only)
#    - Treatment I (rephrased + CEC)
#    - Treatment II (rephrased + CWE)
#    - Treatment III (rephrased + CEC + CWE)
# 4. For each generation, validate the rephrasing with a focused cosine similarity score.
# 5. For each generation, generate a list of similar companies to the original resume's work experience.
# 5. Save the 4 generated documents as separate entries in the 'Treated_resumes' collection as seperate documents with the same metadata.

# OPTIMIZATIONS:
# - Use CSV files instead of Excel for faster loading
# - Lazy load SentenceTransformer model only when needed
# - Add timing logs to identify bottlenecks
# - Optimize prompt template loading
# - Keep UI validation intact

# ═══════════════════════════════════════════════════════════════════════════════
# IDE CONFIGURATION - Set these when running from IDE
# ═══════════════════════════════════════════════════════════════════════════════
# HOW TO USE:
# 1. Set RUN_FROM_IDE = True
# 2. Configure IDE_CONFIG below with your sector and files
# 3. Hit Run in your IDE (F5 or right-click → Run)
# 4. No command-line arguments needed!
#
# Examples:
#   - Single file:   'files': ['ITC resume 16.pdf']
#   - Multiple:      'files': ['ITC resume 16.pdf', 'ITC resume 17.pdf']
#   - All in sector: 'files': None
# ═══════════════════════════════════════════════════════════════════════════════

RUN_FROM_IDE = True  # ← Set to False for command-line mode, True for IDE mode

# Settings when RUN_FROM_IDE = True
IDE_CONFIG = {
    'sector': 'MSfE',  # Industry sector (ITC, CCC, CHC, DMC, EEC, FSC, LC, MSfE, PME, SCC)
    'files': ['MSfE resume 17.pdf','MSfE resume 18.pdf']  # Specific files to process, or None for all files
    # 'files': None,  # Uncomment to process ALL files in the sector
}

# ═══════════════════════════════════════════════════════════════════════════════

import sys
import os
sys.path.append('..')
sys.path.append('../libs')

import os
import sys
import time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from libs.mongodb import get_all_file_ids,_get_mongo_client ,get_document_by_fileid, _clean_raw_llm_response
from libs.gemini_processor import GeminiProcessor
from libs.text_editor_app import TextEditorDialog # Custom class for text editor - company research
from PySide6.QtWidgets import QApplication # For the text editor dialog
from utils import get_logger
import json
import copy # Helper, to create deep copies
import datetime
import random # for treatment randomization
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity # Calculate distance between two vectors (sets of words)
import argparse # To enter the command line arguments

logger = get_logger(__name__)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Handle IDE vs Command Line mode
if RUN_FROM_IDE:
    # Use IDE configuration
    logger.info("Running in IDE mode with predefined configuration")
    SECTOR = str.upper(IDE_CONFIG['sector']).strip()
    SPECIFIC_FILES = IDE_CONFIG.get('files', None)
else:
    # Use command line arguments
    parser = argparse.ArgumentParser(description="Generate treated resumes for a correspondence study.")
    parser.add_argument("--sector", type=str, required=True, help="Industry prefix as in the mongoDB (all caps)")
    parser.add_argument("--files", type=str, nargs='+', help="Optional: A list of specific file IDs to process (e.g., ITC-01.pdf ITC-02.pdf).")
    args = parser.parse_args()
    
    SECTOR = str.upper(args.sector).strip()
    SPECIFIC_FILES = args.files

# MongoDB configuration
MONGO_CLIENT = _get_mongo_client()
DB_NAME = "Resume_study"
SOURCE_COLLECTION_NAME = "Standardized_resume_data"
TARGET_COLLECTION_NAME = "Treated_resumes"

# Gemini model configuration
REFINER_GEMINI_MODEL_NAME = "gemini-2.5-pro"
RESEARCH_GEMINI_MODEL_NAME = "gemini-2.5-pro" #gemini-2.5-pro
TREATMENT_GEMINI_MODEL_NAME = "gemini-2.5-pro"
GEMINI_TEMPERATURE = 0.6

BASE_PROMPT_TEMPLATE_PATH = os.path.join(SCRIPT_DIR, "Prompts", "prompt_treatment_generation.md")
COMPANY_RESEARCH_PROMPT_TEMPLATE_PATH = os.path.join(SCRIPT_DIR, "Prompts", "prompt_similar_company_generation.md")
CONTROL_REFINER_PROMPT_TEMPLATE_PATH = os.path.join(SCRIPT_DIR, "Prompts", "prompt_control_refiner.md")
MAX_RETRIES = 2

# Rate limiting configuration to prevent API overload
DELAY_BETWEEN_FILES = 3.0  # Seconds to wait between processing different files
DELAY_AFTER_COMPANY_RESEARCH = 2.0  # Seconds to wait after company research API call
DELAY_AFTER_CONTROL_REFINER = 2.0  # Seconds to wait after control refiner API call
DELAY_AFTER_TREATMENT_GENERATION = 1.5  # Seconds to wait after each treatment generation
# API retry configuration (passed to generate_content)
API_INITIAL_RETRY_DELAY = 5.0  # Initial delay for exponential backoff (seconds)
API_MAX_RETRY_DELAY = 120.0  # Maximum delay between retries (seconds)
STYLE_MODIFIERS = [
    "using strong, action-oriented verbs and focusing on quantifiable outcomes",
    "using a direct, concise, and professional tone, prioritizing clarity and brevity",
    "by emphasizing collaborative efforts and cross-functional teamwork",
    "by describing the technical aspects of the work with more precision and detail",
    "by framing the accomplishments as a narrative of challenges, actions, and results"
]

logger.info("=" * 80)
logger.info("INITIALIZATION PHASE - Starting...")
init_start_time = time.time()

# 2. Initialize the GeminiProcessor
logger.info("Initializing Gemini models...")
model_init_start = time.time()

control_refiner_model = GeminiProcessor(
    model_name=REFINER_GEMINI_MODEL_NAME,
    temperature=GEMINI_TEMPERATURE,
    enable_google_search=False
)
control_refiner_prompt = control_refiner_model.load_prompt_template(prompt_file_path=CONTROL_REFINER_PROMPT_TEMPLATE_PATH)

treatment_model = GeminiProcessor(
    model_name=TREATMENT_GEMINI_MODEL_NAME,
    temperature=GEMINI_TEMPERATURE,
    enable_google_search=False
)
treatment_prompt = treatment_model.load_prompt_template(prompt_file_path=BASE_PROMPT_TEMPLATE_PATH)

company_research_model = GeminiProcessor(
    model_name=RESEARCH_GEMINI_MODEL_NAME,
    temperature=GEMINI_TEMPERATURE,
    enable_google_search=True
)
company_research_prompt = company_research_model.load_prompt_template(prompt_file_path=COMPANY_RESEARCH_PROMPT_TEMPLATE_PATH)

logger.info(f"Gemini models initialized in {time.time() - model_init_start:.2f}s")

# Treatment file paths - OPTIMIZED: Use CSV instead of Excel
logger.info("Loading treatment data from CSV files...")
csv_load_start = time.time()

TREATMENT_CEC_FILE = os.path.join(SCRIPT_DIR, "Education_treatment_final.csv")
TREATMENT_CWE_FILE = os.path.join(SCRIPT_DIR, "Work_experience_final.csv")

# Load treatment data from CSV files in pandas DataFrames (much faster than Excel)
cec_treatment_df = pd.read_csv(TREATMENT_CEC_FILE)
cec_treatment_df = cec_treatment_df[cec_treatment_df['sector'] == SECTOR].reset_index(drop=True)
cwe_treatment_df = pd.read_csv(TREATMENT_CWE_FILE)
cwe_treatment_df = cwe_treatment_df[cwe_treatment_df['sector'] == SECTOR].reset_index(drop=True)

logger.info(f"Treatment data loaded in {time.time() - csv_load_start:.2f}s")
logger.info(f"Found {len(cec_treatment_df)} CEC treatments and {len(cwe_treatment_df)} CWE treatments for sector {SECTOR}")

# OPTIMIZED: Lazy load the similarity model only when needed
SIMILARITY_MODEL = None
FOCUSED_SIMILARITY_THRESHOLD = 0.60

def get_similarity_model():
    """Lazy load the SentenceTransformer model only when needed."""
    global SIMILARITY_MODEL
    if SIMILARITY_MODEL is None:
        logger.info("Loading SentenceTransformer model (first use)...")
        model_load_start = time.time()
        from sentence_transformers import SentenceTransformer
        SIMILARITY_MODEL = SentenceTransformer(
            os.path.join(SCRIPT_DIR, "models", "all-MiniLM-L6-v2")
        )
        logger.info(f"SentenceTransformer model loaded in {time.time() - model_load_start:.2f}s")
    return SIMILARITY_MODEL

logger.info(f"INITIALIZATION PHASE completed in {time.time() - init_start_time:.2f}s")
logger.info("=" * 80)

############################ ------------ Helper Functions ------------ ############################

def is_valid_resume_data(data: dict, label: str, treatment: str, file: str, retry_count: int) -> bool:
    if not data or not isinstance(data, dict):
        logger.error(f"Invalid {label} (not a dict) for treatment {treatment} in file {file} (attempt {retry_count + 1}).")
        return False
    if not data.get('resume_data') or not isinstance(data['resume_data'], dict):
        logger.error(f"Missing or invalid 'resume_data' in {label} for treatment {treatment} in file {file} (attempt {retry_count + 1}).")
        return False
    return True

def extract_rephrased_text(resume_data, skip_first_job=False):
    """
    Extracts text from summary and work experience highlights for similarity comparison.
    
    Args:
        resume_data: The resume data dictionary
        skip_first_job: If True, skip the first work_experience entry (used for Type_II/Type_III
                       treatments where the first job is the new Canadian work experience)
    
    Returns:
        Combined text string of summary + highlights
    """
    text_parts = []
    try:
        if 'basics' in resume_data and 'summary' in resume_data['basics']:
            text_parts.append(resume_data['basics']['summary'])
        if 'work_experience' in resume_data:
            work_exp = resume_data['work_experience']
            # Skip first job if it's a treatment addition (Canadian work experience)
            start_idx = 1 if skip_first_job else 0
            for job in work_exp[start_idx:]:
                if 'highlights' in job and isinstance(job['highlights'], list):
                    text_parts.append(" ".join(job['highlights']))
        return " ".join(text_parts)
    except Exception as e:
        logger.error(f"Error extracting rephrased text from resume_data: {e}")
        return ""

def calculate_focused_similarity(control_resume_data, treated_resume_data, treatment_type=None):
    """
    Calculate cosine similarity between control and treated resume text.
    
    Args:
        control_resume_data: The control resume data
        treated_resume_data: The treated resume data
        treatment_type: The type of treatment ("Type_I", "Type_II", "Type_III")
                       Used to determine if we should skip treatment additions
    
    Returns:
        Similarity score (0.0 to 1.0) or 'error' if calculation fails
    """
    try:
        similarity_start = time.time()
        
        # For Type_II and Type_III, skip the first job in treated resume
        # because it's the NEW Canadian work experience (not a rephrasing of original content)
        skip_first_job = treatment_type in ["Type_II", "Type_III"]
        
        control_text = extract_rephrased_text(control_resume_data, skip_first_job=False)
        treated_text = extract_rephrased_text(treated_resume_data, skip_first_job=skip_first_job)
        
        if not control_text or not treated_text:
            logger.warning("Empty text extracted for similarity comparison")
            return 0.0
        
        if skip_first_job:
            logger.info(f"Similarity check for {treatment_type}: Excluding first job (Canadian work experience treatment)")
        
        # Get the model (lazy loaded)
        model = get_similarity_model()
        
        control_embedding = model.encode(control_text)
        treated_embedding = model.encode(treated_text)
        score = cosine_similarity([control_embedding], [treated_embedding])[0][0]
        
        logger.debug(f"Similarity calculation took {time.time() - similarity_start:.2f}s")
        return score
    except Exception as e:
        import traceback
        logger.error(f"Error while calculating the focused similarity score: {e}\n{traceback.format_exc()}")
        return 'error'

def remove_north_american_elements(source_resume_data, control_refiner_model=control_refiner_model, control_refiner_prompt=control_refiner_prompt):
    """
    Removes North American elements from the resume data, such as company names and locations.
    
    Args:
        source_resume_data (dict): The original resume data.
    
    Returns:
        dict: The modified resume data with North American elements removed.
    
    Raises:
        Exception: If API call fails (including rate limits)
    """
    refiner_start = time.time()
    control_refiner_prompt_filled = control_refiner_prompt.replace('{JSON_resume_object}', str(source_resume_data))
    
    try:
        # generate_content now handles retries with exponential backoff
        response = company_research_model.generate_content(
            prompt=control_refiner_prompt_filled,
            max_retries=5,
            initial_retry_delay=API_INITIAL_RETRY_DELAY,
            max_retry_delay=API_MAX_RETRY_DELAY
        )
        llm_response = _clean_raw_llm_response(response.text)
        logger.info(f"Control refiner completed in {time.time() - refiner_start:.2f}s")
        return llm_response
    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
            logger.error("Rate limit exceeded after all retry attempts. Please wait a few minutes before retrying.")
            logger.error("Gemini API free tier limit: 2 requests per minute for gemini-2.5-pro")
        elif "503" in error_str or "overloaded" in error_str.lower():
            logger.error("Service is overloaded. Please try again later.")
        logger.error(f"Control refiner failed after retries: {e}")
        raise

def _extract_company_and_position_list(source_resume_data):
    """
    Extracts company names, positions, and locations from the work experience section.

    Args:
        source_resume_data (dict): Resume data dictionary.

    Returns:
        dict: Dictionary with work_experience_entries list containing company, position, and location.
    """
    # Handle multiple levels of nesting in the resume data structure
    # MongoDB can have: doc['resume_data']['resume_data']['work_experience']
    # or after processing: doc['resume_data']['work_experience']
    # or just: doc['work_experience']
    
    resume = source_resume_data
    
    # Check for double-nested structure (MongoDB format)
    if 'resume_data' in resume and isinstance(resume['resume_data'], dict):
        resume = resume['resume_data']
        # Check if there's another nested level
        if 'resume_data' in resume and isinstance(resume['resume_data'], dict):
            resume = resume['resume_data']
    
    work_history = resume.get('work_experience', [])
    
    # Log for debugging
    logger.info(f"Extracting companies and positions from {len(work_history)} work experience entries")
    
    # Collect company, position, and location for each job
    work_experience_entries = []
    for job in work_history:
        company = job.get('company')
        position = job.get('position')
        location = job.get('location')
        if company or position:  # At least company or position should exist
            work_experience_entries.append({
                'company': company,
                'position': position,
                'location': location
            })
            logger.info(f"  Found: {position} at {company}, {location}")
    
    if not work_experience_entries:
        logger.warning("No companies/positions found in work experience! This will cause the LLM to return an error.")
        logger.warning(f"Resume data structure - Top level keys: {list(source_resume_data.keys())}")
        logger.warning(f"Resume data structure - Current level keys: {list(resume.keys())}")
    
    return {
        'work_experience_entries': work_experience_entries
    }

# Keep old function for backward compatibility (if needed elsewhere)
def _extract_company_name_list(source_resume_data):
    """Legacy function - use _extract_company_and_position_list instead"""
    result = _extract_company_and_position_list(source_resume_data)
    # Convert to old format
    return {
        'company_location_pairs': [
            {'company': entry['company'], 'location': entry['location']}
            for entry in result['work_experience_entries']
        ]
    }

#old company research function, unused
def company_research(source_resume_data ,company_research_model=company_research_model, company_research_prompt=company_research_prompt):
    company_name_list = _extract_company_name_list(source_resume_data=source_resume_data)
    company_research_prompt_filled = company_research_prompt.replace('{company_names}', str(company_name_list))
    response = company_research_model.generate_content(prompt=company_research_prompt_filled)
    llm_response = _clean_raw_llm_response(response.text)
    return llm_response

def company_research_with_ui(source_resume_data ,company_research_model=company_research_model, company_research_prompt=company_research_prompt):
    """
    Performs company and position research, then opens a UI for validation and editing.
    Allows the user to retry the generation or accept the result.
    
    Returns a list of mappings with company AND position variations.
    """
    work_experience_data = _extract_company_and_position_list(source_resume_data=source_resume_data)
    final_prompt = company_research_prompt.replace('{company_names}', str(work_experience_data))

    while True: # This loop allows for retries
        # 1. Generate the content using the LLM
        research_start = time.time()
        try:
            # generate_content now handles retries with exponential backoff automatically
            raw_response = company_research_model.generate_content(
                prompt=final_prompt,
                max_retries=5,
                initial_retry_delay=API_INITIAL_RETRY_DELAY,
                max_retry_delay=API_MAX_RETRY_DELAY
            )
            llm_response = _clean_raw_llm_response(raw_response.text)
            logger.info(f"Company research generation took {time.time() - research_start:.2f}s")
        except Exception as e:
            error_str = str(e)
            logger.error(f"Company research failed after retries: {e}")
            if "503" in error_str or "overloaded" in error_str.lower():
                logger.error("Service is overloaded. Please try again later or wait a few minutes.")
            elif "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                logger.error("Rate limit exceeded. Please wait a few minutes before retrying.")
            
            # Ask user if they want to retry or cancel
            logger.warning("API call failed. You can choose to retry or cancel in the UI.")
            app = QApplication.instance() or QApplication(sys.argv)
            editor = TextEditorDialog(initial_text=f'API Error: {error_str}\n\nChoose "Retry" to attempt again or "Cancel" to exit.')
            status, _ = editor.run()
            
            if status == "retry":
                logger.info("User chose to retry after API error.")
                continue
            else:
                logger.info("User cancelled after API error.")
                sys.exit(1)
        
        llm_response_str = json.dumps(llm_response, indent=2)  # Convert to pretty JSON string for display
        logger.info("Content generated. Opening editor for validation...")
        
        # This is used for the editor dialog
        app = QApplication.instance() or QApplication(sys.argv) 
        # 2. Open the editor window and wait for the user
        editor = TextEditorDialog(initial_text=llm_response_str)
        status, final_text = editor.run()

        # 3. Handle the user's decision
        if status == "accepted":
            logger.info("Content accepted by user.")
            # Validate the final text
            try:
                final_text = json.loads(final_text)  # Ensure it's valid JSON
                logger.info("Final text is valid JSON. Returning the result.")
                return final_text
            except json.JSONDecodeError as e:
                logger.error(f'Invalid JSON format in final text while company generation: {e}')
                sys.exit(1)
        elif status == "retry":
            logger.info("User chose to retry. Regenerating company mappings")
            continue # Go to the next iteration of the while loop
        else: # 'cancelled'
            logger.info("\ncompany mapping generation cancelled by user.")
            sys.exit(1)

def replace_companies_and_positions(resume_data: dict,
                                    mappings: list[dict],
                                    treatment_type: str) -> dict:
    """
    Replaces both company names AND position titles in work_experience entries
    based on the specified treatment_type ("Type_I", "Type_II", "Type_III").

    Args:
        resume_data: Resume data dictionary
        mappings: List of mappings with company and position variations
        treatment_type: Type of treatment (Type_I, Type_II, Type_III)

    Returns:
        Modified resume_data dict with replaced companies and positions
    """
    if not resume_data or not isinstance(resume_data, dict):
        logger.error("Invalid resume_data provided. Expected a non-empty dictionary.")
        return resume_data
    if not mappings or not isinstance(mappings, list):
        logger.error("Invalid mappings provided. Expected a non-empty list of dictionaries.")
        return resume_data
    logger.debug(f"Starting company and position replacement for treatment: {treatment_type}")

    # Build lookup dict: {lowercase_original_company: {company: new_company, position: new_position}}
    lookup = {}
    for entry in mappings:
        orig_company = entry.get("Original_company")
        orig_position = entry.get("Original_position")
        
        if not orig_company:
            logger.warning("Found an entry with no 'Original_company' field. Skipping.")
            continue

        # Extract variations for this treatment type
        variations = entry.get("Variations", [])
        replacement = None
        
        for var_dict in variations:
            if treatment_type in var_dict:
                replacement = var_dict[treatment_type]
                break
        
        if not replacement:
            logger.warning(f"No '{treatment_type}' replacement found for '{orig_company}'. Skipping.")
            continue
        
        # Store the replacement (both company and position)
        lookup[orig_company.lower()] = {
            'company': replacement.get('company'),
            'position': replacement.get('position')
        }
        logger.debug(f"Mapped '{orig_company}' + '{orig_position}' → '{replacement.get('company')}' + '{replacement.get('position')}'")

    # Deep copy to avoid modifying original
    new_data = copy.deepcopy(resume_data)

    company_replacements = 0
    position_replacements = 0
    
    for exp in new_data.get("resume_data", {}).get("work_experience", []):
        orig_comp = exp.get("company", "")
        replacement = lookup.get(orig_comp.lower())

        if replacement:
            new_company = replacement.get('company')
            new_position = replacement.get('position')
            
            if new_company:
                logger.debug(f"Replacing company '{orig_comp}' → '{new_company}'")
                exp["company"] = new_company
                company_replacements += 1
            
            if new_position:
                orig_pos = exp.get("position", "")
                logger.debug(f"Replacing position '{orig_pos}' → '{new_position}'")
                exp["position"] = new_position
                position_replacements += 1
        else:
            logger.debug(f"No replacement found for company: '{orig_comp}' (keeping original)")

    logger.info(f"Replacement complete. Companies: {company_replacements}, Positions: {position_replacements}")
    return new_data

# Keep old function for backward compatibility
def replace_companies(resume_data: dict, company_mappings: list[dict], treatment_type: str) -> dict:
    """Legacy function - use replace_companies_and_positions instead"""
    return replace_companies_and_positions(resume_data, company_mappings, treatment_type)

def select_and_prepare_treatments(
    cec_treatment_df: pd.DataFrame,
    cwe_treatment_df: pd.DataFrame,
    source_resume_data: dict,
    treatment_prompt_template: str,
    style_modifiers: list[str]
):
    """
    Selects random treatments, assigns unique style modifiers, and prepares prompts
    for the 3 treated resume variations (Type I, Type II, Type III).

    The 'Control' version is the original source resume and is handled separately.

    Args:
        cec_treatment_df: DataFrame with Canadian Education treatments.
        cwe_treatment_df: DataFrame with Canadian Work Experience treatments.
        source_resume_data: The original resume data to be treated.
        treatment_prompt_template: Prompt template with placeholders for resume,
                                   treatment, and style modifier.
        style_modifiers: A list of style instructions for rephrasing.

    Returns:
        A dictionary where keys are treatment types ('Type_I', 'Type_II', 'Type_III')
        and values are dicts containing the final 'prompt' and 'treatment_applied' info.
        Returns None if treatments are unavailable.
    """
    if cec_treatment_df.empty or cwe_treatment_df.empty:
        logger.error("No treatments available for CEC or CWE.")
        return None

    # --- 1. Select all treatments needed for this run ---
    try:
        # Select two unique treatments for CEC and CWE
        cec_treatments = cec_treatment_df.sample(n=2, replace=False).to_dict('records')
        cwe_treatments = cwe_treatment_df.sample(n=2, replace=False).to_dict('records')

        # OPTIMIZED: Rename CSV columns to match JSON schema for LLM compatibility
        for treatment in cwe_treatments:
            # Map Position to position
            if 'Position' in treatment:
                treatment['position'] = treatment.pop('Position')
            
            # Map Name of Organization Providing Project to company (the actual organization)
            # IMPORTANT: We use the organization name, NOT the project title
            if 'Name of Organization Providing Project' in treatment:
                treatment['company'] = treatment.pop('Name of Organization Providing Project')
            
            # Remove 'Title of Experiential Learning Project' - we don't use this
            # This is the project description, not the company name
            if 'Title of Experiential Learning Project' in treatment:
                treatment.pop('Title of Experiential Learning Project')
            
            # Combine highlight_1, highlight_2, highlight_3 into 'highlights' array
            treatment['highlights'] = [
                treatment.pop(f'highlight_{i}') for i in range(1, 4) if f'highlight_{i}' in treatment
            ]
            
            # Map Duration to duration
            if 'Duration' in treatment:
                treatment['duration'] = treatment.pop('Duration')
            
            # Map Location (with trailing space) to location
            if 'Location ' in treatment:
                treatment['location'] = treatment.pop('Location ')
            
    except ValueError:
        logger.error("Not enough unique treatments available in the dataframes to sample.")
        return None

    # --- 2. Prepare for style assignment ---
    # We now need 3 unique styles for the 3 treated versions.
    if len(style_modifiers) < 3:
        logger.error("Not enough style modifiers to ensure unique styles for all treatments.")
        return None
    shuffled_styles = random.sample(style_modifiers, 3)

    # --- 3. Prepare prompts for each treatment type ---
    treatment_prompts = {}
    
    # Prepare the base prompt with the resume data, which is common to all versions
    base_prompt = treatment_prompt_template.replace(
        "{JSON_resume_object}", str(source_resume_data)
    )

    # a) Prepare "Type_I" (CEC)
    cec_treatment_idx = random.randint(0, 1)  # Randomly select one of the two CEC treatments
    cec_treatment = cec_treatments[cec_treatment_idx]  # Randomly select one of the two CEC treatments
    type_i_prompt = base_prompt.replace("{Treatment_object}", str(cec_treatment))
    type_i_prompt = type_i_prompt.replace("{treatment_type}", "Type_I")
    type_i_style_guide = shuffled_styles.pop()
    type_i_prompt = type_i_prompt.replace("{style_guide}", type_i_style_guide)
    treatment_prompts["Type_I"] = {
        "prompt": type_i_prompt,
        "style_guide": type_i_style_guide,
        "treatment_applied": {"Canadian_Education": cec_treatment}
    }
    cec_treatment_idx = 1 - cec_treatment_idx  # Get the other CEC treatment for Type III

    # b) Prepare "Type_II" (CWE)
    cwe_treatment_idx = random.randint(0, 1)
    cwe_treatment = cwe_treatments[cwe_treatment_idx]
    type_ii_prompt = base_prompt.replace("{Treatment_object}", str(cwe_treatment))
    type_ii_prompt = type_ii_prompt.replace("{treatment_type}", "Type_II")
    type_ii_style_guide = shuffled_styles.pop()
    type_ii_prompt = type_ii_prompt.replace("{style_guide}", type_ii_style_guide)
    treatment_prompts["Type_II"] = {
        "prompt": type_ii_prompt,
        "style_guide": type_ii_style_guide,
        "treatment_applied": {"Canadian_Work_Experience": cwe_treatment}
    }
    cwe_treatment_idx = 1 - cwe_treatment_idx  # Get the other CWE treatment for Type III

    # c) Prepare "Type_III" (CEC + CWE)
    # Use the *other* selected treatments to avoid overlap within a single resume set
    mixed_treatment_payload = {
        "task": "ADD_EDUCATION_AND_EXPERIENCE",
        "payload": {
            "education": cec_treatments[cec_treatment_idx],
            "experience": cwe_treatments[cwe_treatment_idx]
        }
    }
    type_iii_prompt = base_prompt.replace("{Treatment_object}", str(mixed_treatment_payload))
    type_iii_style_guide = shuffled_styles.pop()
    type_iii_prompt = type_iii_prompt.replace("{style_guide}", type_iii_style_guide)
    type_iii_prompt = type_iii_prompt.replace("{treatment_type}", "Type_III")
    treatment_prompts["Type_III"] = {
        "prompt": type_iii_prompt,
        "style_guide": type_iii_style_guide,
        "treatment_applied": {
            "Canadian_Education": cec_treatments[cec_treatment_idx],
            "Canadian_Work_Experience": cwe_treatments[cwe_treatment_idx]
        }
    }

    logger.info(f"Successfully prepared 3 unique treatment prompts for the resume.")
    return treatment_prompts

############################ ------------ Main code ------------ ############################

logger.info("=" * 80)
logger.info("FILE FETCHING PHASE - Starting...")
fetch_start = time.time()

# 1. Import all files from the source collection for the specified sector
if SPECIFIC_FILES:
    # If specific files are provided (via command line or IDE config), use that list
    valid_files = get_all_file_ids(db_name=DB_NAME, collection_name=SOURCE_COLLECTION_NAME, mongo_client=MONGO_CLIENT)
    sector_files = [f for f in SPECIFIC_FILES if f in valid_files]
    logger.info(f"Processing {len(sector_files)} specific files.")
else:
    # Otherwise, fall back to the original behavior: get all files for the sector
    logger.info(f"No specific files provided. Fetching all files for sector: {SECTOR}.")
    all_files = get_all_file_ids(
        db_name=DB_NAME,
        collection_name=SOURCE_COLLECTION_NAME,
        mongo_client=MONGO_CLIENT
    )
    sector_files = [f for f in all_files if SECTOR in f]


if not sector_files:
    logger.error(f"No files found for sector {SECTOR}. Exiting.")
    sys.exit(1)
logger.info(f"Found {len(sector_files)} files for sector: {SECTOR}")
logger.info(f"FILE FETCHING completed in {time.time() - fetch_start:.2f}s")
logger.info("=" * 80)

target_collection = MONGO_CLIENT[DB_NAME][TARGET_COLLECTION_NAME]

# main processing loop
error_files = []
failed_similarity_files = [] ##### FOR DEBUGGING AND QA 

logger.info("=" * 80)
logger.info("PROCESSING PHASE - Starting...")
processing_start = time.time()

for file_idx, file in enumerate(sector_files):
    file_start_time = time.time()
    logger.info("=" * 80)
    logger.info(f"Processing file {file_idx + 1}/{len(sector_files)}: {file}")
    logger.info("-" * 80)
    
    # Add delay between files (except first one) to respect rate limits
    if file_idx > 0:
        logger.info(f"Rate limiting: Waiting {DELAY_BETWEEN_FILES}s before processing next file...")
        time.sleep(DELAY_BETWEEN_FILES)

    try:
        # Building the final document structure, initializing empty doc with metadata
        file_data = get_document_by_fileid(
            db_name=DB_NAME,
            collection_name=SOURCE_COLLECTION_NAME,
            file_id=file,
            mongo_client=MONGO_CLIENT
        )
        # Filter the resume data for the current file
        source_resume_data = file_data.get('resume_data', {})
        if not source_resume_data:
            logger.error(f"No resume data found for file {file}. Skipping.")
            error_files.append(file)
            continue

        documents_to_save = []
        common_metadata = {
            'original_file_id': file,
            'industry_prefix': file_data.get('industry_prefix'),
            'file_size_bytes': file_data.get('file_size_bytes'),
            'source_file_hash': file_data.get('file_hash'),
        }
        
        # IMPORTANT: Extract companies BEFORE removing North American elements
        # The control refiner will remove/modify company names, so we need the original data
        logger.info("Step 1/4: Extracting original company names...")
        original_resume_data = source_resume_data  # Keep a reference to original
        company_mappings = company_research_with_ui(
            source_resume_data=original_resume_data
        )
        
        # Rate limiting: Wait after company research API call
        if DELAY_AFTER_COMPANY_RESEARCH > 0:
            logger.debug(f"Rate limiting: Waiting {DELAY_AFTER_COMPANY_RESEARCH}s after company research...")
            time.sleep(DELAY_AFTER_COMPANY_RESEARCH)
        
        if not company_mappings or not isinstance(company_mappings, list):
            # Check for placeholder company names even if it's a string or malformed input
            if "place holder" in str(company_mappings).lower():
                logger.error(f"Company mappings for file {file} contain company place holders (fake names). Please check the file and try again.")
                placeholder_file = "CONTAINS FAKE COMPANY NAMES: " + str(file)
                error_files.append(placeholder_file)
                continue
            logger.error(f"Invalid company mappings for file {file}. Skipping.")
            error_files.append(file)
            continue
        
        logger.info("Step 2/4: Removing North American elements...")
        source_resume_data = remove_north_american_elements(
            source_resume_data=source_resume_data,
            control_refiner_model=control_refiner_model,
            control_refiner_prompt=control_refiner_prompt
        )
        
        # Rate limiting: Wait after control refiner API call
        if DELAY_AFTER_CONTROL_REFINER > 0:
            logger.debug(f"Rate limiting: Waiting {DELAY_AFTER_CONTROL_REFINER}s after control refiner...")
            time.sleep(DELAY_AFTER_CONTROL_REFINER)
        
        
        control_resume_target_collection = {
                **common_metadata, # Add the common data
                "document_id": f"{file}_control",
                "treatment_type": "control",
                "generation_timestamp": datetime.datetime.now(),
                "validation": {
                    "focused_similarity_score": "",
                    "passed_threshold": "N/A"
                },
                "treatment_applied": "N/A",
                "resume_data": source_resume_data
        }
        documents_to_save.append(control_resume_target_collection)

        logger.info("Step 3/4: Preparing treatment prompts...")
        treatment_prompts = select_and_prepare_treatments(
            cec_treatment_df,
            cwe_treatment_df,
            source_resume_data,
            treatment_prompt_template=treatment_prompt,
            style_modifiers=STYLE_MODIFIERS
        )

        if not treatment_prompts:
            logger.error(f"No treatments available for file {file}. stopping flow")
            sys.exit(1)

    except Exception as e:
        import traceback
        logger.error(f"Error in the control generation, or prompt generation for {file}: {e}\n{traceback.format_exc()}")
        error_files.append(file)
        continue
        
    try:
        logger.info("Step 4/4: Generating treated resumes...")
        for idx, (key, value) in enumerate(treatment_prompts.items(), 1):
            logger.info(f"  Treatment {idx}/3: Generating {key}...")
            retry_count = 0
            focused_similarity_score = 0.0
            treated_resume_data = None
            
            while retry_count < MAX_RETRIES:
                treatment_gen_start = time.time()
                try:
                    # generate_content now handles retries with exponential backoff automatically
                    response = treatment_model.generate_content(
                        prompt=value['prompt'],
                        max_retries=5,
                        initial_retry_delay=API_INITIAL_RETRY_DELAY,
                        max_retry_delay=API_MAX_RETRY_DELAY
                    )
                    if not response or not response.text:
                        logger.error(f"Failed to generate content for treatment {key} in file {file} (attempt {retry_count+1}).")
                        retry_count += 1
                        continue
                except Exception as e:
                    error_str = str(e)
                    logger.error(f"API error during treatment generation for {file}_{key} (attempt {retry_count+1}/{MAX_RETRIES}): {e}")
                    if "503" in error_str or "overloaded" in error_str.lower():
                        logger.warning("Service is overloaded. Will retry after delay...")
                    elif "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                        logger.warning("Rate limit exceeded. Will retry after delay...")
                    
                    retry_count += 1
                    if retry_count < MAX_RETRIES:
                        # Additional delay before retry (on top of what generate_content already did)
                        delay = min(5.0 * (2 ** (retry_count - 1)), 30.0)
                        logger.info(f"Waiting {delay:.1f}s before retrying treatment generation...")
                        time.sleep(delay)
                    continue
                    
                logger.info(f"    LLM generation took {time.time() - treatment_gen_start:.2f}s")
                
                # Rate limiting: Wait after each treatment generation
                if DELAY_AFTER_TREATMENT_GENERATION > 0:
                    logger.debug(f"Rate limiting: Waiting {DELAY_AFTER_TREATMENT_GENERATION}s after treatment generation...")
                    time.sleep(DELAY_AFTER_TREATMENT_GENERATION)
                
                # Clean the raw response
                treated_resume_data = _clean_raw_llm_response(response.text)
                # Validate the rephrasing with cosine similarity
                if not is_valid_resume_data(treated_resume_data, "treated resume", key, file, retry_count):
                    retry_count += 1
                    logger.error(f"The model returned invalid treated resume data for {file}_{key}")
                    continue
                if not is_valid_resume_data(source_resume_data, "source resume", key, file, retry_count):
                    retry_count += 1
                    logger.error(f"The source resume data seems corrupted for {file}")
                    continue
                    
                try:
                    focused_similarity_score = calculate_focused_similarity(
                        source_resume_data['resume_data'], 
                        treated_resume_data['resume_data'],
                        treatment_type=key  # Pass treatment type to exclude new work experience for Type_II/Type_III
                    )
                
                    focused_similarity_score = float(focused_similarity_score)
                    ########## FOR DEBUGGING AND SIMILARITY TEST
                    if focused_similarity_score < 0.8:
                        logger.debug(f'Failed the 0.8 similarity test at score: {focused_similarity_score}')
                        if file not in failed_similarity_files:
                            failed_similarity_files.append(file)

                except Exception as e:
                    logger.error(f"Could not convert similarity score to float: {focused_similarity_score} ({e})")
                    focused_similarity_score = 0.0
                    
                if focused_similarity_score >= FOCUSED_SIMILARITY_THRESHOLD:
                    logger.info(f"    Similarity score: {focused_similarity_score:.3f} (PASSED)")
                    break
                else:
                    logger.warning(f"    Similarity score: {focused_similarity_score:.3f} (LOW - attempt {retry_count+1}/{MAX_RETRIES})")
                    retry_count += 1
                    
            if focused_similarity_score < FOCUSED_SIMILARITY_THRESHOLD:
                logger.error(f"Failed to achieve desired similarity score for treatment {key} in file {file} after {MAX_RETRIES} attempts.")
                error_files.append(file)
                break

            treated_resume_data = replace_companies(
                resume_data=treated_resume_data,
                company_mappings=company_mappings,
                treatment_type=key
            )

            final_doc_for_this_version = {
                **common_metadata, # Add the common data
                "document_id": f"{file.replace('.pdf', '')}_{key}",
                "treatment_type": key,
                "generation_timestamp": datetime.datetime.now(),
                "validation": {
                    "focused_similarity_score": focused_similarity_score,
                    "passed_threshold": True 
                },
                "style_guide": value['style_guide'],
                "treatment_applied": value['treatment_applied'],
                "resume_data": treated_resume_data
            }
            documents_to_save.append(final_doc_for_this_version)
            logger.info(f"  -> Successfully prepared '{key}'")
            
    except Exception as e:
        import traceback
        logger.error(f"Error in the inner loop for {file}: {e}\n{traceback.format_exc()}")
        error_files.append(file)

    # If any error occurred for this file, skip saving
    if file in error_files:
        logger.warning(f"Skipping saving for file {file} due to errors.")
        continue

    if documents_to_save:
        try:
            save_start = time.time()
            target_collection.insert_many(documents_to_save)
            logger.info(f"Successfully saved {len(documents_to_save)} documents to MongoDB in {time.time() - save_start:.2f}s")
        except Exception as e:
            import traceback
            logger.error(f"Error saving documents for file {file}: {e}\n{traceback.format_exc()}")
            error_files.append(file)
    else:
        logger.error(f"No documents to save for file {file}. Skipping saving step.")
        error_files.append(file)
    
    logger.info(f"File {file} completed in {time.time() - file_start_time:.2f}s")
    logger.info("=" * 80)

logger.info("=" * 80)
logger.info(f"PROCESSING PHASE completed in {time.time() - processing_start:.2f}s")
logger.info("=" * 80)

# Final summary
logger.info("=" * 80)
logger.info("FINAL SUMMARY")
logger.info("=" * 80)
if error_files:
    logger.warning(f"List of failed files ({len(error_files)}): {error_files}")
else:
    logger.info("[SUCCESS] All files processed successfully.")

if failed_similarity_files: ###### FOR DEBUGGING AND QA
    logger.warning(f"Files that failed 0.8 similarity test but inserted to MongoDB anyways: {failed_similarity_files}")

logger.info("=" * 80)
logger.info("Script execution completed.")
logger.info("=" * 80)

