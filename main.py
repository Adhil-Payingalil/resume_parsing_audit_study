""" Main script to process resumes and save results to MongoDB.
This script processes resumes in a specified directory, converts .docx files to .pdf,"""


import os 
import shutil
from datetime import datetime
from docx2pdf import convert
import gemini_processor
from mongodb import save_LLM_response_to_mongodb, _get_mongo_client
import utils

# Initialize logging
logger = utils.get_logger(__name__)

# Initialize Gemini processor with model and API key
mongo_client = _get_mongo_client()
gemini = gemini_processor.GeminiProcessor(
    model_name="gemini-2.0-flash",
    temperature=0.4,
    api_key=os.getenv("GEMINI_API_KEY"),
    enable_google_search=False,
)

""" Safely move a file to a new destination, appending a timestamp if the destination already exists. """

def safe_move(src, dst):
    """
    Args:
    src (str): Source file path.
    dst (str): Destination file path.

    Returns:
    str: The final destination path.
    """
    if os.path.exists(dst):
        base, ext = os.path.splitext(dst)
        dst = f"{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
    shutil.move(src, dst)
    return dst

def loop_local_files(Loop_dir="Resume_inputs", prompt_template_path="prompt_engineering_eda.md", collection_name="EDA_data", db_name="Resume_study"):
    """ 
    Main loop to process all resumes in the input directory.
    Steps:
    1. Iterates over each file in `Loop_dir`.
    2. Converts `.docx` files to PDF and archives the original.
    3. Processes each PDF with Gemini and the selected prompt template.
    4. Moves processed files to `Processed_resumes`.
    5. Saves output and metadata to MongoDB.

    Args:
        Loop_dir (str): Directory containing input resumes.
        prompt_template_path (str): Path to the prompt template.
        collection_name (str): MongoDB collection to save results.
    """ 
    for filename in os.listdir(Loop_dir):
        try:
            file_path = os.path.join(Loop_dir, filename)
            if not os.path.isfile(file_path):
                continue
            
            # Handle DOCX conversion
            if filename.endswith(".docx"):
                pdf_file_path = os.path.splitext(file_path)[0] + ".pdf"
                convert(file_path, pdf_file_path)

                archive_dir = os.path.join(Loop_dir, "base_docx_pre-conversion")
                os.makedirs(archive_dir, exist_ok=True)
                safe_move(file_path, os.path.join(archive_dir, filename))

                file_path = pdf_file_path
                processed_filename = os.path.basename(pdf_file_path)
            else:
                processed_filename = filename

            logger.info(f"Processing {processed_filename}")

            # Run Gemini Processing Pipeline
            response = gemini.process_file(
                prompt_template_path=prompt_template_path,
                file_path=file_path
            )

            # Move processed file to archive
            processed_dir = "Processed_resumes"
            os.makedirs(processed_dir, exist_ok=True)
            dest_path = safe_move(file_path, os.path.join(processed_dir, processed_filename))

            # Save results to MongoDB
            save_LLM_response_to_mongodb(
                llm_raw_text=response.text,
                llm_response=response,
                file_name=gemini.file_name,
                file_path=dest_path,
                db_name=db_name,
                collection_name=collection_name,
                model_name=gemini.model_name,
                mongo_client=mongo_client
            )

        except Exception as e:
            logger.error(f"Failed to process {filename}: {str(e)}", exc_info=True)

""" 
## Script entry point
""" 
if __name__ == "__main__":
    loop_local_files(
        Loop_dir="Resume_inputs",
        prompt_template_path="Prompt_templates\prompt_engineering_parsing.md",
        collection_name="ITC_JSON_raw",
        db_name="Resume_study")
