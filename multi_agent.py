import os
import shutil
from datetime import datetime
from docx2pdf import convert
import libs.gemini_processor as gemini_processor
from libs.mongodb import save_LLM_response_to_mongodb, _get_mongo_client
from utils import get_logger
import time



LOOP_DIR="Resume_inputs"
ARCHIVE_ROOT="Resume_inputs"
PROCESSED_DIR = "data/Processed_resumes"
TEXT_OUTPUT_DIR = "data/text_output"
os.makedirs(TEXT_OUTPUT_DIR, exist_ok=True)


DB_NAME="Resume_study"

logger = get_logger(__name__)

mongo_client = _get_mongo_client()

root_gemini = gemini_processor.GeminiProcessor(
    model_name="gemini-2.0-flash",
    temperature=0.4,
    enable_google_search=False,
)
time.sleep(3)

gemini_eda = gemini_processor.GeminiProcessor(
    model_name="gemini-2.5-pro",
    temperature=0.4,
    enable_google_search=True,
)
time.sleep(3)

gemini_validator = gemini_processor.GeminiProcessor(
    model_name='gemini-2.5-flash',
    temperature=0.4,
    enable_google_search=False
)

def safe_move(src, dst):
    if os.path.exists(dst):
        base, ext = os.path.splitext(dst)
        dst = f"{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
    shutil.move(src, dst)
    return dst


def convert_to_pdf(input_path: str, archive_root: str = None) -> str:
    """
    Converts a .docx file at input_path to PDF, archives the original .docx,
    and returns the new PDF file path.

    Args:
        input_path: path to the .docx file
        archive_root: directory under which to archive the original .docx

    Returns:
        The path to the converted PDF file.
    """
    base, _ = os.path.splitext(input_path)
    pdf_path = f"{base}.pdf"

    # Convert
    convert(input_path, pdf_path)

    # Archive original .docx if requested
    if archive_root:
        archive_dir = os.path.join(archive_root, "base_docx_pre-conversion")
        os.makedirs(archive_dir, exist_ok=True)
        archived = os.path.join(archive_dir, os.path.basename(input_path))
        safe_move(input_path, archived)

    return pdf_path



if __name__ == "__main__":
    for filename in os.listdir(LOOP_DIR):
        try:
            file_path = os.path.join(LOOP_DIR, filename)
            if not os.path.isfile(file_path):
                continue

            # Convert .docx to PDF and archive original
            if filename.lower().endswith(".docx"):
                file_path = convert_to_pdf(file_path, ARCHIVE_ROOT)
            processed_filename = os.path.basename(file_path)
            
            try:
                uploaded_file = root_gemini.upload_file(file_path)
            except Exception as e:
                logger.error(f"Failed while uploading file {filename}, ERROR: {e}")





            logger.info('Conducting first pass')
            try:
                gemini_eda.load_prompt_template('Prompt_templates/prompt_engineering_eda.md')
                gemini_eda.uploaded_resume_file = root_gemini.uploaded_resume_file
                eda_response = gemini_eda.generate_content()
            except Exception as e: 
                logger.error(f"Failed in first pass, file: {filename}, ERROR: {e}")

            time.sleep(10)

            logger.info('Conducting second pass for validation')
            try:
                validator_prompt = gemini_validator.load_prompt_template('Prompt_templates/prompt_engineering_validation.md')
                validator_prompt = validator_prompt + "\nThe LLM Response:" + eda_response.text
                gemini_validator.uploaded_resume_file = root_gemini.uploaded_resume_file
                validator_response = gemini_validator.generate_content(prompt = validator_prompt)
                gemini_validator.save_generated_content(response=validator_response, output_path=TEXT_OUTPUT_DIR)
            except Exception as e:
                logger.error(f"Failed in second pass, file: {filename}, ERROR: {e}")
                

            


        except Exception as e:
            logger.exception(f'Error processing file {filename}: {e}', exc_info=True)

        
        save_LLM_response_to_mongodb(
            llm_raw_text=validator_response.text,
            llm_response=validator_response,
            file_name=processed_filename,
            db_name=DB_NAME,
            collection_name="multi_agent_test",
            file_path=file_path,
            mongo_client=mongo_client,
            model_name=gemini_validator.model_name
        )
        
        root_gemini.delete_uploaded_file()
        os.makedirs(PROCESSED_DIR, exist_ok=True)
        dest_path = safe_move(file_path, os.path.join(PROCESSED_DIR, processed_filename))
        logger.info(f"File successfully processed: {processed_filename}")
