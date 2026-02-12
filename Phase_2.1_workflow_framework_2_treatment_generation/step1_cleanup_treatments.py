import os
import sys
import json
import argparse
from typing import Dict, Any, List
from dotenv import load_dotenv

# Add project root (adjusted for subfolder)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from libs.mongodb import _get_mongo_client
from utils import setup_logging, get_logger

load_dotenv()
setup_logging("cleanup_treatments")
logger = get_logger("CleanupTreatments")

DB_NAME = "Resume_study"
COL_NAME = "V2_treated_resumes"

def is_safe_to_delete_edu(edu_entry: Dict[str, Any]) -> bool:
    """Safety check: Must be a Certificate or contain specific keywords."""
    study_type = edu_entry.get("studyType", "").lower()
    institution = edu_entry.get("institution", "").lower()
    
    if "certificate" in study_type: return True
    if "acces employment" in institution: return True
    if "connections" in edu_entry.get("area", "").lower(): return True
    
    return False

def clean_document(doc: Dict[str, Any], dry_run: bool) -> List[str]:
    """Clean a single document based on its type."""
    changes = []
    
    # Handle Resume Data Structure
    # Some docs have resume_data.resume_data, others might be flat.
    # The 'doc' passed here is the dictionary from MongoDB.
    
    # We want to modify the inner metadata object
    if "resume_data" not in doc: return [] 
    
    # Pointer to the dict containing 'education' and 'work_experience'
    # Check if nested
    if "resume_data" in doc["resume_data"]:
        resume = doc["resume_data"]["resume_data"]
    else:
        resume = doc["resume_data"]
        
    t_type = doc.get("treatment_type", "")
    metadata = doc.get("treatment_applied") or doc.get("metadata") or {}
    if isinstance(metadata, str):
        try: metadata = json.loads(metadata)
        except: metadata = {}

    # --- LOGIC BY TYPE ---
    
    # 1. Type I: AEC (Edu[0])
    if t_type == "Type_I":
        edu_list = resume.get("education", [])
        if edu_list:
            first = edu_list[0]
            if is_safe_to_delete_edu(first):
                removed = edu_list.pop(0)
                changes.append(f"Removed Edu[0] (Type I): {removed.get('institution')}")
    
    # 2. Type II: AEC (Edu[0]) + CWE (Work[0])
    elif t_type == "Type_II":
        # AEC
        edu_list = resume.get("education", [])
        if edu_list:
            first = edu_list[0]
            if is_safe_to_delete_edu(first):
                removed = edu_list.pop(0)
                changes.append(f"Removed Edu[0] (Type II): {removed.get('institution')}")
        
        # CWE
        # Safety: Compare with metadata company if available
        work_list = resume.get("work_experience", [])
        if work_list:
            first = work_list[0]
            cwe_target = metadata.get("Canadian_Work_Experience", {}).get("company", "").lower()
            current_comp = first.get("company", "").lower()
            
            # If metadata matches OR it looks like a treatment (short duration? specific string?)
            # User didn't specify strict rule for work, but position 0 is likely.
            # We strictly match company if possible, or assume 0 if dry run confirms.
            matched = False
            if cwe_target and cwe_target == current_comp: matched = True
            elif not cwe_target: 
                # Fallback if no metadata: Log warning but maybe skip?
                # For now, let's look for "project" or "intern" in position as weak signal?
                # actually, let's rely on metadata if present.
                pass
            
            if matched:
                removed = work_list.pop(0)
                changes.append(f"Removed Work[0] (Type II): {removed.get('company')}")

    # 3. Type III: AEC + CWE + CEC (Mixed)
    # Previous logic said Type III was "CEC + AEC + CWE".
    # Need to know ORDER. 
    # Current V2 data seems to be AEC + CWE (based on debug_data_any.json which was Type_III).
    # In debug_data_any.json (Type III), we saw:
    # Edu[0]: "ACCES Employment..." (AEC)
    # Work[0]: "ARCortex" (CWE)
    # So it follows the same pattern.
    elif t_type == "Type_III":
        # AEC
        edu_list = resume.get("education", [])
        if edu_list:
            first = edu_list[0]
            if is_safe_to_delete_edu(first):
                removed = edu_list.pop(0)
                changes.append(f"Removed Edu[0] (Type III): {removed.get('institution')}")
        
        # CWE
        work_list = resume.get("work_experience", [])
        if work_list:
            first = work_list[0]
            cwe_target = metadata.get("Canadian_Work_Experience", {}).get("company", "").lower()
            current_comp = first.get("company", "").lower()
            
            if cwe_target and cwe_target == current_comp:
                removed = work_list.pop(0)
                changes.append(f"Removed Work[0] (Type III): {removed.get('company')}")
            # Identify if additional CEC exists? 
            # If existing data has CEC, it might be in Edu list. 
            # Check debug data -> Type III had only AEC in education list shown in debug output.
            
    return changes

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    logger.info(f"Starting Cleanup (Position Based). Dry Run: {args.dry_run}")
    
    client = _get_mongo_client()
    col = client[DB_NAME][COL_NAME]
    
    cursor = col.find({})
    count = 0
    
    for doc in cursor:
        changes = clean_document(doc, args.dry_run)
        if changes:
            logger.info(f"[{doc.get('document_id')}] {', '.join(changes)}")
            count += 1
            if not args.dry_run:
                # Save
                col.update_one({"_id": doc["_id"]}, {"$set": {"resume_data": doc["resume_data"]}})
                
    logger.info(f"Finished. Modified {count} documents.")

if __name__ == "__main__":
    main()
