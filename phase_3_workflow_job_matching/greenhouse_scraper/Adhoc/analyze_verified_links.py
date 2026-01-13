"""
Analyze and report on job link verification results from MongoDB
"""
import os
from datetime import datetime
from collections import Counter
from pymongo import MongoClient
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "Resume_study")
MONGODB_COLLECTION = "Job_postings_greenhouse"


def connect_to_mongodb():
    """Connect to MongoDB"""
    if not MONGODB_URI:
        raise Exception("MONGODB_URI not found in environment variables")
    
    client = MongoClient(MONGODB_URI)
    client.admin.command('ping')
    db = client[MONGODB_DATABASE]
    collection = db[MONGODB_COLLECTION]
    
    logger.info(f"✅ Connected to MongoDB: {MONGODB_DATABASE}.{MONGODB_COLLECTION}")
    return client, collection


def analyze_verification_results(collection):
    """Analyze and display verification results"""
    
    print("\n" + "=" * 80)
    print("JOB LINK VERIFICATION ANALYSIS")
    print("=" * 80)
    
    # Total jobs
    total_jobs = collection.count_documents({})
    jobs_with_links = collection.count_documents({'job_link': {'$exists': True, '$ne': ''}})
    
    print(f"\n📊 OVERALL STATISTICS:")
    print(f"  • Total jobs in database: {total_jobs}")
    print(f"  • Jobs with links: {jobs_with_links}")
    
    # Verification status
    verified_jobs = collection.count_documents({'link_status': {'$exists': True}})
    unverified_jobs = jobs_with_links - verified_jobs
    
    print(f"\n🔍 VERIFICATION STATUS:")
    print(f"  • Verified jobs: {verified_jobs}")
    print(f"  • Unverified jobs: {unverified_jobs}")
    
    if verified_jobs == 0:
        print("\n⚠️ No jobs have been verified yet. Run verify_job_links.py first.")
        return
    
    # Status breakdown
    active_count = collection.count_documents({'link_status': 'active'})
    inactive_count = collection.count_documents({'link_status': 'inactive'})
    error_count = collection.count_documents({'link_status': 'error'})
    
    print(f"\n✅ LINK STATUS BREAKDOWN:")
    print(f"  • Active: {active_count} ({active_count/verified_jobs*100:.1f}%)")
    print(f"  • Inactive: {inactive_count} ({inactive_count/verified_jobs*100:.1f}%)")
    print(f"  • Errors: {error_count} ({error_count/verified_jobs*100:.1f}%)")
    
    # Inactive reasons
    if inactive_count > 0:
        print(f"\n❌ INACTIVE JOB REASONS:")
        inactive_jobs = collection.find(
            {'link_status': 'inactive'}, 
            {'link_status_reason': 1, 'title': 1, 'company': 1}
        )
        
        reasons = []
        for job in inactive_jobs:
            reason = job.get('link_status_reason', 'Unknown')
            reasons.append(reason)
        
        reason_counts = Counter(reasons)
        for reason, count in reason_counts.most_common():
            print(f"  • {reason}: {count} jobs")
    
    # Error reasons
    if error_count > 0:
        print(f"\n⚠️ ERROR REASONS:")
        error_jobs = collection.find(
            {'link_status': 'error'}, 
            {'link_status_reason': 1, 'title': 1, 'company': 1}
        )
        
        error_reasons = []
        for job in error_jobs:
            reason = job.get('link_status_reason', 'Unknown')
            error_reasons.append(reason)
        
        error_counts = Counter(error_reasons)
        for reason, count in error_counts.most_common():
            print(f"  • {reason}: {count} jobs")
    
    # Recent verifications
    print(f"\n🕒 RECENT VERIFICATIONS:")
    recent_jobs = collection.find(
        {'link_status': {'$exists': True}},
        {'title': 1, 'company': 1, 'link_status': 1, 'link_verified_at': 1}
    ).sort('link_verified_at', -1).limit(10)
    
    for i, job in enumerate(recent_jobs, 1):
        status_icon = "✅" if job.get('link_status') == 'active' else "❌"
        verified_at = job.get('link_verified_at', 'Unknown')
        if isinstance(verified_at, datetime):
            verified_at = verified_at.strftime("%Y-%m-%d %H:%M:%S")
        print(f"  {i}. {status_icon} {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')}")
        print(f"     Verified: {verified_at}")
    
    # Company breakdown
    print(f"\n🏢 TOP COMPANIES (Active vs Inactive):")
    pipeline = [
        {'$match': {'link_status': {'$exists': True}}},
        {'$group': {
            '_id': '$company',
            'total': {'$sum': 1},
            'active': {'$sum': {'$cond': [{'$eq': ['$link_status', 'active']}, 1, 0]}},
            'inactive': {'$sum': {'$cond': [{'$eq': ['$link_status', 'inactive']}, 1, 0]}}
        }},
        {'$sort': {'total': -1}},
        {'$limit': 10}
    ]
    
    company_stats = list(collection.aggregate(pipeline))
    for i, company in enumerate(company_stats, 1):
        company_name = company['_id'] or 'Unknown'
        total = company['total']
        active = company['active']
        inactive = company['inactive']
        active_pct = (active / total * 100) if total > 0 else 0
        print(f"  {i}. {company_name}: {active} active / {inactive} inactive ({active_pct:.1f}% active)")
    
    print("\n" + "=" * 80)


def list_inactive_jobs(collection, limit=20):
    """List inactive jobs with details"""
    print("\n" + "=" * 80)
    print(f"INACTIVE JOBS (showing first {limit})")
    print("=" * 80)
    
    inactive_jobs = collection.find(
        {'link_status': 'inactive'},
        {'_id': 1, 'title': 1, 'company': 1, 'job_link': 1, 'link_status_reason': 1, 'link_verified_at': 1}
    ).sort('link_verified_at', -1).limit(limit)
    
    for i, job in enumerate(inactive_jobs, 1):
        print(f"\n{i}. {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')}")
        print(f"   ID: {job['_id']}")
        print(f"   URL: {job.get('job_link', 'N/A')}")
        print(f"   Reason: {job.get('link_status_reason', 'Unknown')}")
        verified_at = job.get('link_verified_at', 'Unknown')
        if isinstance(verified_at, datetime):
            verified_at = verified_at.strftime("%Y-%m-%d %H:%M:%S")
        print(f"   Verified: {verified_at}")


def export_by_status(collection, status='inactive'):
    """Export jobs by status to show which ones to potentially remove"""
    import csv
    from pathlib import Path
    
    jobs = list(collection.find(
        {'link_status': status},
        {'_id': 1, 'title': 1, 'company': 1, 'job_link': 1, 'link_status_reason': 1, 'link_verified_at': 1, 'created_at': 1}
    ).sort('link_verified_at', -1))
    
    if not jobs:
        print(f"\n⚠️ No jobs found with status: {status}")
        return
    
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = data_dir / f"jobs_{status}_{timestamp}.csv"
    
    headers = ['job_id', 'title', 'company', 'job_link', 'reason', 'verified_at', 'created_at']
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        
        for job in jobs:
            writer.writerow({
                'job_id': str(job['_id']),
                'title': job.get('title', 'Unknown'),
                'company': job.get('company', 'Unknown'),
                'job_link': job.get('job_link', ''),
                'reason': job.get('link_status_reason', ''),
                'verified_at': job.get('link_verified_at', ''),
                'created_at': job.get('created_at', '')
            })
    
    print(f"\n✅ Exported {len(jobs)} {status} jobs to: {filename}")


def main():
    """Main function"""
    try:
        client, collection = connect_to_mongodb()
        
        # Main analysis
        analyze_verification_results(collection)
        
        # Ask if user wants to see more details
        print("\n" + "=" * 80)
        print("ADDITIONAL OPTIONS")
        print("=" * 80)
        print("1. View detailed list of inactive jobs")
        print("2. Export inactive jobs to CSV")
        print("3. Export active jobs to CSV")
        print("4. Exit")
        
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == '1':
            limit = input("How many to show? (default 20): ").strip()
            limit = int(limit) if limit else 20
            list_inactive_jobs(collection, limit)
        elif choice == '2':
            export_by_status(collection, 'inactive')
        elif choice == '3':
            export_by_status(collection, 'active')
        
        client.close()
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise


if __name__ == "__main__":
    main()


