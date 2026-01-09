"""
Phase 2 Runner: Treatment Generation
====================================

This script orchestrates the generation of treated resumes.
It uses:
1.  `libs.treatment_generator` for the heavy lifting.
2.  `company_research_ui` for manual verification (optional).
3.  `utils.setup_logging` for structured output.

Usage:
    python run_phase_2.py --sector ITC
"""

import os
import sys
import time
import argparse
import datetime
from dotenv import load_dotenv

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from libs.treatment_generator import TreatmentGenerator
from libs.mongodb import _get_mongo_client, get_all_file_ids, get_document_by_fileid
from Phase_2_Workflow.company_research_ui import run_ui_validation
from utils import setup_logging, get_logger

# Config
load_dotenv()
setup_logging("phase_2") # structured logging
logger = get_logger("Phase2Runner")

DB_NAME = "Resume_study"
SOURCE_COL = "Standardized_resume_data"
TARGET_COL = "Treated_resumes"

# Delays (Rate Limiting)
DELAY_FILES = 3.0
DELAY_QUICK = 2.0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sector", type=str, required=True, help="Industry Sector (e.g. ITC)")
    parser.add_argument("--files", nargs='+', help="Specific file IDs to process")
    parser.add_argument("--skip-ui", action="store_true", help="Skip manual UI validation (Auto-accept)")
    args = parser.parse_args()
    
    sector = args.sector.upper()
    logger.info(f"Starting Phase 2 for Sector: {sector}")

    # 1. Initialize Generator
    generator = TreatmentGenerator(sector)
    mongo_client = _get_mongo_client()
    target_collection = mongo_client[DB_NAME][TARGET_COL]
    
    # 2. Get Files
    all_files = get_all_file_ids(DB_NAME, SOURCE_COL, mongo_client)
    if args.files:
         files_to_process = [f for f in args.files if f in all_files]
    else:
         files_to_process = [f for f in all_files if sector in f]
    
    if not files_to_process:
        logger.error(f"No files found for {sector}")
        return

    logger.info(f"Processing {len(files_to_process)} files...")
    
    # 3. Processing Loop
    for idx, file_id in enumerate(files_to_process):
        logger.info(f"--- Processing {idx+1}/{len(files_to_process)}: {file_id} ---")
        if idx > 0: time.sleep(DELAY_FILES)
        
        try:
            # A. Fetch Data
            doc = get_document_by_fileid(DB_NAME, SOURCE_COL, file_id, mongo_client)
            resume_data = doc.get("resume_data", {})
            
            # B. Company Research (Manual Loop)
            mappings = []
            while True:
                logger.info("Generating company mappings...")
                mappings = generator.research_companies_headless(resume_data)
                
                if args.skip_ui:
                     break # Auto-accept
                
                # Launch UI
                logger.info("Waiting for user validation in UI...")
                status, validated = run_ui_validation(mappings)
                
                if status == "accepted":
                    mappings = validated
                    break
                elif status == "retry":
                    logger.info("User requested retry...")
                    continue
                else:
                    logger.warning("User cancelled. Skipping file.")
                    mappings = None
                    break
            
            if not mappings: continue
            
            # C. Remove NA Elements
            logger.info("Removing NA elements...")
            clean_data = generator.remove_north_american_elements(resume_data)
            time.sleep(DELAY_QUICK)

            # D. Save Control
            control_doc = {
                "original_file_id": file_id,
                 "document_id": f"{file_id}_control",
                 "treatment_type": "control",
                 "resume_data": generator.replace_companies_and_positions(clean_data, mappings, "Type_I"), # Use Type I for control generally or just generic
                 "timestamp": datetime.datetime.now()
            }
            # Note: Logic indicates control is just "Cleaned + Mapped" with no extra CEC/CWE
            target_collection.insert_one(control_doc)
            logger.info("Saved Control.")
            
            # E. Generate Treatments (I, II, III)
            prompts = generator.prepare_treatment_prompts(resume_data)
            if not prompts:
                logger.error("Failed to prepare prompts")
                continue
                
            for t_type, p_data in prompts.items():
                logger.info(f"Generating {t_type}...")
                treated_data = generator.generate_treatment(p_data["prompt"])
                
                if treated_data:
                    # Apply mappings for this specific type
                    final_data = generator.replace_companies_and_positions(treated_data, mappings, t_type)
                    
                    # Calculate Similarity
                    sim_score = generator.calculate_similarity(control_doc["resume_data"], final_data, t_type)
                    
                    # Save
                    t_doc = {
                        "original_file_id": file_id,
                        "document_id": f"{file_id}_{t_type.lower()}",
                        "treatment_type": t_type,
                        "resume_data": final_data,
                        "similarity_score": sim_score,
                        "metadata": p_data["treatment_applied"],
                        "timestamp": datetime.datetime.now()
                    }
                    target_collection.insert_one(t_doc)
                    logger.info(f"Saved {t_type} (Similarity: {sim_score:.2f})")
                
                time.sleep(DELAY_QUICK)

        except Exception as e:
            logger.error(f"Error processing {file_id}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
