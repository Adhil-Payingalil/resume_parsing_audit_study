import os
import time
import json
import csv
from pathlib import Path
from datetime import datetime

# Import Configuration FIRST (Sets up Env Vars and API Keys)
try:
    from config import (
        GREENHOUSE_URL, JOBS_URL, CONTEXT_DIR, CONTEXT_FILE,
        MAX_SEE_MORE_CLICKS, MONGODB_URI, MONGODB_DATABASE,
        MONGODB_COLLECTION, SCRAPED_DATA_DIR, DATA_DIR,
        DEFAULT_JOB_FILTER
    )
except ImportError:
    # Handle direct execution
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from config import (
        GREENHOUSE_URL, JOBS_URL, CONTEXT_DIR, CONTEXT_FILE,
        MAX_SEE_MORE_CLICKS, MONGODB_URI, MONGODB_DATABASE,
        MONGODB_COLLECTION, SCRAPED_DATA_DIR, DATA_DIR,
        DEFAULT_JOB_FILTER
    )

import agentql
from playwright.sync_api import sync_playwright
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, DuplicateKeyError

def setup_mongodb_connection():
    """Set up MongoDB connection"""
    if not MONGODB_URI:
        raise Exception("MONGODB_URI not found in environment variables")
    
    try:
        client = MongoClient(MONGODB_URI)
        # Test the connection
        client.admin.command('ping')
        db = client[MONGODB_DATABASE]
        collection = db[MONGODB_COLLECTION]
        
        # Create unique index on job_link to prevent duplicates
        collection.create_index("job_link", unique=True, sparse=True)
        
        print(f"✅ Connected to MongoDB: {MONGODB_DATABASE}.{MONGODB_COLLECTION}")
        return client, collection
    except ConnectionFailure as e:
        raise Exception(f"Failed to connect to MongoDB: {e}")
    except Exception as e:
        raise Exception(f"MongoDB setup error: {e}")

def setup_browser_context(playwright, persistent=True):
    """Set up browser with persistent context for login state"""
    if persistent and os.path.exists(CONTEXT_FILE):
        print("Loading existing browser context...")
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=CONTEXT_DIR,
            channel="chrome",  # Use localized Chrome
            headless=False,
            args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
        )
        return context, True  # Return context and is_persistent flag
    else:
        print("Creating new browser context...")
        browser = playwright.chromium.launch(
            channel="chrome",  # Use localized Chrome
            headless=False,
            args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        return context, False  # Return context and is_persistent flag

def manual_login_flow(page):
    """Handle manual login process"""
    print("log in manually in the browser window...")
    input("Press Enter after you've completed the login...")
    
    # Verify we're logged in
    try:
        page.wait_for_selector("text=Jobs", timeout=10000)
        print("Login successful!")
        return True
    except Exception as e:
        print(f"Login verification failed: {e}")
        return False

def save_context_info(context):
    """Save context information for future use"""
    os.makedirs(CONTEXT_DIR, exist_ok=True)
    context_info = {
        "timestamp": time.time(),
        "user_data_dir": CONTEXT_DIR
    }
    with open(CONTEXT_FILE, 'w') as f:
        json.dump(context_info, f)
    print(f"Context saved to {CONTEXT_FILE}")

def set_date_posted_filter(page, days=30):
    """Set the Date posted filter to Within 30 days using multiple approaches"""
    print(f"Setting 'Date posted' filter to 'Within {days} days'...")
    
    try:
        # First try using direct Playwright selectors as fallback
        date_posted_selectors = [
            "text=Date posted",
            "button:has-text('Date posted')",
            "[class*='date-posted']",
            "[data-testid*='date-posted']"
        ]
        
        dropdown_clicked = False
        for selector in date_posted_selectors:
            try:
                print(f"Trying to click 'Date posted' with selector: {selector}")
                page.click(selector)
                time.sleep(1)  # Wait for dropdown to open
                dropdown_clicked = True
                print("✅ Successfully clicked 'Date posted' dropdown")
                break
            except Exception as e:
                print(f"Failed with selector '{selector}': {e}")
                continue
        
        if not dropdown_clicked:
            print("❌ Could not click 'Date posted' dropdown with any selector")
            return False
        
        # Now try to select "Within 30 days" option
        within_30_days_selectors = [
            "text=Within 30 days",
            "label:has-text('Within 30 days')",
            "[value*='30']",
            "input[type='radio']:near(text=Within 30 days)"
        ]
        
        option_selected = False
        for selector in within_30_days_selectors:
            try:
                print(f"Trying to select 'Within 30 days' with selector: {selector}")
                page.click(selector)
                time.sleep(1)  # Wait for selection to apply
                option_selected = True
                print("✅ Successfully selected 'Within 30 days'")
                break
            except Exception as e:
                print(f"Failed with selector '{selector}': {e}")
                continue
        
        if option_selected:
            print("✅ Successfully set 'Date posted' filter to 'Within 30 days'")
            return True
        else:
            print("❌ Could not select 'Within 30 days' option")
            return False
            
    except Exception as e:
        print(f"Error setting date posted filter: {e}")
        return False

def search_jobs_by_location(page, location="toronto"):
    """Search for jobs in a specific location using AgentQL with fallback"""
    print(f"Searching for jobs in {location}...")
    
    try:
        # First try AgentQL approach (which was working before)
        if hasattr(page, 'query_elements'):
            try:
                # Query to find location search elements
                search_query = """
                {
                    Input {
                        location_input (text=location)
                        location_dropdown (select__indicators overwritable)
                        search_btn
                    }
                }
                """
                
                # Use query_elements for form interaction
                response = page.query_elements(search_query)
                
                if response and hasattr(response, 'Input'):
                    input_form = response.Input
                    
                    # Fill in the location input
                    if hasattr(input_form, 'location_input'):
                        print(f"Typing '{location}' in location input...")
                        
                        # Clear field and type slowly to trigger dropdown
                        input_form.location_input.clear()
                        time.sleep(0.5)
                        
                        # Type character by character to simulate human typing
                        for char in location:
                            input_form.location_input.type(char)
                            time.sleep(0.1)
                        
                        # Trigger input events to ensure dropdown appears
                        input_form.location_input.evaluate("element => element.dispatchEvent(new Event('input', { bubbles: true }))")
                        input_form.location_input.evaluate("element => element.dispatchEvent(new Event('keyup', { bubbles: true }))")
                        time.sleep(2)
                        
                        # Wait for dropdown and click first option
                        print("Looking for dropdown options...")
                        dropdown_selectors = [
                            "[class*='option']",
                            "[class*='dropdown']",
                            "[class*='suggestion']",
                            "[class*='autocomplete']",
                            "[role='option']"
                        ]
                        
                        dropdown_found = False
                        for selector in dropdown_selectors:
                            try:
                                page.wait_for_selector(selector, timeout=3000)
                                print(f"Found dropdown with selector: {selector}")
                                dropdown_found = True
                                break
                            except:
                                continue
                        
                        # Click first dropdown option if found
                        if dropdown_found:
                            first_option_selectors = [
                                "[class*='option']:first-child",
                                "[class*='dropdown'] li:first-child",
                                "[role='option']:first-child"
                            ]
                            
                            for option_selector in first_option_selectors:
                                try:
                                    first_option = page.query_selector(option_selector)
                                    if first_option and first_option.is_visible():
                                        first_option.click()
                                        print("✅ Selected first dropdown option")
                                        time.sleep(1)
                                        break
                                except:
                                    continue
                        else:
                            print("⚠️ No dropdown found, continuing...")
                        
                        # Click search button
                        if hasattr(input_form, 'search_btn'):
                            print("Clicking search button...")
                            input_form.search_btn.click()
                            page.wait_for_load_state('networkidle')
                            print(f"✅ Successfully searched for jobs in {location}")
                            return True
                        else:
                            print("❌ Search button not found")
                            return False
                    else:
                        print("❌ Location input not found with AgentQL")
            except Exception as e:
                print(f"AgentQL approach failed: {e}")
        
        # Fallback to direct Playwright selectors
        print("Trying fallback approach with direct selectors...")
        
        # Try to find location input using multiple selectors
        location_input_selectors = [
            "input[placeholder*='location' i]",
            "input[placeholder*='city' i]", 
            "input[placeholder*='where' i]",
            "input[placeholder*='Location']",
            "[class*='location'] input",
            "[data-testid*='location'] input",
            "input[type='text']:near(text=Location)",
            "input[type='search']"
        ]
        
        location_input = None
        for selector in location_input_selectors:
            try:
                location_input = page.query_selector(selector)
                if location_input and location_input.is_visible():
                    print(f"Found location input with selector: {selector}")
                    break
            except:
                continue
        
        if not location_input:
            print("❌ Location input not found with any selector")
            return False
        
        # Fill in the location
        print(f"Typing '{location}' in location input...")
        location_input.clear()
        time.sleep(0.5)
        
        # Type character by character to simulate human typing
        for char in location:
            location_input.type(char)
            time.sleep(0.1)
        
        # Trigger input events to ensure dropdown appears
        location_input.evaluate("element => element.dispatchEvent(new Event('input', { bubbles: true }))")
        location_input.evaluate("element => element.dispatchEvent(new Event('keyup', { bubbles: true }))")
        time.sleep(2)
        
        # Wait for dropdown and click first option
        print("Looking for dropdown options...")
        dropdown_selectors = [
            "[class*='option']",
            "[class*='dropdown']",
            "[class*='suggestion']",
            "[class*='autocomplete']",
            "[role='option']"
        ]
        
        dropdown_found = False
        for selector in dropdown_selectors:
            try:
                page.wait_for_selector(selector, timeout=3000)
                print(f"Found dropdown with selector: {selector}")
                dropdown_found = True
                break
            except:
                continue
        
        # Click first dropdown option if found
        if dropdown_found:
            first_option_selectors = [
                "[class*='option']:first-child",
                "[class*='dropdown'] li:first-child",
                "[role='option']:first-child"
            ]
            
            for option_selector in first_option_selectors:
                try:
                    first_option = page.query_selector(option_selector)
                    if first_option and first_option.is_visible():
                        first_option.click()
                        print("✅ Selected first dropdown option")
                        time.sleep(1)
                        break
                except:
                    continue
        else:
            print("⚠️ No dropdown found, continuing...")
        
        # Find and click search button
        search_button_selectors = [
            "button:has-text('Search')",
            "input[type='submit']",
            "[class*='search'] button",
            "[data-testid*='search'] button"
        ]
        
        search_clicked = False
        for selector in search_button_selectors:
            try:
                print(f"Trying to click search button with selector: {selector}")
                page.click(selector)
                page.wait_for_load_state('networkidle')
                print(f"✅ Successfully searched for jobs in {location}")
                search_clicked = True
                break
            except Exception as e:
                print(f"Failed with selector '{selector}': {e}")
                continue
        
        if search_clicked:
            return True
        else:
            print("❌ Search button not found")
            return False
            
    except Exception as e:
        print(f"Error searching for location: {e}")
        return False


def extract_job_data(page):
    """Extract job posting data from the current page using AgentQL"""
    print("Extracting job data...")
    
    # Verify AgentQL is working
    if not hasattr(page, 'query_data'):
        raise Exception("AgentQL not properly initialized - page object missing 'query_data' method")
    
    try:
        # Wait for job listings to load
        try:
            page.wait_for_selector(".job-card, .job-listing, [class*='job']", timeout=10000)
        except:
            # Fallback to text selector
            page.wait_for_selector("text=View job", timeout=10000)
    
        # Query to get all job listings
        job_query = """
        {
            jobs[] {
                title
                company
                location
                posted_date
                job_link
            }
        }
        """
        
        # Execute the query
        result = page.query_data(job_query)
        
        if result and 'jobs' in result:
            jobs = result['jobs']
            print(f"Found {len(jobs)} job listings")
            return jobs
        else:
            print("No job data found")
            return []
            
    except Exception as e:
        print(f"Job extraction failed: {e}")
        raise Exception(f"Job data extraction failed: {e}")

def clean_job_title(title):
    """Clean job title to remove duplicates"""
    if not title:
        return title
    
    # Check if the entire title is duplicated (e.g., "Product DesignerProduct Designer")
    title_length = len(title)
    if title_length % 2 == 0:  # Even length
        mid_point = title_length // 2
        first_half = title[:mid_point]
        second_half = title[mid_point:]
        
        if first_half == second_half:
            # Title is duplicated, return only the first half
            return first_half
    
    # Also check for word-level duplication
    words = title.split()
    if len(words) >= 2:
        mid_point = len(words) // 2
        first_half = words[:mid_point]
        second_half = words[mid_point:mid_point + len(first_half)]
        
        if first_half == second_half:
            # Title is duplicated at word level, return only the first half
            cleaned_title = ' '.join(first_half)
            return cleaned_title
    
    return title

def remove_duplicate_jobs(jobs):
    """Remove duplicate job postings based on job_link"""
    if not jobs:
        return jobs
    
    seen_links = set()
    unique_jobs = []
    
    for job in jobs:
        # Clean the title to remove duplicates
        original_title = job.get('title', '')
        cleaned_title = clean_job_title(original_title)
        if cleaned_title != original_title:
            job['title'] = cleaned_title
        
        job_link = job.get('job_link', '')
        if job_link and job_link not in seen_links:
            seen_links.add(job_link)
            unique_jobs.append(job)
        elif not job_link:
            # If no job_link, use title + company as unique identifier
            identifier = f"{job.get('title', '')}_{job.get('company', '')}"
            if identifier not in seen_links:
                seen_links.add(identifier)
                unique_jobs.append(job)
    
    removed_count = len(jobs) - len(unique_jobs)
    if removed_count > 0:
        print(f"✅ Removed {removed_count} duplicate job postings")
    
    return unique_jobs

def save_jobs_to_mongodb(jobs, collection, location=None, cycle=0):
    """Save job data to MongoDB collection"""
    if not jobs:
        print("No job data to save")
        return 0
    
    if collection is None:
        raise Exception("MongoDB collection not provided")
    
    # Prepare jobs for MongoDB insertion
    jobs_to_insert = []
    current_time = datetime.now()
    today_date = current_time.date()
    
    for job in jobs:
        # Clean and format the data
        job_link = str(job.get('job_link', '')).strip()
        
        # Determine link_type based on job_link URL
        if job_link.startswith('https://job-boards.greenhouse.io') or job_link.startswith('https://boards.greenhouse.io'):
            link_type = 'greenhouse'
        else:
            link_type = 'dynamic'
        
        clean_job = {
            'title': str(job.get('title', '')).strip(),
            'company': str(job.get('company', '')).strip(),
            'location': str(job.get('location', '')).strip(),
            'posted_date': str(job.get('posted_date', '')).strip(),
            'job_link': job_link,
            'link_type': link_type,
            'scraped_at': current_time,
            'scrapped_on': today_date.isoformat(),
            'search_location': location,
            'source': 'greenhouse',
            'cycle': cycle
        }
        
        # Remove empty values
        clean_job = {k: v for k, v in clean_job.items() if v}
        jobs_to_insert.append(clean_job)
    
    # Insert jobs into MongoDB
    inserted_count = 0
    duplicate_count = 0
    
    for job in jobs_to_insert:
        try:
            # Check if job_link already exists in MongoDB
            existing_job = collection.find_one({'job_link': job.get('job_link')})
            
            if existing_job:
                # Document already exists - skip it (don't overwrite)
                duplicate_count += 1
            else:
                # Document doesn't exist - insert it
                result = collection.insert_one(job)
                if result.inserted_id:
                    inserted_count += 1
                
        except DuplicateKeyError:
            duplicate_count += 1
        except Exception as e:
            print(f"Error inserting job {job.get('title', 'Unknown')}: {e}")
            continue
    
    print(f"✅ MongoDB: {inserted_count} jobs inserted, {duplicate_count} duplicates skipped")
    return inserted_count

def save_jobs_to_csv(jobs, filename=None, page_number=None, location=None):
    """Save job data to CSV file in data folder (kept for backup purposes)"""
    if not jobs:
        print("No job data to save")
        return
    
    # Create data directory if it doesn't exist
    # Create base data directory for scraped jobs
    os.makedirs(SCRAPED_DATA_DIR, exist_ok=True)
    
    # Generate filename if not provided
    if not filename:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        if location:
            # Clean location string for filename
            clean_loc = "".join(c for c in location if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')
            filename = SCRAPED_DATA_DIR / f"greenhouse_jobs_{clean_loc}_{timestamp}.csv"
        elif page_number:
            filename = SCRAPED_DATA_DIR / f"greenhouse_jobs_page_{page_number}_{timestamp}.csv"
        else:
            filename = SCRAPED_DATA_DIR / f"greenhouse_jobs_{timestamp}.csv"
    else:
        # If filename provided, ensure it's in the data directory
        filename = SCRAPED_DATA_DIR / Path(filename).name
    
    # Define CSV headers - updated to match your query fields
    headers = ['title', 'company', 'location', 'posted_date', 'job_link']
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        
        for job in jobs:
            # Clean and format the data
            clean_job = {}
            for header in headers:
                value = job.get(header, '')
                if isinstance(value, list):
                    value = ', '.join(value) if value else ''
                clean_job[header] = str(value).strip()
            
            writer.writerow(clean_job)
    
    print(f"Job data saved to {filename}")
    return filename

def load_all_jobs_by_clicking_see_more(page, max_clicks=10):
    """Click 'See more jobs' button multiple times to load all available jobs"""
    print(f"Loading all jobs by clicking 'See more jobs' button (max {max_clicks} clicks)...")
    
    try:
        clicks_performed = 0
        
        for click_attempt in range(max_clicks):
            print(f"Click attempt {click_attempt + 1}/{max_clicks}...")
            
            # Try multiple selectors to find "See more jobs" button
            see_more_selectors = [
                "text=See more jobs",
                "button:has-text('See more jobs')",
                "span:has-text('See more jobs')",
                "[class*='see-more']",
                "[class*='load-more']",
                "[data-testid*='see-more']",
                "[data-testid*='load-more']",
                "button:has-text('Load more')",
                "text=Load more",
                "text=Show more",
                "button:has-text('Show more')"
            ]
            
            button_found = False
            for selector in see_more_selectors:
                try:
                    # Check if button exists and is visible
                    button_element = page.query_selector(selector)
                    if button_element and button_element.is_visible():
                        print(f"Found 'See more jobs' button with selector: {selector}")
                        
                        # Try to click the button
                        button_element.click()
                        page.wait_for_load_state('networkidle')
                        print(f"✅ Successfully clicked 'See more jobs' using: {selector}")
                        clicks_performed += 1
                        button_found = True
                        time.sleep(2)  # Wait for new jobs to load
                        break
                except Exception as e:
                    print(f"Failed with selector '{selector}': {e}")
                    continue
            
            if not button_found:
                print("✅ No more 'See more jobs' button found - all jobs loaded!")
                break
        
        print(f"✅ Completed loading all jobs. Total clicks performed: {clicks_performed}")
        return clicks_performed
        
    except Exception as e:
        print(f"Error loading all jobs: {e}")
        raise Exception(f"Failed to load all jobs: {e}")

def navigate_to_next_page(page):
    """Navigate to the next page of job listings using AgentQL"""
    try:
        # Verify AgentQL is working
        if not hasattr(page, 'query_data'):
            raise Exception("AgentQL not properly initialized - page object missing 'query_data' method")
        
        # Look for next page button using AgentQL - using your correct syntax
        next_query = """
        {
            next_button (text=See more jobs)
        }
        """
        
        result = page.query_data(next_query)
        
        if result and 'next_button' in result and result['next_button']:
            print("Found next page button, clicking...")
            # Try different selectors for the next button
            selectors_to_try = [
                "text=See more jobs"
            ]
            
            for selector in selectors_to_try:
                try:
                    page.click(selector)
                    page.wait_for_load_state('networkidle')
                    print(f"Successfully clicked next page using: {selector}")
                    return True
                except:
                    continue
            
            print("Could not click any next page button")
            return False
        else:
            print("No next page button found")
            return False
            
    except Exception as e:
        print(f"Error navigating to next page: {e}")
        raise Exception(f"AgentQL pagination failed: {e}")

def clear_search_filters(page):
    """Clear any existing search filters and results"""
    print("Clearing existing search filters...")
    
    try:
        # Try to find and click clear/reset buttons
        clear_selectors = [
            "text=Clear",
            "button:has-text('Clear')",
            "text=Reset",
            "button:has-text('Reset')",
            "text=Clear all",
            "button:has-text('Clear all')",
            "[class*='clear']",
            "[class*='reset']"
        ]
        
        for selector in clear_selectors:
            try:
                clear_button = page.query_selector(selector)
                if clear_button and clear_button.is_visible():
                    clear_button.click()
                    print(f"✅ Clicked clear button with selector: {selector}")
                    time.sleep(1)
                    break
            except:
                continue
        
        # Also try to clear location input if it exists
        location_input_selectors = [
            "input[placeholder*='location' i]",
            "input[placeholder*='city' i]", 
            "input[placeholder*='where' i]",
            "input[placeholder*='Location']",
            "[class*='location'] input"
        ]
        
        for selector in location_input_selectors:
            try:
                location_input = page.query_selector(selector)
                if location_input and location_input.is_visible():
                    location_input.clear()
                    print(f"✅ Cleared location input with selector: {selector}")
                    break
            except:
                continue
        
        # Wait a moment for any filters to clear
        time.sleep(2)
        
    except Exception as e:
        print(f"Warning: Could not clear filters: {e}")

def set_date_posted_filter(page, days=30):
    """Set the Date Posted filter to 'Within X days'"""
    try:
        # Determine strict text: "day" for 1, "days" for others
        day_text = "day" if days == 1 else "days"
        filter_text = f"Within {days} {day_text}"
        
        print(f"Setting 'Date posted' filter to '{filter_text}'...")
        
        # Click the dropdown first
        print("Trying to click 'Date posted' with selector: text=Date posted")
        page.click("text=Date posted")
        time.sleep(1)
        print("✅ Successfully clicked 'Date posted' dropdown")
        
        # Wait for options and click the specific one
        print(f"Trying to select '{filter_text}' with selector: text={filter_text}")
        page.click(f"text={filter_text}")
        time.sleep(2)
        print(f"✅ Successfully selected '{filter_text}'")
        return True
    
    except Exception as e:
        print(f"❌ Error setting date filter: {e}")
        return False

def scrape_location(page, location, mongo_collection, date_posted_days=30, cycle=0):
    """Scrape jobs for a specific location"""
    print(f"\n{'='*60}")
    print(f"SCRAPING JOBS FOR: {location.upper()}")
    print(f"{'='*60}")
    
    try:
        # Navigate to jobs page with hard refresh to clear previous search
        print(f"Navigating to {JOBS_URL}...")
        page.goto(JOBS_URL, wait_until='networkidle')
        
        # Wait for jobs page to load
        page.wait_for_selector("text=Jobs", timeout=10000)
        print("Successfully reached the jobs page!")
        
        # Clear any existing search filters
        clear_search_filters(page)
        
        # Set date posted filter
        print("\n--- Setting Date Posted Filter ---")
        if not set_date_posted_filter(page, days=date_posted_days):
            print("❌ Failed to set date posted filter, skipping location...")
            return 0, 0
        
        # Search for jobs in specific location - CRITICAL STEP
        print(f"\n--- Searching for jobs in {location} ---")
        if not search_jobs_by_location(page, location):
            print(f"❌ Failed to search for location '{location}', skipping this location...")
            return 0, 0
        
        # Wait for search results to load
        print("Waiting for search results to load...")
        time.sleep(3)
        
        # Load all jobs by clicking "See more jobs" button multiple times
        print("\n--- Loading all available jobs ---")
        clicks_performed = load_all_jobs_by_clicking_see_more(page, max_clicks=MAX_SEE_MORE_CLICKS)
        print(f"✅ Loaded all jobs with {clicks_performed} clicks")
        
        # Extract all job data at once
        print("\n--- Extracting all job data ---")
        all_jobs = extract_job_data(page)
        
        if all_jobs:
            print(f"✅ Successfully extracted {len(all_jobs)} total jobs")
            
            # Remove duplicate jobs and clean titles
            print("\n--- Processing job data ---")
            unique_jobs = remove_duplicate_jobs(all_jobs)
            
            # Save all jobs to CSV
            print("\n--- Saving jobs to CSV ---")
            csv_file = save_jobs_to_csv(unique_jobs, location=location)
            
            # Save all jobs to MongoDB
            print("\n--- Saving jobs to MongoDB ---")
            inserted_count = save_jobs_to_mongodb(unique_jobs, mongo_collection, location, cycle=cycle)
            
            print(f"\n✅ Scraping completed for {location}! Total unique jobs collected: {len(unique_jobs)}")
            print(f"📁 CSV file saved: {csv_file}")
            print(f"📊 MongoDB: {inserted_count} new jobs inserted into {MONGODB_DATABASE}.{MONGODB_COLLECTION} (Cycle {cycle})")
            
            return len(unique_jobs), inserted_count
        else:
            print(f"❌ No job data was collected for {location}")
            return 0, 0
            
    except Exception as e:
        print(f"❌ Error scraping {location}: {e}")
        return 0, 0

def main():
    """Main scraping function"""
    print("Starting Greenhouse job scraper...")
    
    # Define list of locations to scrape
    locations = [
        "toronto",
        "vancouver",
        "edmonton",
        "calgary",
        "ottawa",
        "hamilton",
        "waterloo",
        "quebec",
        "montreal",
        "winnipeg",
        "halifax",
        "st. john's",
        "saskatoon"
    ]
    
    # Option to customize locations
    print(f"\nDefault locations: {', '.join(locations)}")
    custom_locations = input("Enter custom locations (comma-separated) or press Enter to use default: ").strip()
    
    if custom_locations:
        locations = [loc.strip().lower() for loc in custom_locations.split(',') if loc.strip()]
        print(f"Using custom locations: {', '.join(locations)}")
    else:
        print(f"Using default locations: {', '.join(locations)}")

    # Option to customize Date Posted filter
    print("\nSelect Date Posted Filter:")
    print("1. Within 1 day")
    print("2. Within 5 days")
    print("3. Within 10 days")
    print("4. Within 30 days (Default)")
    
    date_choice = input("Enter choice (1-4) or press Enter for default (30 days): ").strip()
    
    date_posted_days = 30
    if date_choice == "1":
        date_posted_days = 1
    elif date_choice == "2":
        date_posted_days = 5
    elif date_choice == "3":
        date_posted_days = 10
    elif date_choice == "4":
        date_posted_days = 30
    
    print(f"Using Date Posted Filter: Within {date_posted_days} {'day' if date_posted_days == 1 else 'days'}")
    
    # Option to customize Cycle Number
    default_cycle = DEFAULT_JOB_FILTER.get('cycle', 9)
    print(f"\nDefault Cycle Number: {default_cycle}")
    cycle_input = input(f"Enter Cycle Number (default {default_cycle}): ").strip()
    
    try:
        if cycle_input:
            cycle = float(cycle_input)
            # If it's effectively an integer (e.g. 8.0), convert to int for display cleanliness
            if cycle.is_integer():
                cycle = int(cycle)
        else:
            cycle = default_cycle
        print(f"Using Cycle Number: {cycle}")
    except ValueError:
        print(f"Invalid input '{cycle_input}'. Using default cycle: {default_cycle}")
        cycle = default_cycle
    
    # Setup MongoDB connection
    try:
        mongo_client, mongo_collection = setup_mongodb_connection()
    except Exception as e:
        print(f"❌ MongoDB setup failed: {e}")
        print("Please check your MONGODB_URI in the .env file")
        return
    
    with sync_playwright() as playwright:
        # Try to use persistent context first
        context, is_persistent = setup_browser_context(playwright, persistent=True)
        
        # Create a new page from the context
        playwright_page = context.new_page()
        
        # Wrap the page with AgentQL
        page = agentql.wrap(playwright_page)
        
        # Verify AgentQL wrapping worked
        if not hasattr(page, 'query_data'):
            raise Exception("AgentQL not properly initialized - page object missing 'query_data' method")
        
        try:
            # Navigate to Greenhouse
            print(f"Navigating to {GREENHOUSE_URL}...")
            page.goto(GREENHOUSE_URL)
            
            # Check if we need to login
            try:
                page.wait_for_selector("text=Sign in", timeout=5000)
                print("Login required...")
                if manual_login_flow(page):
                    print("Login successful!")
                    # Save context for future use
                    if not is_persistent:
                        save_context_info(context)
                        print("Context saved for future use")
                else:
                    print("Login failed, exiting...")
                    return
            except:
                print("Already logged in or login not required")
            
            # Scrape each location
            total_jobs_collected = 0
            total_jobs_inserted = 0
            successful_locations = []
            failed_locations = []
            
            for i, location in enumerate(locations, 1):
                print(f"\n{'='*80}")
                print(f"PROGRESS: {i}/{len(locations)} - Processing location: {location.upper()}")
                print(f"{'='*80}")
                
                jobs_count, inserted_count = scrape_location(page, location, mongo_collection, date_posted_days, cycle=cycle)
                
                if jobs_count > 0:
                    total_jobs_collected += jobs_count
                    total_jobs_inserted += inserted_count
                    successful_locations.append(location)
                else:
                    failed_locations.append(location)
                
                # Add delay between locations to be respectful to the server
                if i < len(locations):
                    print(f"\n⏳ Waiting 5 seconds before next location...")
                    time.sleep(5)
            
            # Final summary
            print(f"\n{'='*80}")
            print("SCRAPING SUMMARY")
            print(f"{'='*80}")
            print(f"✅ Successful locations ({len(successful_locations)}): {', '.join(successful_locations)}")
            if failed_locations:
                print(f"❌ Failed locations ({len(failed_locations)}): {', '.join(failed_locations)}")
            print(f"📊 Total jobs collected: {total_jobs_collected}")
            print(f"📊 Total jobs inserted to MongoDB: {total_jobs_inserted}")
            print(f"📊 Database: {MONGODB_DATABASE}.{MONGODB_COLLECTION}")
            
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            # Close the context/browser
            context.close()
            # Close MongoDB connection
            mongo_client.close()
            print("✅ MongoDB connection closed")

if __name__ == "__main__":
    main()