import os
import shutil
from datetime import datetime
from docx2pdf import convert
import libs.gemini_processor as gemini_processor
from libs.mongodb import save_single_LLM_response_to_mongodb, _get_mongo_client
from utils import get_logger

logger = get_logger(__name__)

mongo_client = _get_mongo_client()
gemini = gemini_processor.GeminiProcessor(
    model_name="gemini-2.5-flash",
    temperature=0.3,
    api_key=os.getenv("GEMINI_API_KEY"),
    enable_google_search=False,
)

def safe_move(src, dst):
    if os.path.exists(dst):
        base, ext = os.path.splitext(dst)
        dst = f"{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
    shutil.move(src, dst)
    return dst

def loop_local_files(Loop_dir="Resume_inputs", prompt_template_path="prompt_engineering_eda.md", collection_name="Pretty_resume_Test"):
    for filename in os.listdir(Loop_dir):
        try:
            file_path = os.path.join(Loop_dir, filename)
            if not os.path.isfile(file_path):
                continue

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
            response = gemini.process_file(
                prompt_template_path=prompt_template_path,
                file_path=file_path
            )

            save_single_LLM_response_to_mongodb(
                llm_response=response,
                file_path=file_path, #File path used to get filename, raw bytes, industry prefix, and file size (all metadata)
                db_name="Resume_study",
                collection_name=collection_name,
                mongo_client=mongo_client
            )

            processed_dir = "data/Processed_resumes"
            os.makedirs(processed_dir, exist_ok=True)
            dest_path = safe_move(file_path, os.path.join(processed_dir, processed_filename))
            logger.info(f'Successfully processed file: {processed_filename}')
        except Exception as e:
            logger.error(f"Failed to process {filename}: {str(e)}", exc_info=True)

if __name__ == "__main__":
    loop_local_files(
        Loop_dir="Resume_inputs",
        prompt_template_path="Prompt_templates/Prompt_resume_data+EDA extraction.md",
        collection_name="single_agent_test")