import os
import sys
import json
import argparse
import random
import pandas as pd
from typing import Dict, Any, List
from dotenv import load_dotenv

# Add project root 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from libs.mongodb import _get_mongo_client
from utils import setup_logging, get_logger

load_dotenv()
setup_logging("apply_aec")
logger = get_logger("ApplyAEC")

DB_NAME = "Resume_study"
COL_NAME = "V2_treated_resumes"

def get_date_range(t_type: str) -> Dict[str, str]:
    """Returns (startDate, endDate) based on treatment type."""
    if t_type in ["control", "Control", "Type_I", "Type I"]:
        return {"startDate": "2025-09", "endDate": "2025-12"}
    elif t_type in ["Type_II", "Type II"]:
        return {"startDate": "2025-01", "endDate": "2025-04"}
    elif t_type in ["Type_III", "Type III"]:
        return {"startDate": "2025-02", "endDate": "2025-05"}
    else:
        # Fallback?
        return {"startDate": "2025-09", "endDate": "2025-12"}

# Global cache for CSV data
AEC_DATA = {}

def load_aec_data():
    global AEC_DATA
    if AEC_DATA: return
    
    # Use the CSV in the current directory
    csv_path = os.path.join(os.path.dirname(__file__), "AEC_ACESS_education_credentials.csv")
    try:
        df = pd.read_csv(csv_path)
        # Group by sector
        for sector, group in df.groupby("sector"):
            AEC_DATA[sector.upper()] = group.to_dict("records")
        logger.info(f"Loaded AEC data for {len(AEC_DATA)} sectors.")
    except Exception as e:
        logger.error(f"Failed to load CSV: {e}")

def get_deterministic_aec(sector: str, doc_id: str, t_type: str) -> Dict[str, Any]:
    """Selects an AEC option consistently for a given resume ID and type."""
    load_aec_data()
    candidates = AEC_DATA.get(sector, [])
    if not candidates: return None
    
    # Extract base_id for seeding (e.g. 'CCC resume 14')
    # Use .replace('.pdf', '') to ensure "CCC resume 14.pdf" and "CCC resume 14" match
    base_id = doc_id.split('_Type_')[0].replace('_control', '').replace('_Control', '').replace('.pdf', '')
    
    # Seeded Shuffle
    rng = random.Random(base_id)
    shuffled = list(candidates)
    rng.shuffle(shuffled)
    
    # Select distinct index based on type
    type_map = {"control": 0, "type_i": 1, "type_ii": 2, "type_iii": 3}
    idx = type_map.get(t_type.lower(), 0) % len(shuffled)
    
    return shuffled[idx]

def apply_aec(doc: Dict[str, Any], dry_run: bool) -> List[str]:
    changes = []
    doc_id = doc.get("document_id")
    t_type = doc.get("treatment_type", "")
    sector = doc.get("industry_prefix", "").upper() # e.g. CCC
    
    # Get metadata
    metadata = doc.get("treatment_applied") or doc.get("metadata") or {}
    if isinstance(metadata, str):
        try: metadata = json.loads(metadata)
        except: metadata = {}
        
    aec_meta = metadata.get("Canadian_Education")
    
    # Fallback / Override Logic
    # User Request: "Assign different AEC... from the 4 available options"
    # To strictly enforce this, we should prioritize the deterministic selection 
    # over legacy metadata if the user wants to ensure diversity now.
    # However, standard practice is usually to respect metadata. 
    # Given the user specifically asked for this NOW, I will use the deterministic getter 
    # if aec_meta is missing OR if we want to force update (not implemented, assuming missing/dry-run).
    # Update: We will use deterministic fetch if metadata is missing. 
    
    if not aec_meta:
        aec_meta = get_deterministic_aec(sector, doc_id, t_type)
        if aec_meta:
             logger.debug(f"[{doc_id}] Assigned deterministic AEC: {aec_meta.get('certificate_name')}")
    
    if not aec_meta:
        return [f"Skipped {doc_id} (No AEC metadata and no fallback)"]

    # Construct New Entry
    dates = get_date_range(t_type)
    
    new_entry = {
        "institution": aec_meta.get("affiliate_university"),
        "location": "Toronto, ON",
        "area": aec_meta.get("certificate_name"),
        "studyType": "Certificate",
        "startDate": "", # User requested BLANK start date
        "endDate": dates["endDate"],
        "score": "",
        "coursework": []
    }
    
    # Handle Resume Data
    if "resume_data" not in doc: return []
    if "resume_data" in doc["resume_data"]:
        resume = doc["resume_data"]["resume_data"]
    else:
        resume = doc["resume_data"]
        
    # Insert at 0
    if "education" not in resume: resume["education"] = []
    
    # Double check we aren't duplicating if run twice
    current_0 = resume["education"][0] if resume["education"] else {}
    if current_0.get("institution") == new_entry["institution"] and current_0.get("startDate") == new_entry["startDate"]:
         return [] # Already applied
         
    resume["education"].insert(0, new_entry)
    changes.append(f"Added AEC to {t_type}: {new_entry['institution']} ({dates['startDate']} - {dates['endDate']})")
    
    # --- LOGIC: CONTROL Work Date Update ---
    # User Request: "Change the end date of the latest work experience (0 Object) to Jun 2025"
    if t_type.lower() == "control":
        work_list = resume.get("work_experience", [])
        if work_list:
            # We assume index 0 is the latest
            work_list[0]["endDate"] = "2025-06"
            changes.append(f"Updated Control Work[0] EndDate to 2025-06")

    # --- LOGIC: TYPE I Work Date Update ---
    # User Request: "Work experience (0) end date needs to be updated to Jun 2024 (2024-06)"
    if t_type.lower() == "type_i":
        work_list = resume.get("work_experience", [])
        if work_list:
            work_list[0]["endDate"] = "2024-06"
            changes.append(f"Updated Type I Work[0] EndDate to 2024-06")

    # --- LOGIC: TYPE II Work Date Update ---
    # User Request: "Work experience (0) gets updated to Dec 2024 (2024-12)"
    if t_type.lower() == "type_ii":
        work_list = resume.get("work_experience", [])
        if work_list:
            work_list[0]["endDate"] = "2024-12"
            changes.append(f"Updated Type II Work[0] EndDate to 2024-12")

    # --- LOGIC: TYPE III Work Date Update ---
    # User Request: "existing work experience (0) gets updated to Nov 2023 (2023-11)"
    if t_type.lower() == "type_iii":
        work_list = resume.get("work_experience", [])
        if work_list:
            work_list[0]["endDate"] = "2023-11"
            changes.append(f"Updated Type III Work[0] EndDate to 2023-11")

    return changes

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    logger.info(f"Starting AEC Application. Dry Run: {args.dry_run}")
    
    client = _get_mongo_client()
    col = client[DB_NAME][COL_NAME]
    
    cursor = col.find({})
    count = 0
    
    for doc in cursor:
        try:
            changes = apply_aec(doc, args.dry_run)
            if changes and "Skipped" not in changes[0]:
                logger.info(f"[{doc.get('document_id')}] {', '.join(changes)}")
                count += 1
                if not args.dry_run:
                    col.update_one({"_id": doc["_id"]}, {"$set": {"resume_data": doc["resume_data"]}})
            elif changes:
                logger.debug(f"{changes[0]}") # Log skips as debug
        except Exception as e:
            logger.error(f"Error processing {doc.get('document_id')}: {e}")
                
    logger.info(f"Finished. Modified {count} documents.")

if __name__ == "__main__":
    main()
