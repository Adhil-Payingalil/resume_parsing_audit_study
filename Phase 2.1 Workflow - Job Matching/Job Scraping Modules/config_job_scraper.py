

CONFIG = {
    # List of job boards to scrape
    # Options: 'indeed', 'linkedin', 'zip_recruiter', 'glassdoor', 'google', 'bayt', 'naukri'
    "SITE_NAME": ["indeed"],

    # List of job titles or keywords to search for
    "SEARCH_TERMS": ["Software Developer"],

    # List of locations to search in (e.g., city, state/province, country)
    "LOCATIONS": ["Toronto, ON"],

    # Number of job results to retrieve per search term per platform
    # Max ~1000, recommended 50-100 for LinkedIn
    "RESULTS_WANTED":2,

    # Filter by job type. Options: 'fulltime', 'parttime', 'internship', 'contract', or None for no filter
    "JOB_TYPE": None,

    # Set to True to only get remote jobs (if supported by platform)
    "IS_REMOTE": False,

    # Only get jobs posted in the last X hours (e.g., 72 = last 3 days). None for no filter
    "HOURS_OLD": None,

    # Country for Indeed/Glassdoor searches (e.g., 'Canada', 'USA')
    "COUNTRY_INDEED": "Canada",

    # List of proxies to use for scraping (optional, for avoiding rate limits)
    # Example: ["user:pass@proxy1:port", "user:pass@proxy2:port"]
    "PROXIES": None,

    # Time to wait between each request to avoid rate-limiting (in seconds)
    "DELAY_SECONDS": 7,

    # Verbosity: 0 = errors only, 1 = errors+warnings, 2 = all logs
    "VERBOSE": 2,

    # Description format: 'markdown' or 'html' for job descriptions
    "DESCRIPTION_FORMAT": "markdown",

    # Only jobs with easy apply (if supported)
    "EASY_APPLY": False,

    # Fetch full description and direct job URL for LinkedIn
    "LINKEDIN_FETCH_DESCRIPTION": False
} 

"""
# Job Scraper Configuration

This file contains all user-configurable parameters for the job scraper integration module.

## How to Use
- Edit the values in the CONFIG dictionary to control scraping behavior.
- All scripts that import CONFIG will use these settings.

## Parameter Reference
- **SITE_NAME**: List of job boards to scrape. Options: 'indeed', 'linkedin', 'zip_recruiter', 'glassdoor', 'google', 'bayt', 'naukri'.
- **SEARCH_TERMS**: List of job titles or keywords to search for.
- **LOCATIONS**: List of locations to search in (e.g., city, state/province, country).
- **RESULTS_WANTED**: Number of job results to retrieve per search term per platform (max ~1000, recommended 50-100 for LinkedIn).
- **JOB_TYPE**: Filter by job type. Options: 'fulltime', 'parttime', 'internship', 'contract', or None for no filter.
- **IS_REMOTE**: Set to True to only get remote jobs (if supported by platform).
- **HOURS_OLD**: Only get jobs posted in the last X hours (e.g., 72 = last 3 days). None for no filter.
- **COUNTRY_INDEED**: Country for Indeed/Glassdoor searches (e.g., 'Canada', 'USA').
- **PROXIES**: List of proxies to use for scraping (optional, for avoiding rate limits).
- **DELAY_SECONDS**: Time to wait between each request to avoid rate-limiting.
- **VERBOSE**: 0 = errors only, 1 = errors+warnings, 2 = all logs.
- **DESCRIPTION_FORMAT**: 'markdown' or 'html' for job descriptions.
- **EASY_APPLY**: Only jobs with easy apply (if supported).
- **LINKEDIN_FETCH_DESCRIPTION**: Fetch full description and direct job URL for LinkedIn.

"""