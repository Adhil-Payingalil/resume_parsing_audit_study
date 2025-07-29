# treatment_generation_script.py
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
# 5. Save the 4 generated documents as separate entries in the 'Treated_resumes' collection as seperate documents with the same metadata.

# TODO:
# [ ] Add another agent that can create 4 company name lists for each resume to reduce the risk of experiment detection or flags by ATS systems. This can introduce confounding variables, caution


# [ ] Do some QA on Focused similarity score to see whether it is helpful or not. 
        # [ ] Remove Debugging things after QA
# [*] Functionality to do a single file 
# [*] Implement retry logic for low similarity scores.
# [*] Add logging, and error handling.
# [*] Add a failed files array to track files that failed to process.
# [*] Since the model does not get data for previous treatments, we have to ensure that all treatments are rephrased slightly differently.
#     [*] This can be done by adding a random seed to the rephrasing prompt (can we)
#     [O] (Too complex) Alternatively, we can add a langchain mechanism that gives all previous treatments to the model as context.
# [*] Fix similarity score, it is 0 for all resumes, which is not expected.
# [*] Add the source resume data to the target collection as well


import sys
import os
sys.path.append('..')
sys.path.append('../libs')

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
from sentence_transformers import SentenceTransformer # Local model to calculate the distance
import argparse # To enter the command line arguments

logger = get_logger(__name__)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Sector we are processing
parser = argparse.ArgumentParser(description="Generate treated resumes for a correspondence study.")
parser.add_argument("--sector", type=str, required=True, help="Industry prefix as in the mongoDB (all caps)")
parser.add_argument("--files", type=str, nargs='+', help="Optional: A list of specific file IDs to process (e.g., ITC-01.pdf ITC-02.pdf).")
args = parser.parse_args()

SECTOR = str.upper(args.sector).strip()

# MongoDB configuration
MONGO_CLIENT = _get_mongo_client()
DB_NAME = "Resume_study"
SOURCE_COLLECTION_NAME = "Standardized_resume_data"
TARGET_COLLECTION_NAME = "Treated_resumes"

# Gemini model configuration
GEMINI_MODEL_NAME = "gemini-2.5-flash"
GEMINI_TEMPERATURE = 0.6
ENABLE_GOOGLE_SEARCH = False
BASE_PROMPT_TEMPLATE_PATH = os.path.join(SCRIPT_DIR, "Prompts", "prompt_treatment_generation.md")
COMPANY_RESEARCH_PROMPT_TEMPLATE_PATH = os.path.join(SCRIPT_DIR, "Prompts", "prompt_similar_company_generation.md")
CONTROL_REFINER_PROMPT_TEMPLATE_PATH = os.path.join(SCRIPT_DIR, "Prompts", "prompt_control_refiner.md")
MAX_RETRIES = 2
STYLE_MODIFIERS = [
    "using strong, action-oriented verbs and focusing on quantifiable outcomes",
    "using a direct, concise, and professional tone, prioritizing clarity and brevity",
    "by emphasizing collaborative efforts and cross-functional teamwork",
    "by describing the technical aspects of the work with more precision and detail",
    "by framing the accomplishments as a narrative of challenges, actions, and results"
]

# 2. Initialize the GeminiProcessor
control_refiner_model = GeminiProcessor(
    model_name=GEMINI_MODEL_NAME,
    temperature=GEMINI_TEMPERATURE,
    enable_google_search=ENABLE_GOOGLE_SEARCH
)
control_refiner_prompt = control_refiner_model.load_prompt_template(prompt_file_path=CONTROL_REFINER_PROMPT_TEMPLATE_PATH)

treatment_model = GeminiProcessor(
    model_name=GEMINI_MODEL_NAME,
    temperature=GEMINI_TEMPERATURE,
    enable_google_search=ENABLE_GOOGLE_SEARCH
)
treatment_prompt = treatment_model.load_prompt_template(prompt_file_path=BASE_PROMPT_TEMPLATE_PATH)

company_research_model = GeminiProcessor(
    model_name=GEMINI_MODEL_NAME,
    temperature=GEMINI_TEMPERATURE,
    enable_google_search=True
)
company_research_prompt = company_research_model.load_prompt_template(prompt_file_path=COMPANY_RESEARCH_PROMPT_TEMPLATE_PATH)

# Treatment file paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TREATMENT_CEC_FILE = os.path.join(SCRIPT_DIR, "Education_treatment_dummy.xlsx")
TREATMENT_CWE_FILE = os.path.join(SCRIPT_DIR, "WE_treatment_dummy.xlsx")
# Load treatment data from Excel files in pandas DataFrames
cec_treatment_df = pd.read_excel(TREATMENT_CEC_FILE)
cec_treatment_df = cec_treatment_df[cec_treatment_df['sector'] == SECTOR].reset_index(drop=True)
cwe_treatment_df = pd.read_excel(TREATMENT_CWE_FILE)
cwe_treatment_df = cwe_treatment_df[cwe_treatment_df['sector'] == SECTOR].reset_index(drop=True)

# Load the model once to be reused in the loop for cosine similarity calculations
SIMILARITY_MODEL = SentenceTransformer(
    os.path.join(SCRIPT_DIR, "models", "all-MiniLM-L6-v2")
)
FOCUSED_SIMILARITY_THRESHOLD = 0.60

############################ ------------ Helper Functions ------------ ############################

def is_valid_resume_data(data: dict, label: str, treatment: str, file: str, retry_count: int) -> bool:
    if not data or not isinstance(data, dict):
        logger.error(f"Invalid {label} (not a dict) for treatment {treatment} in file {file} (attempt {retry_count + 1}).")
        return False
    if not data.get('resume_data') or not isinstance(data['resume_data'], dict):
        logger.error(f"Missing or invalid 'resume_data' in {label} for treatment {treatment} in file {file} (attempt {retry_count + 1}).")
        return False
    return True

def extract_rephrased_text(resume_data):
    text_parts = []
    try:
        if 'basics' in resume_data and 'summary' in resume_data['basics']:
            text_parts.append(resume_data['basics']['summary'])
        if 'work_experience' in resume_data:
            for job in resume_data['work_experience']:
                if 'highlights' in job and isinstance(job['highlights'], list):
                    text_parts.append(" ".join(job['highlights']))
        return " ".join(text_parts)
    except Exception as e:
        logger.error(f"Error extracting rephrased text from resume_data: {e}")
        return ""

def calculate_focused_similarity(control_resume_data, treated_resume_data):
    try:
        control_text = extract_rephrased_text(control_resume_data)
        treated_text = extract_rephrased_text(treated_resume_data)
        if not control_text or not treated_text:
            return 0.0
        control_embedding = SIMILARITY_MODEL.encode(control_text)
        treated_embedding = SIMILARITY_MODEL.encode(treated_text)
        score = cosine_similarity([control_embedding], [treated_embedding])[0][0]
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
    """
    control_refiner_prompt = control_refiner_prompt.replace('{JSON_resume_object}', str(source_resume_data))
    response = company_research_model.generate_content(prompt=control_refiner_prompt)
    llm_response = _clean_raw_llm_response(response.text)
    return llm_response

def _extract_company_name_list(source_resume_data):
    """
    Extracts a list of company names from the work experience section of the resume data.

    Args:
        source_resume_data (dict): Resume data dictionary.

    Returns:
        list: List of company names.
    """
    resume = source_resume_data.get('resume_data', {})
    work_history = resume.get('work_experience', [])
    company_names = []
    for job in work_history:
        company = job.get('company')
        if company:
            company_names.append(company)
    # Collect both company names and locations
    company_locations = []
    for job in work_history:
        company = job.get('company')
        location = job.get('location')
        if company or location:
            company_locations.append({'company': company, 'location': location})
    return {
        'company_location_pairs': company_locations
    }

#old company research function, unused
def company_research(source_resume_data ,company_research_model=company_research_model, company_research_prompt=company_research_prompt):
    company_name_list = _extract_company_name_list(source_resume_data=source_resume_data)
    company_research_prompt = company_research_prompt.replace('{company_names}', str(company_name_list))
    response = company_research_model.generate_content(prompt=company_research_prompt)
    llm_response = _clean_raw_llm_response(response.text)
    return llm_response

def company_research_with_ui(source_resume_data ,company_research_model=company_research_model, company_research_prompt=company_research_prompt):
    """
    Performs company research, then opens a UI for validation and editing.
    Allows the user to retry the generation or accept the result.
    """
    company_name_list = _extract_company_name_list(source_resume_data=source_resume_data)
    final_prompt = company_research_prompt.replace('{company_names}', str(company_name_list))

    while True: # This loop allows for retries
        # 1. Generate the content using the LLM
        raw_response = company_research_model.generate_content(prompt=final_prompt)
        llm_response = _clean_raw_llm_response(raw_response.text)
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
                logger.error('Invalid JSON format in final text while company generation: {e}')
                sys.exit(1)
        elif status == "retry":
            logger.info("User chose to retry. Regenerating company mappings")
            continue # Go to the next iteration of the while loop
        else: # 'cancelled'
            logger.info("\ncompany mapping generation cancelled by user.")
            sys.exit(1)

def replace_companies(resume_data: dict,
                      company_mappings: list[dict],
                      treatment_type: str) -> dict:
    """
    Replaces each work_experience company with a corresponding similar company
    based on the specified treatment_type ("Type_I", "Type_II", "Type_III").

    Returns a new resume_data dict.
    """
    if not resume_data or not isinstance(resume_data, dict):
        logger.error("Invalid resume_data provided. Expected a non-empty dictionary.")
        return resume_data
    if not company_mappings or not isinstance(company_mappings, list):
        logger.error("Invalid company_mappings provided. Expected a non-empty list of dictionaries.")
        return resume_data
    logger.info(f"Starting company replacement with treatment: {treatment_type}")
    logger.info(f"Number of companies in the original resume: {len(resume_data.get('resume_data', {}).get('work_experience', []))}")

    # Build lookup dict: {lowercase_original: {type: replacement_name}}
    lookup = {}
    for entry in company_mappings:
        orig = entry.get("Original_company")
        if not orig:
            logger.warning("Found an entry with no 'Original_company' field. Skipping.")
            continue

        similar_list = entry.get("Similar companies", [])
        type_mapping = {}
        for d in similar_list:
            for k, v in d.items():
                type_mapping[k] = v

        if treatment_type not in type_mapping:
            logger.warning(f"No '{treatment_type}' replacement found for '{orig}'. Skipping.")
            continue

        lookup[orig.lower()] = type_mapping[treatment_type]
        logger.info(f"Mapped '{orig}' → '{type_mapping[treatment_type]}'")

    # Deep copy to avoid modifying original
    new_data = copy.deepcopy(resume_data)

    replacements_done = 0
    for exp in new_data.get("resume_data", {}).get("work_experience", []):
        comp = exp.get("company", "")
        repl = lookup.get(comp.lower())

        if repl:
            logger.info(f"Replacing company '{comp}' with '{repl}'")
            exp["company"] = repl
            replacements_done += 1
        else:
            logger.warning(f"No replacement found for company: '{comp}' (keeping original)")

    logger.info(f"Company replacement complete. Total replacements made: {replacements_done}")
    return new_data

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

# 1. Import all files from the source collection for the specified sector
if args.files:
    # If specific files are provided via the command line, use that list
    valid_files = get_all_file_ids(db_name=DB_NAME, collection_name=SOURCE_COLLECTION_NAME, mongo_client=MONGO_CLIENT)
    sector_files = [f for f in args.files if f in valid_files]
    logger.info(f"Processing {len(sector_files)} specific files provided via command line.")
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
logger.info(f"Found {len(sector_files)} files for sector: {SECTOR}.")


target_collection = MONGO_CLIENT[DB_NAME][TARGET_COLLECTION_NAME]

# main processing loop
error_files = []
failed_similarity_files = [] ##### FOR DEBUGGING AND QA 
for file in sector_files[0:5]:
    try:
        # Building the final document structure, initializing empty doc with metadata
        logger.info(f"Processing file: {file}")
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
        source_resume_data = remove_north_american_elements(
            source_resume_data=source_resume_data,
            control_refiner_model=control_refiner_model,
            control_refiner_prompt=control_refiner_prompt
        )
        
        
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

        #Prepare a company name list for the source resume data. A pop up window will open to allow the user to validate and edit the company names.
        logger.info(f"Preparing company mappings for file {file}.")
        company_mappings = company_research_with_ui(
            source_resume_data=source_resume_data
        )

    except Exception as e:
        logger.error(f"Error in the control generation, or prompt generation for {file}: {e}")
        error_files.append(file)
    try:
        for key, value in treatment_prompts.items():
            logger.info(f"Generating treatment {key} for file {file}.")
            retry_count = 0
            focused_similarity_score = 0.0
            treated_resume_data = None
            while retry_count < MAX_RETRIES:
                response = treatment_model.generate_content(
                    prompt=value['prompt'],
                )
                if not response or not response.text:
                    logger.error(f"Failed to generate content for treatment {key} in file {file} (attempt {retry_count+1}).")
                    retry_count += 1
                    continue
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
                    next
                try:
                    focused_similarity_score = calculate_focused_similarity(
                        source_resume_data['resume_data'], treated_resume_data['resume_data']
                    )
                
                    focused_similarity_score = float(focused_similarity_score)
                    ########## FOR DEBUGGING AND SIMILARITY TEST
                    if focused_similarity_score < 0.8:
                        print(f'failed the similarity test at similarity score of: {focused_similarity_score}')
                        failed_similarity_files.append(file)

                except Exception as e:
                    logger.error(f"Could not convert similarity score to float: {focused_similarity_score} ({e})")
                    focused_similarity_score = 0.0
                if focused_similarity_score >= FOCUSED_SIMILARITY_THRESHOLD:
                    break
                else:
                    logger.warning(f"Low similarity score ({focused_similarity_score}) for treatment {key} with style guide: {value['style_guide']} in file {file} (attempt {retry_count+1}). Retrying...")
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
            logger.info(f"  -> Successfully prepared '{key}' for saving.")
    except Exception as e:
        import traceback
        logger.error(f"Error in the inner loop for {file} {key}: {e}\n{traceback.format_exc()}")
        error_files.append(file)

    # If any error occurred for this file, skip saving
    if file in error_files:
        logger.warning(f"Skipping saving for file {file} due to errors.")
        continue

    if documents_to_save:
        try:
            target_collection.insert_many(documents_to_save)
            logger.info(f"Successfully saved {len(documents_to_save)} treated resumes for file {file}.")
        except Exception as e:
            import traceback
            logger.error(f"Error saving documents for file {file}: {e}\n{traceback.format_exc()}")
            error_files.append(file)
    else:
        logger.error(f"No documents to save for file {file}. Skipping saving step.")
        error_files.append(file)

if error_files:
    logger.warning(f"List of failed files: {error_files}")
else:
    logger.info("All files processed successfully.")

if failed_similarity_files: ###### FOR DEBUGGING AND QA
    logger.warning(f"Files that failed similarity scores but inserted to mongoDB anyways: {failed_similarity_files}")



    

    
