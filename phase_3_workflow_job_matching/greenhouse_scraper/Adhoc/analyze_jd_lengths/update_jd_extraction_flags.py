import os
import json
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Get the script directory and set up paths
script_dir = Path(__file__).parent
data_dir = script_dir / 'data'
logs_dir = Path('logs')

# Create directories if they don't exist
data_dir.mkdir(exist_ok=True)
logs_dir.mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(logs_dir / 'update_jd_extraction_flags.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "Resume_study")
MONGODB_COLLECTION = "Job_postings_greenhouse"

class JDExtractionFlagUpdater:
    def __init__(self):
        self.mongo_client = None
        self.collection = None
        self.setup_mongodb_connection()
        
    def setup_mongodb_connection(self):
        """Set up MongoDB connection"""
        if not MONGODB_URI:
            raise Exception("MONGODB_URI not found in environment variables")
        
        try:
            self.mongo_client = MongoClient(MONGODB_URI)
            # Test the connection
            self.mongo_client.admin.command('ping')
            db = self.mongo_client[MONGODB_DATABASE]
            self.collection = db[MONGODB_COLLECTION]
            
            logger.info(f"✅ Connected to MongoDB: {MONGODB_DATABASE}.{MONGODB_COLLECTION}")
        except ConnectionFailure as e:
            raise Exception(f"Failed to connect to MongoDB: {e}")
        except Exception as e:
            raise Exception(f"MongoDB setup error: {e}")
    
    def find_low_quality_jobs(self, word_threshold: int = 50, char_threshold: int = 200) -> List[Dict]:
        """Find jobs with low quality descriptions based on length thresholds"""
        
        # Query for jobs that have length data and meet low quality criteria
        query = {
            "$and": [
                {"job_description": {"$exists": True, "$ne": None, "$ne": ""}},
                {"jd_word_count": {"$exists": True}},
                {"jd_char_count": {"$exists": True}},
                {
                    "$or": [
                        {"jd_word_count": {"$lt": word_threshold}},
                        {"jd_char_count": {"$lt": char_threshold}}
                    ]
                }
            ]
        }
        
        low_quality_jobs = list(self.collection.find(query))
        
        logger.info(f"Found {len(low_quality_jobs)} jobs with low quality descriptions")
        logger.info(f"Criteria: < {word_threshold} words OR < {char_threshold} characters")
        
        return low_quality_jobs
    
    def preview_updates(self, low_quality_jobs: List[Dict]) -> Dict:
        """Preview what would be updated without making changes"""
        
        currently_true = 0
        currently_false = 0
        currently_missing = 0
        
        for job in low_quality_jobs:
            jd_extraction = job.get('jd_extraction')
            
            if jd_extraction is True:
                currently_true += 1
            elif jd_extraction is False:
                currently_false += 1
            else:
                currently_missing += 1
        
        preview_data = {
            'total_low_quality': len(low_quality_jobs),
            'currently_jd_extraction_true': currently_true,
            'currently_jd_extraction_false': currently_false,
            'currently_jd_extraction_missing': currently_missing,
            'would_be_updated': currently_true + currently_missing
        }
        
        return preview_data
    
    def update_jd_extraction_flags(self, low_quality_jobs: List[Dict], dry_run: bool = True) -> Dict:
        """Update jd_extraction flag to False for low quality jobs"""
        
        if dry_run:
            logger.info("🔍 DRY RUN MODE - No actual changes will be made")
        else:
            logger.info("🔄 LIVE UPDATE MODE - Making actual changes to database")
        
        updated_count = 0
        already_false_count = 0
        error_count = 0
        updated_jobs = []
        
        for job in low_quality_jobs:
            try:
                job_id = job['_id']
                current_jd_extraction = job.get('jd_extraction')
                
                # Only update if jd_extraction is currently True or missing
                if current_jd_extraction is not False:
                    
                    update_data = {
                        'jd_extraction': False,
                        'jd_extraction_updated_at': datetime.now(),
                        'jd_extraction_update_reason': f"Low quality: {job.get('jd_word_count', 0)} words, {job.get('jd_char_count', 0)} chars"
                    }
                    
                    if not dry_run:
                        result = self.collection.update_one(
                            {'_id': job_id},
                            {'$set': update_data}
                        )
                        
                        if result.modified_count > 0:
                            updated_count += 1
                            updated_jobs.append({
                                'job_id': str(job_id),
                                'title': job.get('title', 'N/A'),
                                'company': job.get('company', 'N/A'),
                                'word_count': job.get('jd_word_count', 0),
                                'char_count': job.get('jd_char_count', 0),
                                'job_link': job.get('job_link', 'N/A'),
                                'previous_jd_extraction': current_jd_extraction,
                                'new_jd_extraction': False
                            })
                        else:
                            logger.warning(f"⚠️ No changes made to job {job_id}")
                    else:
                        # Dry run - just count what would be updated
                        updated_count += 1
                        updated_jobs.append({
                            'job_id': str(job_id),
                            'title': job.get('title', 'N/A'),
                            'company': job.get('company', 'N/A'),
                            'word_count': job.get('jd_word_count', 0),
                            'char_count': job.get('jd_char_count', 0),
                            'job_link': job.get('job_link', 'N/A'),
                            'previous_jd_extraction': current_jd_extraction,
                            'new_jd_extraction': False
                        })
                        
                    if updated_count % 50 == 0:
                        logger.info(f"{'Would update' if dry_run else 'Updated'} {updated_count} jobs so far...")
                        
                else:
                    already_false_count += 1
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Error {'previewing' if dry_run else 'updating'} job {job.get('_id')}: {e}")
                continue
        
        results = {
            'total_processed': len(low_quality_jobs),
            'updated_count': updated_count,
            'already_false_count': already_false_count,
            'error_count': error_count,
            'updated_jobs': updated_jobs,
            'dry_run': dry_run
        }
        
        action = "Would update" if dry_run else "Updated"
        logger.info(f"✅ {action} {updated_count} jobs with jd_extraction=False")
        logger.info(f"📝 {already_false_count} jobs already had jd_extraction=False")
        if error_count > 0:
            logger.warning(f"⚠️ {error_count} jobs failed to {'preview' if dry_run else 'update'}")
        
        return results
    
    def save_update_report(self, results: Dict, word_threshold: int, char_threshold: int):
        """Save update report to CSV file in data directory"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mode = "dry_run" if results['dry_run'] else "live_update"
        filename = data_dir / f"jd_extraction_update_report_{mode}_{timestamp}.csv"
        
        if results['updated_jobs']:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['job_id', 'title', 'company', 'word_count', 'char_count', 
                             'job_link', 'previous_jd_extraction', 'new_jd_extraction']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results['updated_jobs'])
            
            logger.info(f"✅ Saved update report to {filename}")
        
        # Also save summary to data directory
        summary_filename = data_dir / f"jd_extraction_update_summary_{mode}_{timestamp}.json"
        summary = {
            'timestamp': timestamp,
            'mode': mode,
            'criteria': {
                'word_threshold': word_threshold,
                'char_threshold': char_threshold
            },
            'results': {
                'total_processed': results['total_processed'],
                'updated_count': results['updated_count'],
                'already_false_count': results['already_false_count'],
                'error_count': results['error_count']
            }
        }
        
        with open(summary_filename, 'w', encoding='utf-8') as jsonfile:
            json.dump(summary, jsonfile, indent=2, default=str)
        
        logger.info(f"✅ Saved summary to {summary_filename}")
        
        return filename, summary_filename
    
    def print_update_summary(self, results: Dict, word_threshold: int, char_threshold: int):
        """Print a formatted summary of the update operation"""
        
        mode_text = "DRY RUN PREVIEW" if results['dry_run'] else "LIVE UPDATE RESULTS"
        
        print("\n" + "="*80)
        print(f"JD_EXTRACTION FLAG UPDATE - {mode_text}")
        print("="*80)
        
        print(f"\n🎯 CRITERIA:")
        print(f"   Word count < {word_threshold} OR Character count < {char_threshold}")
        
        print(f"\n📊 RESULTS:")
        print(f"   Total low quality jobs processed: {results['total_processed']:,}")
        
        action = "Would be updated" if results['dry_run'] else "Updated"
        print(f"   Jobs {action.lower()}: {results['updated_count']:,}")
        print(f"   Jobs already jd_extraction=False: {results['already_false_count']:,}")
        
        if results['error_count'] > 0:
            print(f"   Errors encountered: {results['error_count']:,}")
        
        if results['dry_run'] and results['updated_count'] > 0:
            print(f"\n💡 NEXT STEPS:")
            print(f"   Run this script with --live-update to make actual changes")
            print(f"   {results['updated_count']} jobs would have jd_extraction set to False")
        elif not results['dry_run'] and results['updated_count'] > 0:
            print(f"\n✅ SUCCESS:")
            print(f"   {results['updated_count']} jobs now have jd_extraction=False")
            print(f"   These jobs are marked as having low quality descriptions")
        
        print("="*80)
    
    def close_connection(self):
        """Close MongoDB connection"""
        if self.mongo_client:
            self.mongo_client.close()
            logger.info("MongoDB connection closed")

def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Update jd_extraction flags for low quality job descriptions')
    parser.add_argument('--word-threshold', type=int, default=50,
                       help='Word count threshold (default: 50)')
    parser.add_argument('--char-threshold', type=int, default=200,
                       help='Character count threshold (default: 200)')
    parser.add_argument('--live-update', action='store_true',
                       help='Perform live update (default is dry run)')
    
    args = parser.parse_args()
    
    updater = None
    
    try:
        # Initialize updater
        updater = JDExtractionFlagUpdater()
        
        # Find low quality jobs
        logger.info("Finding low quality job descriptions...")
        low_quality_jobs = updater.find_low_quality_jobs(
            word_threshold=args.word_threshold,
            char_threshold=args.char_threshold
        )
        
        if not low_quality_jobs:
            print("✅ No low quality job descriptions found!")
            return
        
        # Preview what would be updated
        preview = updater.preview_updates(low_quality_jobs)
        
        print(f"\n📋 PREVIEW:")
        print(f"   Total low quality jobs: {preview['total_low_quality']:,}")
        print(f"   Currently jd_extraction=True: {preview['currently_jd_extraction_true']:,}")
        print(f"   Currently jd_extraction=False: {preview['currently_jd_extraction_false']:,}")
        print(f"   Currently missing jd_extraction: {preview['currently_jd_extraction_missing']:,}")
        print(f"   Would be updated: {preview['would_be_updated']:,}")
        
        # Perform update (dry run by default)
        dry_run = not args.live_update
        results = updater.update_jd_extraction_flags(low_quality_jobs, dry_run=dry_run)
        
        # Print summary
        updater.print_update_summary(results, args.word_threshold, args.char_threshold)
        
        # Save report
        csv_file, json_file = updater.save_update_report(results, args.word_threshold, args.char_threshold)
        
        print(f"\n📄 REPORTS SAVED:")
        print(f"   Detailed report: {csv_file}")
        print(f"   Summary: {json_file}")
        
    except Exception as e:
        logger.error(f"Update operation failed: {e}")
        raise
    
    finally:
        if updater:
            updater.close_connection()

if __name__ == "__main__":
    main()
