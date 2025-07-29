"""
Resume Extraction and Key Metrics Multi-Agent Workflow
=============================================

This script automates the process of extracting structured data from resumes using multiple Gemini LLM agents, performing Key Metrics Analysis, validating the results, and generating vector embeddings for semantic search. It is designed for batch processing of resume files and saving results to MongoDB.

Workflow Overview
-----------------
1. **File Preparation**: Loops through all files in the `Resume_inputs` directory.
2. **Conversion**: Converts `.docx` resumes to PDF and archives the originals.
3. **Upload**: Uploads each resume to the root Gemini agent.
4. **First Pass (Resume Data Extraction)**: Uses a Gemini agent to extract structured data from the resume using a prompt template.
5. **Second Pass (Key Metrics Analysis)**: Runs key metrics analysis on the extracted data using another Gemini agent and a separate prompt template.
6. **Third Pass (Validation)**: Validates the extracted and analyzed data using a validation agent.
7. **Vector Embedding Generation**: Generates semantic embeddings from the extracted resume content for job matching and search capabilities.
8. **Saving Results**: Saves all LLM responses and embeddings to MongoDB. If saving fails, raw responses are logged for debugging.
9. **Cleanup**: Deletes uploaded files from the agent and moves processed files to the archive directory.

**Agent Retry Logic and Pipeline Re-runs**
------------------------------------------
- Each agent step (Extraction, Key Metrics, Validation) includes robust retry logic:
    - If the LLM response is empty, missing, or contains invalid JSON, the agent will retry up to 2 times (`MAX_RETRIES`).
    - All parsing errors and retry attempts are logged for traceability.
- If the validation agent returns a `validation_score` less than 7, the entire extraction/key_metrics/validation pipeline is re-run (up to 2 additional times per file).
    - Each pipeline re-run also includes per-agent retries as above.
    - Validation flags are logged when the score is low.
- Files are only moved to the processed directory after all retries and re-runs are complete, ensuring only successfully processed files are archived.

**Embedding Generation**
------------------------
- **Content Extraction**: Uses the same logic as `batch_resume_embedding.py` to extract key content:
    - Professional summary from `basics.summary`
    - All skills and keywords from `skills` array
    - Recent work experience (last 2 positions) from `work_experience` array
    - Highest education level from `education` array
- **Embedding Model**: Uses Gemini's `embedding-001` model with `RETRIEVAL_DOCUMENT` task type
- **Storage**: Embeddings are stored in MongoDB with metadata including generation timestamp and model information
- **Error Handling**: Embedding generation failures don't stop the workflow; resumes are still processed and saved

Key Components
--------------

- **GeminiProcessor**: Handles LLM interactions for each task (extraction, key metrics, validation, embeddings).
- **MongoDB Integration**: Saves structured responses and embeddings for further analysis and semantic search.
- **Text Extraction**: Extracts key content for embedding generation using `libs.text_extraction`.
- **Logging**: Tracks progress and errors for each file, including retry and re-run attempts.
- **Error Handling & Retries**: Retries LLM calls if invalid JSON is detected in responses, and re-runs the pipeline if validation fails.

Directory Structure
-------------------
- `Resume_inputs/` : Input resumes (.docx or .pdf)
- `Resume_inputs/base_docx_pre-conversion/` : Archived original .docx files
- `data/Processed_resumes/` : Processed resumes (PDFs)
- `data/text_output/` : LLM output text files
- `Phase 1 Workflow/Prompts/` : Prompt templates for each agent

How to Use
----------
1. Place your resume files in the `Resume_inputs` directory.
2. Ensure MongoDB is running and accessible.
3. Run this script. It will process all files in the input directory.
4. Check the output directories and MongoDB for results.
5. Resumes will be ready for semantic search and job matching with generated embeddings.

Dependencies
------------
- Python 3.x
- `docx2pdf` for file conversion
- Custom modules: `libs.gemini_processor`, `libs.mongodb`, `libs.text_extraction`, `utils`

"""
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


import shutil
from datetime import datetime
from docx2pdf import convert
import libs.gemini_processor as gemini_processor
from libs.mongodb import save_llm_responses_to_mongodb, _get_mongo_client
from utils import get_logger
import time
from dotenv import load_dotenv
load_dotenv()

# -----------------------------
# Configuration and Directories
# -----------------------------
# LOOP_DIR: Directory containing input resumes (.docx or .pdf)
# ARCHIVE_ROOT: Where original .docx files are archived after conversion
# PROCESSED_DIR: Where processed resumes (PDFs) are moved after processing
# TEXT_OUTPUT_DIR: Where LLM output text files are saved
LOOP_DIR = "Resume_inputs"
ARCHIVE_ROOT = "Resume_inputs"
PROCESSED_DIR = "data/Processed_resumes"
TEXT_OUTPUT_DIR = "data/text_output"

# -------------------
# MongoDB Connection
# -------------------
# DB_NAME: Name of the MongoDB database
# mongo_client: MongoDB client instance for saving results
DB_NAME = "Resume_study"
mongo_client = _get_mongo_client()

# --------------
# Logging Setup
# --------------
logger = get_logger(__name__)

# -----------------------------
# Gemini Agent Initialization
# -----------------------------
# root_gemini: Handles file uploads (shared with other agents)
# gemini_resume_data: Extracts structured data from resumes
# gemini_key_metrics: Performs Key Metrics Analysis
# gemini_validation: Validates the extracted and analyzed data
root_gemini = gemini_processor.GeminiProcessor(
    model_name="gemini-2.5-flash",
    temperature=0.4,
    enable_google_search=False
)

gemini_resume_data = gemini_processor.GeminiProcessor(
    model_name="gemini-2.5-pro",
    temperature=0.4,
    enable_google_search=True
)

gemini_key_metrics = gemini_processor.GeminiProcessor(
    model_name="gemini-2.5-pro",
    temperature=0.4,
    enable_google_search=False
)

gemini_validation = gemini_processor.GeminiProcessor(
    model_name="gemini-2.5-pro",
    temperature=0.4,
    enable_google_search=False
)

MAX_RETRIES = 2

# -----------------------------------
# Utility: Move file with timestamp
# -----------------------------------
def safe_move(src, dst):
    """
    Move a file from src to dst. If dst exists, append a timestamp to avoid overwriting.
    Returns the final destination path.
    """
    if os.path.exists(dst):
        base, ext = os.path.splitext(dst)
        dst = f"{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
    shutil.move(src, dst)
    return dst

# ---------------------------------------------------
# Utility: Convert .docx to PDF and archive original
# ---------------------------------------------------
def convert_to_pdf(input_path: str, archive_root: str = None) -> str:
    """
    Converts a .docx file to PDF, archives the original .docx, and returns the PDF path.
    Args:
        input_path: Path to the .docx file
        archive_root: Directory to archive the original .docx (optional)
    Returns:
        Path to the converted PDF file.
    """
    base, _ = os.path.splitext(input_path)
    pdf_path = f"{base}.pdf"
    convert(input_path, pdf_path)
    if archive_root:
        archive_dir = os.path.join(archive_root, "base_docx_pre-conversion")
        os.makedirs(archive_dir, exist_ok=True)
        archived = os.path.join(archive_dir, os.path.basename(input_path))
        safe_move(input_path, archived)
    return pdf_path

# ---------------------------------------------------
# Main Processing Flow (see docstring for overview)
# ---------------------------------------------------
if __name__ == "__main__":
    for filename in os.listdir(LOOP_DIR):
        try:
            file_path = os.path.join(LOOP_DIR, filename)
            if not os.path.isfile(file_path):
                continue

            # Step 1: Convert .docx to PDF and archive original
            if filename.lower().endswith(".docx"):
                try:
                    file_path = convert_to_pdf(file_path, ARCHIVE_ROOT)
                except Exception as e:
                    logger.error(f"Failed to convert {file_path} to PDF: {e}. Skipping file.")
                    continue
            processed_filename = os.path.basename(file_path)
            resume_data_response = None
            key_metrics_response = None
            resume_data_retries = 0
            key_metrics_retries = 0
            validation_retries = 0
            try:
                # Step 2: Upload file to root Gemini agent
                uploaded_file = root_gemini.upload_file(file_path)
            except Exception as e:
                logger.error(f"Failed while uploading file {filename}, ERROR: {e}")

            # Step 3: Resume Data Extraction (First Pass)
            logger.info(f'Conducting first pass for {processed_filename}')
            try:
                gemini_resume_data.load_prompt_template('Phase 1 Workflow/Prompts/prompt_std_resume_data.md')
                gemini_resume_data.uploaded_resume_file = root_gemini.uploaded_resume_file
                attempt = 0
                while attempt < MAX_RETRIES:
                    try:
                        resume_data_response = gemini_resume_data.generate_content()
                        from libs.mongodb import _clean_raw_llm_response
                        parsed = _clean_raw_llm_response(resume_data_response.text, processed_filename)
                        should_retry = False
                        if not resume_data_response or not hasattr(resume_data_response, 'text') or not resume_data_response.text:
                            should_retry = True
                        elif parsed and "error" in parsed:
                            should_retry = True
                        if should_retry:
                            logger.warning(f"Error or empty response detected, retrying (attempt {attempt+1}) for {processed_filename}... Error: {parsed.get('error') if parsed else 'No response'}")
                            attempt += 1
                            resume_data_retries = attempt
                            continue
                        break
                    except Exception as e:
                        logger.warning(f"Exception during resume data extraction (attempt {attempt+1}) for {processed_filename}: {e}")
                        attempt += 1
                        resume_data_retries = attempt
                        continue
                if resume_data_retries > 0:
                    logger.info(f"First pass for {processed_filename} required {resume_data_retries} retry(ies).")
            except Exception as e: 
                logger.error(f"Failed in first pass, file: {filename}, ERROR: {e}")

            # Step 4: Key Metrics (Second Pass)
            logger.info(f'Conducting second pass (key metrics) for {processed_filename}')
            try:
                key_metrics_prompt = gemini_key_metrics.load_prompt_template('Phase 1 Workflow/Prompts/prompt_std_key_metrics.md')
                key_metrics_prompt = key_metrics_prompt + "\nThe LLM Response:" + resume_data_response.text
                gemini_key_metrics.uploaded_resume_file = root_gemini.uploaded_resume_file
                attempt = 0
                while attempt < MAX_RETRIES:
                    try:
                        key_metrics_response = gemini_key_metrics.generate_content(prompt = key_metrics_prompt)
                        from libs.mongodb import _clean_raw_llm_response
                        parsed = _clean_raw_llm_response(key_metrics_response.text, processed_filename)
                        should_retry = False
                        if not key_metrics_response or not hasattr(key_metrics_response, 'text') or not key_metrics_response.text:
                            should_retry = True
                        elif parsed and "error" in parsed:
                            should_retry = True
                        if should_retry:
                            logger.warning(f"Error or empty response detected, retrying (attempt {attempt+1}) for {processed_filename}... Error: {parsed.get('error') if parsed else 'No response'}")
                            attempt += 1
                            key_metrics_retries = attempt
                            continue
                        break
                    except Exception as e:
                        logger.warning(f"Exception during key metrics extraction (attempt {attempt+1}) for {processed_filename}: {e}")
                        attempt += 1
                        key_metrics_retries = attempt
                        continue
                if key_metrics_retries > 0:
                    logger.info(f"Second pass (key metrics) for {processed_filename} required {key_metrics_retries} retry(ies).")
                gemini_key_metrics.save_generated_content(response=key_metrics_response, output_dir=TEXT_OUTPUT_DIR)
            except Exception as e:
                logger.error(f"Failed in second pass, file: {filename}, ERROR: {e}")
            
            # Step 5: Validation Agent (Third Pass)
            logger.info(f'Conducting third pass (validation agent) for {processed_filename}')
            validation_response = None
            validation_score = None
            try:
                validation_prompt = gemini_validation.load_prompt_template('Phase 1 Workflow/Prompts/prompt_std_validation.md')
                with open('Phase 1 Workflow/Prompts/prompt_std_resume_data.md', 'r', encoding='utf-8') as f:
                    resume_data_reference = f.read()
                with open('Phase 1 Workflow/Prompts/prompt_std_key_metrics.md', 'r', encoding='utf-8') as f:
                    key_metrics_reference = f.read()
                full_validation_prompt = (
                    validation_prompt +
                    "\n\n---\nREFERENCE: Resume Data Extraction Schema and Instructions (DO NOT FOLLOW FOR OUTPUT FORMAT)\n" +
                    resume_data_reference +
                    "\n\n---\nREFERENCE: Key Metrics Extraction Schema and Logic (DO NOT FOLLOW FOR OUTPUT FORMAT)\n" +
                    key_metrics_reference +
                    "\n\nResume Data Response:" + resume_data_response.text +
                    "\nKey Metrics Response:" + key_metrics_response.text
                )
                gemini_validation.uploaded_resume_file = root_gemini.uploaded_resume_file
                attempt = 0
                while attempt < MAX_RETRIES:
                    try:
                        validation_response = gemini_validation.generate_content(prompt=full_validation_prompt)
                        from libs.mongodb import _clean_raw_llm_response
                        parsed = _clean_raw_llm_response(validation_response.text, processed_filename)
                        validation_score = parsed.get("validation_score")
                        should_retry = False
                        if not validation_response or not hasattr(validation_response, 'text') or not validation_response.text:
                            should_retry = True
                        elif parsed and "error" in parsed:
                            should_retry = True
                        if should_retry:
                            logger.warning(f"Error or empty response detected, retrying (attempt {attempt+1}) for {processed_filename}... Error: {parsed.get('error') if parsed else 'No response'}")
                            attempt += 1
                            validation_retries = attempt
                            continue
                        break
                    except Exception as e:
                        logger.warning(f"Exception during validation (attempt {attempt+1}) for {processed_filename}: {e}")
                        attempt += 1
                        validation_retries = attempt
                        continue
                if validation_retries > 0:
                    logger.info(f"Third pass (validation agent) for {processed_filename} required {validation_retries} retry(ies).")
                gemini_validation.save_generated_content(response=validation_response, output_dir=TEXT_OUTPUT_DIR)
            except Exception as e:
                logger.error(f"Failed in third pass (validation agent), file: {filename}, ERROR: {e}")


            # If validation_score is present and less than 7, re-run the extraction/key_metrics/validation loop (up to 2 times)

            rerun_count = 0
            MAX_RERUNS = 2
            while validation_score is not None:
                try:
                    score_val = float(validation_score)
                except Exception:
                    score_val = None
                if score_val is not None and score_val < 7 and rerun_count < MAX_RERUNS:
                    # Log validation_flags if present
                    validation_flags = None
                    if parsed and isinstance(parsed, dict):
                        validation_flags = parsed.get("validation_flags")
                    logger.warning(f"Validation score {score_val} < 7 for {processed_filename}. Validation flags: {validation_flags}")
                    rerun_count += 1

                    logger.info(f"Re-running extraction, key metrics, and validation for {processed_filename} due to low validation score (attempt {rerun_count}).")
                    try:
                        # --- Extraction Agent with Retry (robust logic) ---
                        gemini_resume_data.load_prompt_template('Phase 1 Workflow/Prompts/prompt_std_resume_data.md')
                        gemini_resume_data.uploaded_resume_file = root_gemini.uploaded_resume_file
                        extraction_attempt = 0
                        resume_data_response = None
                        while extraction_attempt < MAX_RETRIES:
                            try:
                                resume_data_response = gemini_resume_data.generate_content()
                                from libs.mongodb import _clean_raw_llm_response
                                parsed_extraction = _clean_raw_llm_response(resume_data_response.text, processed_filename)
                                should_retry = False
                                if not resume_data_response or not hasattr(resume_data_response, 'text') or not resume_data_response.text:
                                    should_retry = True
                                elif parsed_extraction and "error" in parsed_extraction:
                                    should_retry = True
                                if should_retry:
                                    logger.warning(f"Extraction re-run: Error or empty response, retrying (attempt {extraction_attempt+1}) for {processed_filename}... Error: {parsed_extraction.get('error') if parsed_extraction else 'No response'}")
                                    extraction_attempt += 1
                                    continue
                                break
                            except Exception as e:
                                logger.warning(f"Exception during extraction re-run (attempt {extraction_attempt+1}) for {processed_filename}: {e}")
                                extraction_attempt += 1
                                continue
                        if extraction_attempt > 0:
                            logger.info(f"Extraction re-run for {processed_filename} required {extraction_attempt} retry(ies).")
                        if not resume_data_response or not hasattr(resume_data_response, 'text') or getattr(resume_data_response, 'text', None) in (None, ""):
                            logger.error(f"Extraction re-run failed for {processed_filename}: No response or missing text after retries. Will retry re-run loop if attempts remain.")
                            continue
                        logger.info(f"Extraction re-run complete for {processed_filename}.");

                        # --- Key Metrics Agent with Retry (robust logic) ---
                        key_metrics_prompt = gemini_key_metrics.load_prompt_template('Phase 1 Workflow/Prompts/prompt_std_key_metrics.md')
                        key_metrics_prompt = key_metrics_prompt + "\nThe LLM Response:" + resume_data_response.text
                        gemini_key_metrics.uploaded_resume_file = root_gemini.uploaded_resume_file
                        key_metrics_attempt = 0
                        key_metrics_response = None
                        while key_metrics_attempt < MAX_RETRIES:
                            try:
                                key_metrics_response = gemini_key_metrics.generate_content(prompt=key_metrics_prompt)
                                from libs.mongodb import _clean_raw_llm_response
                                parsed_key_metrics = _clean_raw_llm_response(key_metrics_response.text, processed_filename)
                                should_retry = False
                                if not key_metrics_response or not hasattr(key_metrics_response, 'text') or not key_metrics_response.text:
                                    should_retry = True
                                elif parsed_key_metrics and "error" in parsed_key_metrics:
                                    should_retry = True
                                if should_retry:
                                    logger.warning(f"Key metrics re-run: Error or empty response, retrying (attempt {key_metrics_attempt+1}) for {processed_filename}... Error: {parsed_key_metrics.get('error') if parsed_key_metrics else 'No response'}")
                                    key_metrics_attempt += 1
                                    continue
                                break
                            except Exception as e:
                                logger.warning(f"Exception during key metrics re-run (attempt {key_metrics_attempt+1}) for {processed_filename}: {e}")
                                key_metrics_attempt += 1
                                continue
                        if key_metrics_attempt > 0:
                            logger.info(f"Key metrics re-run for {processed_filename} required {key_metrics_attempt} retry(ies).")
                        if not key_metrics_response or not hasattr(key_metrics_response, 'text') or getattr(key_metrics_response, 'text', None) in (None, ""):
                            logger.error(f"Key metrics re-run failed for {processed_filename}: No response or missing text after retries. Will retry re-run loop if attempts remain.")
                            continue
                        logger.info(f"Key metrics re-run complete for {processed_filename}.");

                        # --- Validation Agent with Retry (robust logic) ---
                        validation_prompt = gemini_validation.load_prompt_template('Phase 1 Workflow/Prompts/prompt_std_validation.md')
                        with open('Phase 1 Workflow/Prompts/prompt_std_resume_data.md', 'r', encoding='utf-8') as f:
                            resume_data_reference = f.read()
                        with open('Phase 1 Workflow/Prompts/prompt_std_key_metrics.md', 'r', encoding='utf-8') as f:
                            key_metrics_reference = f.read()
                        full_validation_prompt = (
                            validation_prompt +
                            "\n\n---\nREFERENCE: Resume Data Extraction Schema and Instructions (DO NOT FOLLOW FOR OUTPUT FORMAT)\n" +
                            resume_data_reference +
                            "\n\n---\nREFERENCE: Key Metrics Extraction Schema and Logic (DO NOT FOLLOW FOR OUTPUT FORMAT)\n" +
                            key_metrics_reference +
                            "\n\nResume Data Response:" + resume_data_response.text +
                            "\nKey Metrics Response:" + key_metrics_response.text
                        )
                        gemini_validation.uploaded_resume_file = root_gemini.uploaded_resume_file
                        validation_attempt = 0
                        validation_response = None
                        while validation_attempt < MAX_RETRIES:
                            try:
                                validation_response = gemini_validation.generate_content(prompt=full_validation_prompt)
                                from libs.mongodb import _clean_raw_llm_response
                                parsed_validation = _clean_raw_llm_response(validation_response.text, processed_filename)
                                validation_score = parsed_validation.get("validation_score")
                                validation_flags = parsed_validation.get("validation_flags")
                                should_retry = False
                                if not validation_response or not hasattr(validation_response, 'text') or not validation_response.text:
                                    should_retry = True
                                elif parsed_validation and "error" in parsed_validation:
                                    should_retry = True
                                if should_retry:
                                    logger.warning(f"Validation re-run: Error or empty response, retrying (attempt {validation_attempt+1}) for {processed_filename}... Error: {parsed_validation.get('error') if parsed_validation else 'No response'}")
                                    validation_attempt += 1
                                    continue
                                break
                            except Exception as e:
                                logger.warning(f"Exception during validation re-run (attempt {validation_attempt+1}) for {processed_filename}: {e}")
                                validation_attempt += 1
                                continue
                        if validation_attempt > 0:
                            logger.info(f"Validation re-run for {processed_filename} required {validation_attempt} retry(ies).")
                        if not validation_response or not hasattr(validation_response, 'text') or getattr(validation_response, 'text', None) in (None, ""):
                            logger.error(f"Validation re-run failed for {processed_filename}: No response or missing text after retries. Will retry re-run loop if attempts remain.")
                            continue
                        gemini_validation.save_generated_content(response=validation_response, output_dir=TEXT_OUTPUT_DIR)
                        logger.info(f"Validation re-run complete for {processed_filename}.")
                        # Update validation_score and validation_flags for next check
                        try:
                            from libs.mongodb import _clean_raw_llm_response
                            parsed = _clean_raw_llm_response(validation_response.text, processed_filename)
                            validation_score = parsed.get("validation_score")
                            validation_flags = parsed.get("validation_flags")
                        except Exception as e:
                            logger.error(f"Error parsing validation_response after re-run: {e}")
                            continue
                    except Exception as e:
                        logger.error(f"Error during re-run for low validation score for {processed_filename}: {e}")
                        continue
                else:
                    break

            # Step 6: Generate Vector Embedding (New Step)
            logger.info(f'Generating vector embedding for {processed_filename}')
            embedding = None
            try:
                # Parse the resume_data_response to get the nested resume_data
                if resume_data_response and hasattr(resume_data_response, 'text') and resume_data_response.text:
                    from libs.mongodb import _clean_raw_llm_response
                    parsed_resume_data = _clean_raw_llm_response(resume_data_response.text, processed_filename)
                    
                    if parsed_resume_data and isinstance(parsed_resume_data, dict):
                        # Create a temporary document structure with the nested resume_data
                        temp_doc = {
                            "resume_data": parsed_resume_data
                        }
                        
                        # Extract content for embedding using the same logic as batch_resume_embedding
                        from libs.text_extraction import extract_resume_content_from_mongo_doc
                        content_for_embedding = extract_resume_content_from_mongo_doc(temp_doc)
                        
                        if content_for_embedding:
                            # Generate embedding using the root_gemini processor
                            embedding = root_gemini.generate_embedding(
                                text=content_for_embedding,
                                task_type="RETRIEVAL_DOCUMENT"
                            )
                            
                            if embedding:
                                logger.info(f"Successfully generated embedding for {processed_filename} (dimensions: {len(embedding)})")
                            else:
                                logger.warning(f"Failed to generate embedding for {processed_filename}")
                        else:
                            logger.warning(f"No content extracted for embedding for {processed_filename}")
                    else:
                        logger.warning(f"Could not parse resume_data_response for {processed_filename}")
                else:
                    logger.warning(f"No resume_data_response available for embedding generation for {processed_filename}")
                    
            except Exception as e:
                logger.error(f"Error generating embedding for {processed_filename}: {e}")

        except Exception as e:
            logger.exception(f'Error processing file {filename}: {e}', exc_info=True)

        # Step 7: Save all LLM responses to MongoDB (if available)
        llm_responses_dict = {}
        if resume_data_response is not None:
            llm_responses_dict["resume_data"] = resume_data_response
        if key_metrics_response is not None:
            llm_responses_dict["key_metrics"] = key_metrics_response
        if validation_response is not None:
            llm_responses_dict["validation"] = validation_response

        if llm_responses_dict:
            try:
                save_llm_responses_to_mongodb(
                    llm_responses_dict,
                    db_name=DB_NAME,
                    collection_name="Standardized_resume_data",
                    file_path=file_path,
                    mongo_client=mongo_client,
                )
                
                # Add embedding to the document if available (update the saved document)
                if embedding:
                    try:
                        db = mongo_client[DB_NAME]
                        collection = db["Standardized_resume_data"]
                        result = collection.update_one(
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
                        if result.modified_count > 0:
                            logger.info(f"Successfully added embedding to MongoDB for {processed_filename}")
                        else:
                            logger.warning(f"No document updated with embedding for {processed_filename}")
                    except Exception as e:
                        logger.error(f"Error adding embedding to MongoDB for {processed_filename}: {e}")
                
            except Exception as e:
                logger.error(f"Error saving to MongoDB for {processed_filename}: {e}")
                # If saving fails, log raw LLM responses for debugging
                raw_log_dir = os.path.join(TEXT_OUTPUT_DIR, "raw_failed_llm_responses")
                os.makedirs(raw_log_dir, exist_ok=True)
                if resume_data_response is not None and hasattr(resume_data_response, 'text'):
                    with open(os.path.join(raw_log_dir, f"{processed_filename}_resume_data_raw.txt"), "w", encoding="utf-8") as f:
                        f.write(resume_data_response.text)
                if key_metrics_response is not None and hasattr(key_metrics_response, 'text'):
                    with open(os.path.join(raw_log_dir, f"{processed_filename}_key_metrics_raw.txt"), "w", encoding="utf-8") as f:
                        f.write(key_metrics_response.text)
        
        # Step 8: Cleanup - delete uploaded file and move processed file
        root_gemini.delete_uploaded_file()
        os.makedirs(PROCESSED_DIR, exist_ok=True)
        dest_path = safe_move(file_path, os.path.join(PROCESSED_DIR, processed_filename))
        logger.info(f"File successfully processed: {processed_filename}")
