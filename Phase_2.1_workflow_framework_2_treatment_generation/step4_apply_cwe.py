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
setup_logging("apply_cwe")
logger = get_logger("ApplyCWE")

DB_NAME = "Resume_study"
COL_NAME = "V2_treated_resumes"

# Global cache for CSV data
CWE_DATA = {}

def load_cwe_data():
    global CWE_DATA
    if CWE_DATA: return
    
    csv_path = os.path.join(os.path.dirname(__file__), "CWE_work_experience_credentials.csv")
    try:
        df = pd.read_csv(csv_path)
        # Group by sector
        for sector, group in df.groupby("sector"):
            CWE_DATA[sector.upper()] = group.to_dict("records")
        logger.info(f"Loaded CWE data for {len(CWE_DATA)} sectors. Sectors: {list(CWE_DATA.keys())}")
        if CWE_DATA:
             first_val = list(CWE_DATA.values())[0][0]
             logger.info(f"Sample CWE CSV Row Keys: {list(first_val.keys())}")
    except Exception as e:
        logger.error(f"Failed to load CSV: {e}")

def get_deterministic_cwe(sector: str, doc_id: str, t_type: str) -> Dict[str, Any]:
    load_cwe_data()
    candidates = CWE_DATA.get(sector, [])
    if not candidates: 
        logger.warning(f"No CWE candidates for sector: {sector}")
        return None
        
    # Extract base_id for seeding
    base_id = doc_id.split('_Type_')[0].replace('.pdf', '')
    
    # Seeded Shuffle
    rng = random.Random(base_id)
    shuffled = list(candidates)
    rng.shuffle(shuffled)
    
    # Select distinct index based on type
    # Type II gets index 0, Type III gets index 1
    idx = 0
    if t_type.lower() == "type_iii":
        idx = 1
    
    return shuffled[idx % len(shuffled)]

def get_cwe_dates(t_type: str) -> Dict[str, str]:
    """Returns (startDate, endDate) based on treatment type."""
    if t_type.lower() == "type_ii":
        return {"startDate": "2025-05", "endDate": "2025-11"}
    elif t_type.lower() == "type_iii":
        return {"startDate": "2025-06", "endDate": "2025-12"}
    return None

def apply_cwe(doc: Dict[str, Any], dry_run: bool) -> List[str]:
    changes = []
    doc_id = doc.get("document_id")
    t_type = doc.get("treatment_type", "")
    sector = doc.get("industry_prefix", "").upper()
    
    # Only Type II and Type III get CWE
    # Only Type II and Type III get CWE
    if t_type.lower() not in ["type_ii", "type_iii"]:
        return []
        
    dates = get_cwe_dates(t_type)
    if not dates: return ["No Dates For Type"]

    # Get metadata or fetch new
    metadata = doc.get("treatment_applied") or doc.get("metadata") or {}
    if isinstance(metadata, str):
        try: metadata = json.loads(metadata)
        except: metadata = {}
        
    cwe_meta = metadata.get("Canadian_Work_Experience") 
    
    # Validate metadata if it exists
    if cwe_meta:
        if not cwe_meta.get("Name of Organization Providing Project"):
            logger.info(f"[{doc_id}] Old metadata found but missing Name. Refreshing from CSV.")
            cwe_meta = None

    # If not found or invalid, fetch deterministic
    if not cwe_meta:
        cwe_meta = get_deterministic_cwe(sector, doc_id, t_type)
        if not cwe_meta:
             return [f"Skipped {doc_id} (No CWE data found for sector {sector})"]
             
    # Construct New Entry
    highlights = []
    # User Request: Don't do 'Project: ...' in highlights
    # if cwe_meta.get("Title of Experiential Learning Project"):
    #     highlights.append(f"Project: {cwe_meta.get('Title of Experiential Learning Project')}")
    
    for i in range(1, 5):
        h = cwe_meta.get(f"highlight_{i}")
        if h and isinstance(h, str):
            highlights.append(h)
            
    name = cwe_meta.get("Name of Organization Providing Project")
    if not name: return ["Skipped (Missing Name in CSV)"]
    
    new_entry = {
        "name": name,
        "position": cwe_meta.get("Position"),
        "location": cwe_meta.get("Location ", "Toronto, ON").strip(), # Note space in key "Location "
        "startDate": dates["startDate"],
        "endDate": dates["endDate"],
        "highlights": highlights,
        "summary": "",
        "url": ""
    }
    
    # Handle Resume Data
    if "resume_data" not in doc: return ["No Resume Data"]
    if "resume_data" in doc["resume_data"]:
        resume = doc["resume_data"]["resume_data"]
    else:
        resume = doc["resume_data"]
    
    if "work_experience" not in resume: resume["work_experience"] = []
    
    # Insert at position 0 (Most Recent)
    current_0 = resume["work_experience"][0] if len(resume["work_experience"]) > 0 else {}
    if current_0.get("name") == new_entry["name"]:
         return [f"Duplicate: {new_entry['name']} already at pos 0"]
         
    resume["work_experience"].insert(0, new_entry)
    changes.append(f"Added CWE to {t_type} at Work[0]: {new_entry['name']} ({dates['startDate']} - {dates['endDate']})")
        
    return changes

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    logger.info(f"Starting CWE Application. Dry Run: {args.dry_run}")
    
    client = _get_mongo_client()
    col = client[DB_NAME][COL_NAME]
    
    cursor = col.find({})
    count = 0
    
    for i, doc in enumerate(cursor):
        try:
            t_type = doc.get("treatment_type", "")
            if i < 3: logger.info(f"Doc {i} Type: {t_type}")
            
            if t_type.lower() not in ["type_ii", "type_iii"]:
                continue

            changes = apply_cwe(doc, args.dry_run)
            if changes and "Skipped" not in changes[0] and "Duplicate" not in changes[0] and "No Dates" not in changes[0]:
                logger.info(f"[{doc.get('document_id')}] {', '.join(changes)}")
                count += 1
                if not args.dry_run:
                    col.update_one({"_id": doc["_id"]}, {"$set": {"resume_data": doc["resume_data"]}})
            elif changes:
                # Log why it was skipped/duplicate at info level for dry run visibility
                logger.info(f"MSG [{doc.get('document_id')}]: {changes[0]}")
            else:
                 logger.info(f"MSG [{doc.get('document_id')}]: Returned Empty.")
        except Exception as e:
            logger.error(f"Error processing {doc.get('document_id')}: {e}")
                
    logger.info(f"Finished. Modified {count} documents.")
                


if __name__ == "__main__":
    main()
