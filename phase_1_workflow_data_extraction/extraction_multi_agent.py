"""
Resume Extraction and Key Metrics Multi-Agent Workflow
=============================================

This script automates the process of extracting structured data from resumes using multiple Gemini LLM agents.
It handles file conversion, data extraction, key metrics analysis, validation, and embedding generation.

Refactored for modularity and maintainability.
"""

import os
import sys
import shutil
import time
from datetime import datetime
from docx2pdf import convert
from dotenv import load_dotenv

# Add project root to path to allow importing from libs
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import libs.gemini_processor as gemini_processor
from libs.mongodb import save_llm_responses_to_mongodb, _get_mongo_client, _clean_raw_llm_response
from libs.text_extraction import extract_resume_content_from_mongo_doc
from utils import get_logger

# -----------------------------
# Configuration
# -----------------------------
load_dotenv()
logger = get_logger(__name__)

# Paths - anchored to this script's location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Inputs
LOOP_DIR = os.path.join(SCRIPT_DIR, "Resume_inputs")
ARCHIVE_ROOT = os.path.join(SCRIPT_DIR, "Resume_inputs")
PROMPTS_DIR = os.path.join(SCRIPT_DIR, "Prompts")

# Outputs (in Project Root data folder)
PROCESSED_DIR = os.path.join(PROJECT_ROOT, "data", "Processed_resumes")
TEXT_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "text_output")
RAW_LOG_DIR = os.path.join(TEXT_OUTPUT_DIR, "raw_failed_llm_responses")

# MongoDB
DB_NAME = "Resume_study"
COLLECTION_NAME = "Standardized_resume_data"

# Operation Mode
# if TEST_MODE is True, we skip MongoDB saves and print to console
TEST_MODE = os.getenv("TEST_MODE", "False").lower() == "true"

# Retry Config
MAX_RETRIES = 2
MAX_RERUNS = 2

# -----------------------------
# Agent Setup
# -----------------------------
def setup_agents():
    """Initialize and return the Gemini agents."""
    root_gemini = gemini_processor.GeminiProcessor(
        model_name="gemini-2.5-flash", temperature=0.4, enable_google_search=False
    )
    gemini_resume_data = gemini_processor.GeminiProcessor(
        model_name="gemini-2.5-pro", temperature=0.4, enable_google_search=True
    )
    gemini_key_metrics = gemini_processor.GeminiProcessor(
        model_name="gemini-2.5-pro", temperature=0.4, enable_google_search=False
    )
    gemini_validation = gemini_processor.GeminiProcessor(
        model_name="gemini-2.5-pro", temperature=0.4, enable_google_search=False
    )
    return root_gemini, gemini_resume_data, gemini_key_metrics, gemini_validation

# -----------------------------
# File Operations
# -----------------------------
def safe_move(src, dst):
    """Move file with timestamp if destination exists."""
    if os.path.exists(dst):
        base, ext = os.path.splitext(dst)
        dst = f"{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
    shutil.move(src, dst)
    return dst

def convert_to_pdf(input_path: str, archive_root: str = None) -> str:
    """Convert .docx to PDF and archive original."""
    base, _ = os.path.splitext(input_path)
    pdf_path = f"{base}.pdf"
    convert(input_path, pdf_path)
    if archive_root:
        archive_dir = os.path.join(archive_root, "base_docx_pre-conversion")
        os.makedirs(archive_dir, exist_ok=True)
        archived = os.path.join(archive_dir, os.path.basename(input_path))
        safe_move(input_path, archived)
    return pdf_path

# -----------------------------
# Workflow Steps
# -----------------------------
def run_extraction_step(agent, uploaded_file_obj, processed_filename):
    """Run Pass 1: Extract Resume Data."""
    try:
        agent.load_prompt_template(os.path.join(PROMPTS_DIR, 'prompt_std_resume_data.md'))
        agent.uploaded_resume_file = uploaded_file_obj
        
        attempt = 0
        while attempt < MAX_RETRIES:
            try:
                response = agent.generate_content()
                parsed = _clean_raw_llm_response(response.text, processed_filename)
                
                if not response.text or (parsed and "error" in parsed):
                    raise ValueError(f"Empty or Error response: {parsed.get('error') if parsed else 'No Text'}")
                
                return response, parsed
            except Exception as e:
                logger.warning(f"Extraction attempt {attempt+1} failed for {processed_filename}: {e}")
                attempt += 1
        
        logger.error(f"Extraction failed after {MAX_RETRIES} retries for {processed_filename}")
        return None, None
    except Exception as e:
        logger.error(f"Error in extraction step setup for {processed_filename}: {e}")
        return None, None

def run_key_metrics_step(agent, uploaded_file_obj, resume_data_text, processed_filename):
    """Run Pass 2: Extract Key Metrics."""
    try:
        prompt_template = agent.load_prompt_template(os.path.join(PROMPTS_DIR, 'prompt_std_key_metrics.md'))
        full_prompt = prompt_template + "\nThe LLM Response:" + resume_data_text
        agent.uploaded_resume_file = uploaded_file_obj
        
        attempt = 0
        while attempt < MAX_RETRIES:
            try:
                response = agent.generate_content(prompt=full_prompt)
                parsed = _clean_raw_llm_response(response.text, processed_filename)
                
                if not response.text or (parsed and "error" in parsed):
                    raise ValueError(f"Empty or Error response: {parsed.get('error') if parsed else 'No Text'}")
                
                agent.save_generated_content(response=response, output_dir=TEXT_OUTPUT_DIR)
                return response, parsed
            except Exception as e:
                logger.warning(f"Key Metrics attempt {attempt+1} failed for {processed_filename}: {e}")
                attempt += 1
                
        logger.error(f"Key Metrics failed after {MAX_RETRIES} retries for {processed_filename}")
        return None, None
    except Exception as e:
        logger.error(f"Error in key metrics step setup for {processed_filename}: {e}")
        return None, None

def run_validation_step(agent, uploaded_file_obj, resume_data_text, key_metrics_text, processed_filename):
    """Run Pass 3: Validate Data."""
    try:
        validation_prompt = agent.load_prompt_template(os.path.join(PROMPTS_DIR, 'prompt_std_validation.md'))
        
        # Load references (could be optimized to load once globaly, but keeping here for simplicity)
        with open(os.path.join(PROMPTS_DIR, 'prompt_std_resume_data.md'), 'r', encoding='utf-8') as f:
            resume_ref = f.read()
        with open(os.path.join(PROMPTS_DIR, 'prompt_std_key_metrics.md'), 'r', encoding='utf-8') as f:
            metrics_ref = f.read()
            
        full_prompt = (
            f"{validation_prompt}\n\n---\nREFERENCE: Resume Data Schema\n{resume_ref}"
            f"\n\n---\nREFERENCE: Key Metrics Schema\n{metrics_ref}"
            f"\n\nResume Data Response:{resume_data_text}"
            f"\nKey Metrics Response:{key_metrics_text}"
        )
        
        agent.uploaded_resume_file = uploaded_file_obj
        
        attempt = 0
        while attempt < MAX_RETRIES:
            try:
                response = agent.generate_content(prompt=full_prompt)
                parsed = _clean_raw_llm_response(response.text, processed_filename)
                
                if not response.text or (parsed and "error" in parsed):
                    raise ValueError(f"Empty or Error response: {parsed.get('error') if parsed else 'No Text'}")
                
                agent.save_generated_content(response=response, output_dir=TEXT_OUTPUT_DIR)
                return response, parsed
            except Exception as e:
                logger.warning(f"Validation attempt {attempt+1} failed for {processed_filename}: {e}")
                attempt += 1

        logger.error(f"Validation failed after {MAX_RETRIES} retries for {processed_filename}")
        return None, None
    except Exception as e:
        logger.error(f"Error in validation step setup for {processed_filename}: {e}")
        return None, None

def generate_embedding_for_doc(root_agent, resume_data_parsed, processed_filename):
    """Generate vector embedding."""
    try:
        if not resume_data_parsed or not isinstance(resume_data_parsed, dict):
            return None
            
        temp_doc = {"resume_data": resume_data_parsed}
        content = extract_resume_content_from_mongo_doc(temp_doc)
        
        if content:
            embedding = root_agent.generate_embedding(text=content, task_type="RETRIEVAL_DOCUMENT")
            logger.info(f"Generated embedding for {processed_filename}")
            return embedding
    except Exception as e:
        logger.error(f"Embedding generation failed for {processed_filename}: {e}")
    return None

def save_results(mongo_client, file_path, responses, embedding, processed_filename):
    """Save responses and embedding to MongoDB (or print if in Test Mode)."""
    if not responses:
        return

    # TEST MODE HANDLING
    if TEST_MODE:
        logger.info(f"*** TEST MODE: Skipping MongoDB Save for {processed_filename} ***")
        import json
        
        # Construct the final object like we would for DB
        final_output = {
            "file_id": processed_filename,
            "timestamp": datetime.now().isoformat(),
            "responses": {}
        }
        
        for key, resp in responses.items():
            if resp and hasattr(resp, 'text'):
                # Try to parse JSON to make it pretty
                parsed = _clean_raw_llm_response(resp.text, processed_filename)
                final_output["responses"][key] = parsed if parsed else resp.text
        
        print(f"\n--- JSON OUTPUT FOR {processed_filename} ---\n")
        print(json.dumps(final_output, indent=2, default=str))
        print(f"\n--- END JSON OUTPUT ---\n")
        return

    try:
        # Save main responses
        save_llm_responses_to_mongodb(
            responses,
            db_name=DB_NAME,
            collection_name=COLLECTION_NAME,
            file_path=file_path,
            mongo_client=mongo_client,
        )

        # Update with embedding if exists
        if embedding:
            db = mongo_client[DB_NAME]
            collection = db[COLLECTION_NAME]
            collection.update_one(
                {"file_id": processed_filename},
                {
                    "$set": {
                        "text_embedding": embedding,
                        "embedding_generated_at": datetime.now(),
                        "embedding_model": "embedding-001",
                        "embedding_task_type": "RETRIEVAL_DOCUMENT"
                    }
                }
            )
            logger.info(f"Saved embedding to MongoDB for {processed_filename}")

    except Exception as e:
        logger.error(f"MongoDB save failed for {processed_filename}: {e}")
        # Backup raw files
        os.makedirs(RAW_LOG_DIR, exist_ok=True)
        for key, resp in responses.items():
            if resp and hasattr(resp, 'text'):
                with open(os.path.join(RAW_LOG_DIR, f"{processed_filename}_{key}_raw.txt"), "w", encoding='utf-8') as f:
                    f.write(resp.text)

# -----------------------------
# Main Processing Pipeline
# -----------------------------
def process_single_file(file_path, agents, mongo_client):
    """Process a single resume file through the entire pipeline."""
    root_gemini, gemini_data, gemini_metrics, gemini_valid = agents
    filename = os.path.basename(file_path)
    
    # 1. Upload File
    try:
        root_gemini.upload_file(file_path)
        uploaded_file = root_gemini.uploaded_resume_file
    except Exception as e:
        logger.error(f"Failed to upload {filename}: {e}")
        return

    try:
        # 2. Pipeline Loop (Extraction -> Metrics -> Validation)
        # We loop here to handle the re-run logic if validation score is low
        
        best_responses = {}
        rerun_count = 0
        
        while rerun_count <= MAX_RERUNS:
            if rerun_count > 0:
                logger.info(f"*** RE-RUNNING Pipeline for {filename} (Attempt {rerun_count}) ***")

            # A. Extraction
            logger.info(f"Step 1: Extraction for {filename}")
            data_resp, data_parsed = run_extraction_step(gemini_data, uploaded_file, filename)
            if not data_resp:
                logger.error(f"Aborting pipeline for {filename} due to extraction failure.")
                break # Cannot proceed without data

            # B. Key Metrics
            logger.info(f"Step 2: Key Metrics for {filename}")
            metrics_resp, metrics_parsed = run_key_metrics_step(gemini_metrics, uploaded_file, data_resp.text, filename)
            if not metrics_resp:
                logger.error(f"Aborting pipeline for {filename} due to metrics failure.")
                break 

            # C. Validation
            logger.info(f"Step 3: Validation for {filename}")
            valid_resp, valid_parsed = run_validation_step(gemini_valid, uploaded_file, data_resp.text, metrics_resp.text, filename)
            
            # Save these as the current "best" candidates
            best_responses = {
                "resume_data": data_resp,
                "key_metrics": metrics_resp,
                "validation": valid_resp
            }

            # Check Score
            score = float(valid_parsed.get("validation_score", 0)) if valid_parsed else 0
            logger.info(f"Validation Score for {filename}: {score}")

            if score >= 7:
                logger.info(f"Score acceptable ({score}). Proceeding.")
                break
            else:
                logger.warning(f"Score too low ({score}). Flags: {valid_parsed.get('validation_flags')}")
                rerun_count += 1
        
        # 3. Embeddings (Pass 4)
        logger.info(f"Step 4: Embedding for {filename}")
        embedding = None
        # We need to re-parse the best response to get the dict for embedding extraction
        if best_responses.get("resume_data"):
             # Parsing again just to be safe/clean
            final_data_parsed = _clean_raw_llm_response(best_responses["resume_data"].text, filename)
            embedding = generate_embedding_for_doc(root_gemini, final_data_parsed, filename)

        # 4. Save
        logger.info(f"Step 5: Saving for {filename}")
        save_results(mongo_client, file_path, best_responses, embedding, filename)

    finally:
        # 5. Cleanup
        try:
            root_gemini.delete_uploaded_file()
        except Exception:
            pass # Best effort

    # 6. Archive processed file
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    safe_move(file_path, os.path.join(PROCESSED_DIR, filename))
    logger.info(f"Finished processing {filename}")

def main():
    """Main entry point."""
    if not os.path.exists(LOOP_DIR):
        logger.error(f"Input directory not found: {LOOP_DIR}")
        return

    # Initialize
    agents = setup_agents()
    mongo_client = _get_mongo_client()
    
    logger.info(f"Starting processing in {LOOP_DIR}")
    
    files = [f for f in os.listdir(LOOP_DIR) if os.path.isfile(os.path.join(LOOP_DIR, f))]
    
    for filename in files:
        file_path = os.path.join(LOOP_DIR, filename)
        
        # Convert if needed
        if filename.lower().endswith(".docx"):
            try:
                logger.info(f"Converting {filename} to PDF...")
                file_path = convert_to_pdf(file_path, ARCHIVE_ROOT)
                filename = os.path.basename(file_path) # Update filename to .pdf
            except Exception as e:
                logger.error(f"Conversion failed for {filename}: {e}")
                continue

        # Process
        process_single_file(file_path, agents, mongo_client)

if __name__ == "__main__":
    main()
