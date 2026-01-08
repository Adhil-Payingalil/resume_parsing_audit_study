"""
Industry-Label Analysis from MongoDB Collection
==============================================

This script fetches industry_prefix and job label pairs from the MongoDB collection 
where Phase 1 workflow results are stored. It extracts the actual data from each 
document and creates a CSV with Industry and Label columns.

Data Structure:
--------------
The script handles the nested MongoDB structure:
document
├── industry_prefix (string) - e.g., "ITC", "HRC"
└── resume_data (object)
    └── resume_data (object)
        └── basics (object)
            └── label (string) - e.g., "Product Designer", "Software Engineer"

Usage:
------
cd "Adhoc analysis"
python fetch_industry_label_pairs.py

Output:
-------
- Console: Summary statistics and first 20 pairs
- CSV Files in output/ folder:
  * industry_and_labels.csv - Main output with Industry and Label columns
  * industry_labels_detailed.csv - Includes File_ID for reference
  * fetch_summary.csv - Summary statistics

Example Output:
--------------
Industry,Label
ITC,Product Designer
HRC,Software Engineer
...

Error Handling:
--------------
- Tracks documents missing industry_prefix
- Tracks documents missing resume_data
- Tracks documents missing label
- Provides detailed logging for debugging

Dependencies:
------------
- MongoDB connection (via libs.mongodb)
- Environment variables (.env file)
- Python standard libraries: os, sys, json, csv
"""

import os
import sys
import json
import csv
from collections import defaultdict
from dotenv import load_dotenv

# Add the project root to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from libs.mongodb import _get_mongo_client
from utils import get_logger

# Load environment variables
load_dotenv()

# Setup logging
logger = get_logger(__name__)

# Configuration
DB_NAME = "Resume_study"
COLLECTION_NAME = "Standardized_resume_data"

def fetch_industry_label_pairs():
    """
    Fetch actual industry_prefix and label pairs from each document in MongoDB.
    
    Returns:
        dict: Dictionary containing pairs and summary statistics
    """
    # Get MongoDB client
    mongo_client = _get_mongo_client()
    if not mongo_client:
        logger.error("Failed to connect to MongoDB")
        return None
    
    try:
        db = mongo_client[DB_NAME]
        collection = db[COLLECTION_NAME]
        
        # Get total document count
        total_docs = collection.count_documents({})
        logger.info(f"Total documents in collection: {total_docs}")
        
        # Fetch all documents
        cursor = collection.find({})
        
        # List to store industry-label pairs
        pairs = []
        
        # Track documents with missing data
        docs_without_industry_prefix = 0
        docs_without_resume_data = 0
        docs_without_label = 0
        
        # Process each document
        for doc in cursor:
            file_id = doc.get('file_id', 'unknown')
            
            # Extract industry_prefix
            industry_prefix = doc.get('industry_prefix')
            if not industry_prefix:
                docs_without_industry_prefix += 1
                logger.warning(f"Document {file_id} missing industry_prefix")
                continue
            
            # Extract resume_data.resume_data.basics.label (nested structure)
            resume_data = doc.get('resume_data', {})
            if not resume_data:
                docs_without_resume_data += 1
                logger.warning(f"Document {file_id} missing resume_data")
                continue
            
            # Handle nested structure: resume_data.resume_data.basics.label
            nested_resume_data = resume_data.get('resume_data', {})
            if nested_resume_data:
                basics = nested_resume_data.get('basics', {})
                if basics:
                    label = basics.get('label')
                else:
                    # Fallback: check if label is directly in nested_resume_data
                    label = nested_resume_data.get('label')
                    if not label:
                        # Check if label is nested in a different structure
                        # Common patterns in LLM responses
                        for key in ['job_title', 'position', 'title', 'role']:
                            if key in nested_resume_data:
                                label = nested_resume_data[key]
                                break
            else:
                # Fallback: check if label is directly in resume_data
                label = resume_data.get('label')
                if not label:
                    # Check if label is nested in a different structure
                    # Common patterns in LLM responses
                    for key in ['job_title', 'position', 'title', 'role']:
                        if key in resume_data:
                            label = resume_data[key]
                            break
            
            if label:
                pairs.append({
                    'file_id': file_id,
                    'industry': industry_prefix,
                    'label': label
                })
            else:
                docs_without_label += 1
                logger.warning(f"Document {file_id} missing label in resume_data")
        
        # Log summary
        logger.info(f"Successfully extracted {len(pairs)} industry-label pairs")
        logger.info(f"Documents without industry_prefix: {docs_without_industry_prefix}")
        logger.info(f"Documents without resume_data: {docs_without_resume_data}")
        logger.info(f"Documents without label: {docs_without_label}")
        
        return {
            'pairs': pairs,
            'summary': {
                'total_documents': total_docs,
                'successful_pairs': len(pairs),
                'docs_without_industry_prefix': docs_without_industry_prefix,
                'docs_without_resume_data': docs_without_resume_data,
                'docs_without_label': docs_without_label
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching data from MongoDB: {e}")
        return None
    finally:
        mongo_client.close()
        logger.info("Closed MongoDB connection")

def save_results_to_files(results):
    """
    Save the results to CSV files for further analysis.
    
    Args:
        results (dict): The results dictionary from fetch_industry_label_pairs()
    """
    if not results:
        logger.error("No results to save")
        return
    
    # Create output directory within Adhoc analysis folder
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)
    
    # Save industry-label pairs to CSV
    pairs_file = os.path.join(output_dir, "industry_and_labels.csv")
    with open(pairs_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Industry', 'Label'])
        
        for pair in results['pairs']:
            writer.writerow([pair['industry'], pair['label']])
    
    # Save detailed pairs with file_id to CSV
    detailed_file = os.path.join(output_dir, "industry_labels_detailed.csv")
    with open(detailed_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['File_ID', 'Industry', 'Label'])
        
        for pair in results['pairs']:
            writer.writerow([pair['file_id'], pair['industry'], pair['label']])
    
    # Save summary to CSV
    summary_file = os.path.join(output_dir, "fetch_summary.csv")
    with open(summary_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['metric', 'value'])
        for key, value in results['summary'].items():
            writer.writerow([key, value])
    
    # Also save as JSON for compatibility
    json_file = os.path.join(output_dir, "fetch_results.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Results saved to {output_dir}/")

def print_results(results):
    """
    Print the results in a formatted way.
    
    Args:
        results (dict): The results dictionary from fetch_industry_label_pairs()
    """
    if not results:
        print("No results to display")
        return
    
    print("\n" + "="*60)
    print("INDUSTRY-LABEL PAIRS FROM MONGODB COLLECTION")
    print("="*60)
    
    print(f"\n📊 SUMMARY:")
    print(f"   Total documents: {results['summary']['total_documents']}")
    print(f"   Successful pairs: {results['summary']['successful_pairs']}")
    print(f"   Documents without industry_prefix: {results['summary']['docs_without_industry_prefix']}")
    print(f"   Documents without resume_data: {results['summary']['docs_without_resume_data']}")
    print(f"   Documents without label: {results['summary']['docs_without_label']}")
    
    print(f"\n💼 INDUSTRY-LABEL PAIRS ({len(results['pairs'])}):")
    for i, pair in enumerate(results['pairs'][:20], 1):  # Show first 20 pairs
        print(f"   {i:2d}. {pair['industry']} -> {pair['label']}")
    
    if len(results['pairs']) > 20:
        print(f"   ... and {len(results['pairs']) - 20} more pairs")
    
    print("\n" + "="*60)

def main():
    """
    Main function to execute the fetch and display process.
    """
    logger.info("Starting to fetch industry-label pairs from MongoDB...")
    
    # Fetch industry-label pairs
    results = fetch_industry_label_pairs()
    
    if results:
        # Print results
        print_results(results)
        
        # Save results to files
        save_results_to_files(results)
        
        logger.info("Process completed successfully!")
    else:
        logger.error("Failed to fetch results from MongoDB")
        print("❌ Failed to fetch results from MongoDB. Check the logs for details.")

if __name__ == "__main__":
    main() 