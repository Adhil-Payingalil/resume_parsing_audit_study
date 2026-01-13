#!/usr/bin/env python3
"""
Test script to verify MongoDB connection and show basic collection stats.
Run this before running the main analysis to ensure everything is set up correctly.
"""

import os
from pathlib import Path
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "Resume_study")
MONGODB_COLLECTION = "Job_postings_greenhouse"

def test_mongodb_connection():
    """Test MongoDB connection and show basic statistics"""
    
    print("🔍 Testing MongoDB Connection...")
    print("="*50)
    
    # Check environment variables
    if not MONGODB_URI:
        print("❌ MONGODB_URI not found in environment variables")
        print("   Please check your .env file")
        return False
    
    print(f"📍 MongoDB URI: {MONGODB_URI[:20]}..." if len(MONGODB_URI) > 20 else MONGODB_URI)
    print(f"🗄️  Database: {MONGODB_DATABASE}")
    print(f"📋 Collection: {MONGODB_COLLECTION}")
    
    try:
        # Connect to MongoDB
        print("\n🔗 Connecting to MongoDB...")
        client = MongoClient(MONGODB_URI)
        
        # Test the connection
        client.admin.command('ping')
        print("✅ Connection successful!")
        
        # Get database and collection
        db = client[MONGODB_DATABASE]
        collection = db[MONGODB_COLLECTION]
        
        # Get basic statistics
        print("\n📊 Collection Statistics:")
        print("-" * 30)
        
        total_jobs = collection.count_documents({})
        print(f"Total jobs: {total_jobs:,}")
        
        jobs_with_descriptions = collection.count_documents({
            "job_description": {"$exists": True, "$ne": None, "$ne": ""}
        })
        print(f"Jobs with descriptions: {jobs_with_descriptions:,}")
        
        jobs_without_descriptions = total_jobs - jobs_with_descriptions
        print(f"Jobs without descriptions: {jobs_without_descriptions:,}")
        
        if total_jobs > 0:
            coverage = (jobs_with_descriptions / total_jobs) * 100
            print(f"Description coverage: {coverage:.1f}%")
        
        # Check for existing length fields
        jobs_with_length_data = collection.count_documents({
            "jd_word_count": {"$exists": True}
        })
        print(f"Jobs with length analysis: {jobs_with_length_data:,}")
        
        # Check jd_extraction status
        jd_extraction_true = collection.count_documents({"jd_extraction": True})
        jd_extraction_false = collection.count_documents({"jd_extraction": False})
        jd_extraction_missing = collection.count_documents({
            "jd_extraction": {"$exists": False}
        })
        
        print(f"\n🏷️  JD Extraction Status:")
        print(f"   jd_extraction = True: {jd_extraction_true:,}")
        print(f"   jd_extraction = False: {jd_extraction_false:,}")
        print(f"   jd_extraction missing: {jd_extraction_missing:,}")
        
        # Sample a few jobs to show structure
        print(f"\n📄 Sample Job Structure:")
        print("-" * 30)
        sample_job = collection.find_one({}, {"_id": 1, "title": 1, "company": 1, 
                                             "job_description": 1, "jd_extraction": 1,
                                             "jd_word_count": 1, "jd_char_count": 1})
        if sample_job:
            print(f"Sample job ID: {sample_job.get('_id')}")
            print(f"Title: {sample_job.get('title', 'N/A')}")
            print(f"Company: {sample_job.get('company', 'N/A')}")
            print(f"Has description: {'Yes' if sample_job.get('job_description') else 'No'}")
            print(f"JD extraction: {sample_job.get('jd_extraction', 'Not set')}")
            print(f"Word count: {sample_job.get('jd_word_count', 'Not analyzed')}")
            print(f"Char count: {sample_job.get('jd_char_count', 'Not analyzed')}")
        
        # Close connection
        client.close()
        
        print(f"\n✅ All tests passed!")
        print(f"🚀 Ready to run: python analyze_jd_lengths.py")
        
        return True
        
    except ConnectionFailure as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Main function"""
    print("🧪 MongoDB Connection Test")
    print("="*50)
    
    success = test_mongodb_connection()
    
    if success:
        print(f"\n💡 Next Steps:")
        print(f"   1. Run: python Adhoc/analyze_jd_lengths/analyze_jd_lengths.py")
        print(f"   2. Review the generated reports in Adhoc/analyze_jd_lengths/data/")
        print(f"   3. Run: python Adhoc/analyze_jd_lengths/update_jd_extraction_flags.py (dry run)")
        print(f"   4. Run: python Adhoc/analyze_jd_lengths/update_jd_extraction_flags.py --live-update")
    else:
        print(f"\n🔧 Troubleshooting:")
        print(f"   1. Check your .env file has MONGODB_URI set")
        print(f"   2. Verify MongoDB server is running")
        print(f"   3. Check network connectivity to MongoDB")
    
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
