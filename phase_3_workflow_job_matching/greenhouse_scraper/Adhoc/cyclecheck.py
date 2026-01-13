from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

client = MongoClient(os.getenv("MONGODB_URI"))
db = client[os.getenv("MONGODB_DATABASE", "Resume_study")]

# Collections
job_postings_collection = db["Job_postings_greenhouse"]
matches_collection = db["greenhouse_resume_job_matches"]
unmatched_collection = db["greenhouse_unmatched_job_postings"]

print("=" * 80)
print("CLEANING CYCLE 8: KEEPING ONLY OVERWRITTEN DOCUMENTS")
print("=" * 80)

# Get all cycle 8 job_links
print("\n1. Getting all cycle 8 job_links...")
cycle_8_docs = list(job_postings_collection.find({"cycle": 8}, {"job_link": 1, "title": 1, "company": 1, "_id": 1}))
cycle_8_links = {doc.get('job_link') for doc in cycle_8_docs if doc.get('job_link')}

print(f"   Found {len(cycle_8_docs)} cycle 8 documents")
print(f"   Found {len(cycle_8_links)} unique job_links in cycle 8")

# Check matches collection
print("\n2. Checking greenhouse_resume_job_matches collection...")
matches_docs = list(matches_collection.find(
    {"job_link": {"$in": list(cycle_8_links)}},
    {"job_link": 1}
))

matched_links = {doc.get('job_link') for doc in matches_docs if doc.get('job_link')}
print(f"   Found {len(matched_links)} cycle 8 job_links in matches collection")

# Check unmatched collection
print("\n3. Checking greenhouse_unmatched_job_postings collection...")
unmatched_docs = list(unmatched_collection.find(
    {"job_link": {"$in": list(cycle_8_links)}},
    {"job_link": 1}
))

unmatched_links = {doc.get('job_link') for doc in unmatched_docs if doc.get('job_link')}
print(f"   Found {len(unmatched_links)} cycle 8 job_links in unmatched collection")

# Get unique set of all overwritten links (these we want to KEEP)
all_overwritten_links = matched_links | unmatched_links

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Total cycle 8 documents: {len(cycle_8_docs)}")
print(f"Total cycle 8 unique job_links: {len(cycle_8_links)}")
print(f"\nDocuments to KEEP (overwritten from previous cycles): {len(all_overwritten_links)}")
print(f"Documents to DELETE (new cycle 8 documents): {len(cycle_8_links) - len(all_overwritten_links)}")

# Identify documents to delete (cycle 8 documents NOT in matches/unmatched)
if all_overwritten_links:
    # Get cycle 8 documents that should be KEPT (have matches in other collections)
    docs_to_keep = [doc for doc in cycle_8_docs if doc.get('job_link') in all_overwritten_links]
    
    # Get cycle 8 documents that should be DELETED (no matches in other collections)
    docs_to_delete = [doc for doc in cycle_8_docs if doc.get('job_link') not in all_overwritten_links]
    
    print(f"\n{'=' * 80}")
    print("DOCUMENTS TO DELETE (new cycle 8, not overwritten):")
    print("=" * 80)
    print(f"Total: {len(docs_to_delete)} documents")
    
    if docs_to_delete:
        print("\nSample of documents to be deleted:")
        for doc in docs_to_delete[:20]:
            print(f"   - {doc.get('title', 'Unknown')} at {doc.get('company', 'Unknown')}")
        if len(docs_to_delete) > 20:
            print(f"   ... and {len(docs_to_delete) - 20} more")
        
        print(f"\n{'=' * 80}")
        print("DOCUMENTS TO KEEP (overwritten from previous cycles):")
        print("=" * 80)
        print(f"Total: {len(docs_to_keep)} documents")
        
        if docs_to_keep:
            print("\nSample of documents to be kept:")
            for doc in docs_to_keep[:20]:
                print(f"   - {doc.get('title', 'Unknown')} at {doc.get('company', 'Unknown')}")
            if len(docs_to_keep) > 20:
                print(f"   ... and {len(docs_to_keep) - 20} more")
        
        # Confirmation prompt
        print("\n" + "=" * 80)
        print("CONFIRMATION REQUIRED")
        print("=" * 80)
        print(f"This will DELETE {len(docs_to_delete)} cycle 8 documents")
        print(f"And KEEP {len(docs_to_keep)} cycle 8 documents (overwritten ones)")
        
        confirm = input("\nType 'DELETE' to confirm deletion: ").strip()
        
        if confirm == "DELETE":
            # Delete documents
            job_links_to_delete = {doc.get('job_link') for doc in docs_to_delete if doc.get('job_link')}
            
            result = job_postings_collection.delete_many({
                "cycle": 8,
                "job_link": {"$in": list(job_links_to_delete)}
            })
            
            print(f"\n✅ Successfully deleted {result.deleted_count} cycle 8 documents")
            print(f"✅ Kept {len(docs_to_keep)} cycle 8 documents (overwritten from previous cycles)")
            
            # Verify
            remaining_cycle8 = job_postings_collection.count_documents({"cycle": 8})
            print(f"\nRemaining cycle 8 documents: {remaining_cycle8}")
            print(f"Expected: {len(docs_to_keep)}")
            
            if remaining_cycle8 == len(docs_to_keep):
                print("✅ Verification passed! All new cycle 8 documents deleted.")
            else:
                print(f"⚠️  Warning: Expected {len(docs_to_keep)} but found {remaining_cycle8}")
        else:
            print("\n❌ Deletion cancelled. No documents were deleted.")
    else:
        print("\n✅ No documents to delete. All cycle 8 documents are overwritten from previous cycles.")
else:
    print("\n⚠️  No overwritten documents found.")
    print("   All cycle 8 documents appear to be new.")
    print("   Do you want to delete ALL cycle 8 documents?")
    
    confirm = input("Type 'DELETE ALL' to delete all cycle 8 documents: ").strip()
    
    if confirm == "DELETE ALL":
        result = job_postings_collection.delete_many({"cycle": 8})
        print(f"\n✅ Successfully deleted {result.deleted_count} cycle 8 documents")
    else:
        print("\n❌ Deletion cancelled. No documents were deleted.")D