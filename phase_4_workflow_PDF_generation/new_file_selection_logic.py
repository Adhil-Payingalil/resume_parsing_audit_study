# Updated File Selection Logic using MongoDB
# ==========================================

from pymongo import MongoClient

print(f"🔌 Connecting to MongoDB...")

# Load existing results from MongoDB
processed_combinations = set()  # Store (job_id, treatment_type) strings or tuples

try:
    if not MONGODB_URI:
        raise ValueError("MONGODB_URI not set in configuration")
        
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    
    # Query for successful renders
    # Filter for render_status='successful' and ensure required fields exist
    query = {
        "render_status": "successful",
        "job_posting_id": {"$exists": True},
        "treatment_type": {"$exists": True}
    }
    
    print(f"🔍 Querying {COLLECTION_NAME} for successful renders...")
    # Fetch job_posting_id and treatment_type directly
    cursor = collection.find(query, {"job_posting_id": 1, "treatment_type": 1})
    
    successful_renders = list(cursor)
    print(f"✅ Found {len(successful_renders)} successful renders in MongoDB")
    
    if not REPROCESS_ALREADY_PROCESSED:
        for doc in successful_renders:
            job_id = doc.get('job_posting_id')
            treatment = doc.get('treatment_type')
            
            if job_id and treatment:
                processed_combinations.add((str(job_id), str(treatment)))
        
        print(f"🔍 Found {len(processed_combinations)} valid job-treatment combinations")

    client.close()

except Exception as e:
    print(f"❌ Error connecting to or reading from MongoDB: {str(e)}")
    print("   ⚠️  Will process all files as if none have been processed (unless this creates duplicates)")


# Filter job matches based on processing status
if not REPROCESS_ALREADY_PROCESSED and processed_combinations:
    print(f"\n🔍 Filtering job matches based on processing status...")
    
    # Create a list to store job matches that need processing
    jobs_to_process = []
    
    for _, job_row in job_matches_df.iterrows():
        # Match using job_posting_id or _id depending on what was used to construct u_id.
        job_id = str(job_row['job_posting_id']) # Changed from _id to job_posting_id based on user description
        
        processed_treatments = [t for j, t in processed_combinations if j == job_id]
        missing_treatments = [t for t in TREATMENT_TYPES if t not in processed_treatments]
        
        if missing_treatments:
            # This job needs processing for missing treatments
            jobs_to_process.append({
                'job_row': job_row,
                'missing_treatments': missing_treatments,
                'processed_treatments': processed_treatments
            })
    
    print(f"📊 Jobs needing processing: {len(jobs_to_process)}")
    
    # Create filtered dataframe
    ids_to_process = [job['job_row']['_id'] for job in jobs_to_process]
    all_files_df = job_matches_df[job_matches_df['_id'].isin(ids_to_process)]
    
    print(f"📊 Job matches to process: {len(all_files_df)}")
    
    total_missing_treatments = sum(len(job['missing_treatments']) for job in jobs_to_process)
    print(f"🔄 Total missing treatments to process: {total_missing_treatments}")
    
else:
    all_files_df = job_matches_df.copy()
    print(f"📊 Processing all {len(all_files_df)} job matches")

# Display first 10 files with their details
print(f"\n📋 Sample files to process (first 10):")
print("-" * 60)
for idx, row in all_files_df.head(10).iterrows():
    print(f"{idx+1:2d}. {row['file_id']}")
    print(f"    Job ID: {row.get('job_posting_id', 'N/A')}")
    if 'key_metrics.basics.likely_home_country' in row and pd.notna(row['key_metrics.basics.likely_home_country']):
        print(f"    Country: {row['key_metrics.basics.likely_home_country']}")
    print(f"    Job Title: {row.get('job_title', 'N/A')}")
    
    # Show treatment status
    if not REPROCESS_ALREADY_PROCESSED and processed_combinations:
        job_id = str(row['job_posting_id'])
        processed_treatments = [t for j, t in processed_combinations if j == job_id]
        missing_treatments = [t for t in TREATMENT_TYPES if t not in processed_treatments]
        print(f"    Processed: {processed_treatments}")
        print(f"    Missing: {missing_treatments}")
    print()

if len(all_files_df) > 10:
    print(f"... and {len(all_files_df) - 10} more files")

# Final Selection (Always All Files now)
files_to_process = all_files_df
print(f"\n✅ Processing ALL {len(files_to_process)} job matches (filtered)")

print(f"\n🎯 Final selection: {len(files_to_process)} job matches to process")

# Calculate total operations
if not REPROCESS_ALREADY_PROCESSED and processed_combinations:
    total_operations = 0
    for _, job_row in files_to_process.iterrows():
        job_id = str(job_row['job_posting_id'])
        processed_treatments = [t for j, t in processed_combinations if j == job_id]
        missing_treatments = [t for t in TREATMENT_TYPES if t not in processed_treatments]
        total_operations += len(missing_treatments)
    print(f"🔄 Total operations to process (missing treatments only): {total_operations}")
else:
    total_operations = len(files_to_process) * len(TREATMENT_TYPES)
    print(f"🔄 Total operations to process: {total_operations}")
