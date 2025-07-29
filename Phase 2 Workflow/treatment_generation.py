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


# [*] Implement retry logic for low similarity scores.
# [*] Add logging, and error handling.
# [*] Add a failed files array to track files that failed to process.
# [*] Since the model does not get data for previous treatments, we have to ensure that all treatments are rephrased slightly differently.
#     [*] This can be done by adding a random seed to the rephrasing prompt (can we)
#     [O] (Too complex) Alternatively, we can add a langchain mechanism that gives all previous treatments to the model as context.
# [*] Fix similarity score, it is 0 for all resumes, which is not expected.
# [*] Add the source resume data to the target collection as well


import sys
sys.path.append('..')
sys.path.append('../libs')


import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from libs.mongodb import get_all_file_ids,_get_mongo_client ,get_document_by_fileid, _clean_raw_llm_response
from libs.gemini_processor import GeminiProcessor
from utils import get_logger
import json
import datetime
import random
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import argparse

logger = get_logger(__name__)

# Sector we are processing
parser = argparse.ArgumentParser(description="Generate treated resumes for a correspondence study.")
parser.add_argument("--sector", type=str, required=True, help="Industry prefix as in the mongoDB (all caps)")
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
PROMPT_TEMPLATE_PATH = "Phase 2 Workflow/Prompts/prompt_treatment_generation.md"
MAX_RETRIES = 2
STYLE_MODIFIERS = [
    "using strong, action-oriented verbs and focusing on quantifiable outcomes",
    "using a direct, concise, and professional tone, prioritizing clarity and brevity",
    "by emphasizing collaborative efforts and cross-functional teamwork",
    "by highlighting strategic thinking and the business impact of the work",
    "by describing the technical aspects of the work with more precision and detail",
    "by framing the accomplishments as a narrative of challenges, actions, and results"
]

# Treatment file paths
TREATMENT_CEC_FILE = "Phase 2 Workflow/Education_treatment_dummy.xlsx"
TREATMENT_CWE_FILE = "Phase 2 Workflow/WE_treatment_dummy.xlsx"
# Load treatment data from Excel files in pandas DataFrames
cec_treatment_df = pd.read_excel(TREATMENT_CEC_FILE)
cec_treatment_df = cec_treatment_df[cec_treatment_df['sector'] == SECTOR].reset_index(drop=True)
cwe_treatment_df = pd.read_excel(TREATMENT_CWE_FILE)
cwe_treatment_df = cwe_treatment_df[cwe_treatment_df['sector'] == SECTOR].reset_index(drop=True)

# Load the model once to be reused in the loop for cosine similarity calculations
SIMILARITY_MODEL = SentenceTransformer(
    r'Phase 2 Workflow/models/all-MiniLM-L6-v2'
)

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
        "{JSON_resume_object}", json.dumps(source_resume_data, indent=2)
    )

    # a) Prepare "Type_I" (CEC)
    cec_treatment_idx = random.randint(0, 1)  # Randomly select one of the two CEC treatments
    cec_treatment = cec_treatments[cec_treatment_idx]  # Randomly select one of the two CEC treatments
    type_i_prompt = base_prompt.replace("{Treatment_object}", str(cec_treatment))
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


#=============================================================================================================================================================================

# 1. Import all files from the source collection for the specified sector
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

# 2. Initialize the GeminiProcessor
treatment_model = GeminiProcessor(
    model_name=GEMINI_MODEL_NAME,
    temperature=GEMINI_TEMPERATURE,
    enable_google_search=ENABLE_GOOGLE_SEARCH
)
treatment_prompt = treatment_model.load_prompt_template(prompt_file_path=PROMPT_TEMPLATE_PATH)

target_collection = MONGO_CLIENT[DB_NAME][TARGET_COLLECTION_NAME]

# main processing loop
error_files = []
for file in sector_files[0:1]:
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
                "resume_data": source_resume_data['resume_data'] 
        }
        documents_to_save.append(control_resume_target_collection)

        # Get two random treatments for Canadian Education and Canadian Work Experience
        treatment_prompts = select_and_prepare_treatments(
            cec_treatment_df,
            cwe_treatment_df,
            source_resume_data,
            treatment_prompt,
            STYLE_MODIFIERS
        )
        if not treatment_prompts:
            logger.error(f"No treatments available for file {file}. stopping flow")
            sys.exit(1)
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
                focused_similarity_score = calculate_focused_similarity(
                    source_resume_data['resume_data'], treated_resume_data['resume_data']
                )
                try:
                    focused_similarity_score = float(focused_similarity_score)
                except Exception as e:
                    logger.error(f"Could not convert similarity score to float: {focused_similarity_score} ({e})")
                    focused_similarity_score = 0.0
                if focused_similarity_score >= 0.80:
                    break
                else:
                    logger.warning(f"Low similarity score ({focused_similarity_score}) for treatment {key} with style guide: {value['style_guide']} in file {file} (attempt {retry_count+1}). Retrying...")
                    retry_count += 1
            if focused_similarity_score < 0.80:
                logger.error(f"Failed to achieve desired similarity score for treatment {key} in file {file} after {MAX_RETRIES} attempts.")
                error_files.append(file)
                break
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



    
    
