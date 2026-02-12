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
setup_logging("apply_cec")
logger = get_logger("ApplyCEC")

DB_NAME = "Resume_study"
COL_NAME = "V2_treated_resumes"

# Global cache for CSV data
CEC_DATA = {}

def load_cec_data():
    global CEC_DATA
    if CEC_DATA: return
    
    csv_path = os.path.join(os.path.dirname(__file__), "CEC_ontario_college_graduate_certificates.csv")
    try:
        df = pd.read_csv(csv_path)
        # Group by sector
        for sector, group in df.groupby("sector"):
            CEC_DATA[sector.upper()] = group.to_dict("records")
        logger.info(f"Loaded CEC data for {len(CEC_DATA)} sectors. Sectors: {list(CEC_DATA.keys())}")
        if CEC_DATA:
             first_val = list(CEC_DATA.values())[0][0]
             logger.info(f"Sample CSV Row Keys: {list(first_val.keys())}")
    except Exception as e:
        logger.error(f"Failed to load CSV: {e}")

def get_deterministic_cec(sector: str, doc_id: str, t_type: str) -> Dict[str, Any]:
    load_cec_data()
    candidates = CEC_DATA.get(sector, [])
    if not candidates: 
        logger.warning(f"No CEC candidates for sector: {sector}")
        return None
        
    # Extract base_id for seeding
    base_id = doc_id.split('_Type_')[0].replace('.pdf', '')
    
    # Seeded Shuffle
    rng = random.Random(base_id)
    shuffled = list(candidates)
    rng.shuffle(shuffled)
    
    # Select distinct index based on type
    # Type I gets index 0, Type III gets index 1
    idx = 0
    if t_type.lower() == "type_iii":
        idx = 1
    
    return shuffled[idx % len(shuffled)]

def get_cec_dates(t_type: str) -> Dict[str, str]:
    """Returns (startDate, endDate) based on treatment type."""
    if t_type.lower() == "type_i":
        return {"startDate": "2024-09", "endDate": "2025-08"}
    elif t_type.lower() == "type_iii":
        return {"startDate": "2024-01", "endDate": "2024-12"}
    return None

def apply_cec(doc: Dict[str, Any], dry_run: bool) -> List[str]:
    changes = []
    doc_id = doc.get("document_id")
    t_type = doc.get("treatment_type", "")
    sector = doc.get("industry_prefix", "").upper()
    
    # Only Type I and Type III get CEC
    if t_type.lower() not in ["type_i", "type_iii"]:
        return []
        
    dates = get_cec_dates(t_type)
    if not dates: return []

    # Get metadata or fetch new
    metadata = doc.get("treatment_applied") or doc.get("metadata") or {}
    if isinstance(metadata, str):
        try: metadata = json.loads(metadata)
        except: metadata = {}
        
    cec_meta = metadata.get("Canadian_Certificate") # Check key name? Plan said "Canadian Education" for AEC.
    # If not found, fetch random
    # If not found, fetch deterministic random
    source = "Metadata"
    if not cec_meta:
        cec_meta = get_deterministic_cec(sector, doc_id, t_type)
        source = "Deterministic"
        if not cec_meta:
             return [f"Skipped {doc_id} (No CEC data found for sector {sector})"]

    # Debug: Check for keys
    inst = cec_meta.get("institution") or cec_meta.get("college") or cec_meta.get("College") or cec_meta.get("Institution")
    if not inst:
        logger.warning(f"[{doc_id}] CEC Meta missing institution. Keys: {list(cec_meta.keys())} Source: {source}")

    # Construct New Entry
    new_entry = {
        "institution": inst,
        "location": cec_meta.get("location", "Toronto, ON"),
        "area": cec_meta.get("program") or cec_meta.get("Program") or cec_meta.get("certificate_name") or cec_meta.get("area"),
        "studyType": cec_meta.get("studyType", "Ontario College Graduate Certificate"),
        "startDate": dates["startDate"],
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
    
    if "education" not in resume: resume["education"] = []
    
    # Insert at position 1 (After AEC)
    # AEC should be at 0. So we insert at 1.
    # Check if 0 exists.
    if len(resume["education"]) == 0:
        # If no AEC (unexpected), insert at 0?
        resume["education"].insert(0, new_entry)
        changes.append(f"Added CEC to {t_type} at Edu[0] (Unexpected: No AEC found)")
    else:
        # Check duplication
        current_1 = resume["education"][1] if len(resume["education"]) > 1 else {}
        if current_1.get("institution") == new_entry["institution"]:
             return [] # Already exists
             
        resume["education"].insert(1, new_entry)
        changes.append(f"Added CEC to {t_type} at Edu[1]: {new_entry['institution']} ({dates['startDate']} - {dates['endDate']})")
        
    return changes

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    logger.info(f"Starting CEC Application. Dry Run: {args.dry_run}")
    
    client = _get_mongo_client()
    col = client[DB_NAME][COL_NAME]
    
    cursor = col.find({"treatment_type": {"$in": ["Type_I", "Type_III"]}})
    count = 0
    
    for doc in cursor:
        try:
            changes = apply_cec(doc, args.dry_run)
            if changes and "Skipped" not in changes[0]:
                logger.info(f"[{doc.get('document_id')}] {', '.join(changes)}")
                count += 1
                if not args.dry_run:
                    col.update_one({"_id": doc["_id"]}, {"$set": {"resume_data": doc["resume_data"]}})
            elif changes:
                logger.debug(f"{changes[0]}")
        except Exception as e:
            logger.error(f"Error processing {doc.get('document_id')}: {e}")
                
    logger.info(f"Finished. Modified {count} documents.")

if __name__ == "__main__":
    main()
