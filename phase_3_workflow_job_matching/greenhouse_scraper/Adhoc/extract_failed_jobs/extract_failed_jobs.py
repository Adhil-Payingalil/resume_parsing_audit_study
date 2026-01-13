import re
import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def extract_failed_jobs_from_log(log_file_path, output_csv_path=None):
    """
    Extract failed job IDs and their corresponding URLs from the log file.
    
    Args:
        log_file_path: Path to the log file
        output_csv_path: Path for the output CSV file (optional)
    
    Returns:
        List of dictionaries with job_id, url, error_type, and timestamp
    """
    
    # Patterns to match different types of failures
    patterns = {
        'processing_job': r'Processing job (\w+) \(attempt \d+/\d+\): (https?://[^\s]+)',
        'marked_failed': r'❌ Marked job (\w+) as failed \(Error: ([^)]+)\)',
        'agentql_error': r'AgentQL query failed for job (\w+): \d+ APIKeyError: ([^:]+)',
        'timeout_error': r'Error processing job (\w+): Timeout \d+ms exceeded\.',
        'general_error': r'Error processing job (\w+): ([^.]+)\.'
    }
    
    failed_jobs = {}
    job_urls = {}
    
    print(f"Reading log file: {log_file_path}")
    
    with open(log_file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            # Extract job processing info (job_id and URL)
            match = re.search(patterns['processing_job'], line)
            if match:
                job_id = match.group(1)
                url = match.group(2)
                job_urls[job_id] = url
                continue
            
            # Extract marked as failed jobs
            match = re.search(patterns['marked_failed'], line)
            if match:
                job_id = match.group(1)
                error_msg = match.group(2)
                failed_jobs[job_id] = {
                    'job_id': job_id,
                    'url': job_urls.get(job_id, 'Unknown'),
                    'error_type': 'Marked as Failed',
                    'error_message': error_msg,
                    'timestamp': extract_timestamp(line),
                    'line_number': line_num
                }
                continue
            
            # Extract AgentQL API errors
            match = re.search(patterns['agentql_error'], line)
            if match:
                job_id = match.group(1)
                error_msg = match.group(2)
                if job_id not in failed_jobs:
                    failed_jobs[job_id] = {
                        'job_id': job_id,
                        'url': job_urls.get(job_id, 'Unknown'),
                        'error_type': 'AgentQL API Error',
                        'error_message': error_msg,
                        'timestamp': extract_timestamp(line),
                        'line_number': line_num
                    }
                continue
            
            # Extract timeout errors
            match = re.search(patterns['timeout_error'], line)
            if match:
                job_id = match.group(1)
                if job_id not in failed_jobs:
                    failed_jobs[job_id] = {
                        'job_id': job_id,
                        'url': job_urls.get(job_id, 'Unknown'),
                        'error_type': 'Timeout Error',
                        'error_message': 'Timeout exceeded',
                        'timestamp': extract_timestamp(line),
                        'line_number': line_num
                    }
                continue
            
            # Extract other general errors
            match = re.search(patterns['general_error'], line)
            if match:
                job_id = match.group(1)
                error_msg = match.group(2)
                if job_id not in failed_jobs:
                    failed_jobs[job_id] = {
                        'job_id': job_id,
                        'url': job_urls.get(job_id, 'Unknown'),
                        'error_type': 'General Error',
                        'error_message': error_msg,
                        'timestamp': extract_timestamp(line),
                        'line_number': line_num
                    }
    
    # Convert to list and sort by timestamp
    failed_jobs_list = list(failed_jobs.values())
    failed_jobs_list.sort(key=lambda x: x['timestamp'] if x['timestamp'] else '')
    
    # Generate output filename if not provided
    if output_csv_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_csv_path = f"failed_jobs_{timestamp}.csv"
    
    # Write to CSV
    if failed_jobs_list:
        with open(output_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['job_id', 'url', 'error_type', 'error_message', 'timestamp', 'line_number']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(failed_jobs_list)
        
        print(f"\n✅ Extracted {len(failed_jobs_list)} failed jobs")
        print(f"📁 Saved to: {output_csv_path}")
        
        # Print summary
        error_types = defaultdict(int)
        for job in failed_jobs_list:
            error_types[job['error_type']] += 1
        
        print(f"\n📊 Error Summary:")
        for error_type, count in error_types.items():
            print(f"  - {error_type}: {count} jobs")
        
        # Show first few failed jobs
        print(f"\n🔍 First 5 failed jobs:")
        for i, job in enumerate(failed_jobs_list[:5]):
            print(f"  {i+1}. {job['job_id']} - {job['error_type']}")
            print(f"     URL: {job['url']}")
            print(f"     Error: {job['error_message']}")
            print()
    else:
        print("❌ No failed jobs found in the log file")
    
    return failed_jobs_list

def extract_timestamp(log_line):
    """Extract timestamp from log line"""
    match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})', log_line)
    return match.group(1) if match else None

def main():
    """Main function"""
    log_file = "../../logs/job_description_dynamic_extractor.log"
    
    if not Path(log_file).exists():
        print(f"❌ Log file not found: {log_file}")
        return
    
    print("🔍 Extracting failed jobs from log file...")
    print("=" * 60)
    
    failed_jobs = extract_failed_jobs_from_log(log_file)
    
    if failed_jobs:
        print(f"\n✅ Successfully extracted {len(failed_jobs)} failed jobs")
        print("📁 Check the current folder for the CSV file")
    else:
        print("\n❌ No failed jobs found")

if __name__ == "__main__":
    main()
