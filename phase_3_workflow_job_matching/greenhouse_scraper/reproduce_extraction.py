
import re

def simplify_line(line):
    return re.sub(r'[^a-z0-9]', '', line.lower())

def extract_description_logic(content, job_title):
    lines = content.split('\n')
    
    # Start Markers
    start_keywords = [
        'about the role', 'what you\'ll do', 'responsibilities', 'requirements', 
        'qualifications', 'what we\'re looking for', 'role overview', 'position overview',
        'about this role', 'key responsibilities', 'job summary', 'role summary',
        'position summary', 'we are looking for', 'the ideal candidate', 
        'you will be responsible', 'about you and the role', 'about the position', 
        'about this position', 'the role', 'this role', 'position details', 'job details',
        'what you\'ll be doing', 'what you will do', 'key duties', 
        'main responsibilities', 'primary responsibilities',
        'who we are', 'about us', 'about the company', 'company overview',
        'location:', 'why join', 'why work', 'why us'
    ]
    
    exact_start_markers = ["apply"]
    
    # End Markers
    end_markers = [
        "create a job alert",
        "apply for this job",
        "voluntary self-identification",
        "privacy policy",
        "candidate privacy notice",
        "submit application",
        "apply now"
    ]
    
    description_lines = []
    extracted = False
    state = "SEARCHING"
    
    simplified_title = simplify_line(job_title) if job_title else None
    
    start_index = -1
    end_index = -1

    print("\n--- Processing Lines ---")
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped:
            if state == "EXTRACTING":
                description_lines.append(line)
            continue
        
        line_lower = line_stripped.lower()
        
        # Check End Markers
        is_end = False
        for marker in end_markers:
            if marker in line_lower:
                if line_lower == "apply" and "apply" in exact_start_markers:
                    break 
                is_end = True
                print(f"[DEBUG] End marker found: '{marker}' in line: '{line_stripped}'")
                break
        
        if is_end:
            if state == "EXTRACTING":
                state = "STOPPED"
                end_index = i
                break 
            elif state == "SEARCHING":
                end_index = i
                print(f"[DEBUG] End marker found while SEARCHING. Breaking.")
                break
        
        # STATE: SEARCHING
        if state == "SEARCHING":
            found_start = False
            trigger = ""
            
            # 1. Check Job Title (Fuzzy)
            if simplified_title:
                sim_line = simplify_line(line_stripped)
                if simplified_title in sim_line and len(sim_line) < len(simplified_title) + 20:
                    found_start = True
                    trigger = f"Title Match: '{line_stripped}' matches '{simplified_title}'"
            
            # 2. Check "Apply" exact match
            if not found_start:
                if line_lower in exact_start_markers:
                    found_start = True
                    trigger = "Exact 'Apply' match"
                    
            # 3. Check Section Keywords
            if not found_start:
                    if any(keyword in line_lower for keyword in start_keywords):
                        if len(line_stripped) < 100 or line_stripped.startswith('#'):
                            found_start = True
                            trigger = f"Keyword match in '{line_stripped}'"
            
            # 4. Check "At [Company]" or "Why [Company]" patterns
            if not found_start:
                if line_stripped.startswith("At ") or line_stripped.startswith("Why "):
                        if len(line_stripped) < 100 or line_stripped.strip().endswith(':'):
                            found_start = True
                            trigger = "At/Why pattern match"
                        elif line_stripped.startswith("At ") and "we " in line_lower:
                            found_start = True
                            trigger = "At..we pattern match"

            if found_start:
                print(f"[DEBUG] Start marker triggered: {trigger}")
                state = "EXTRACTING"
                extracted = True
                start_index = i
                if line_lower not in ["apply"]:
                        description_lines.append(line)
                continue 

        # STATE: EXTRACTING
        elif state == "EXTRACTING":
            if line_lower in ["apply", "apply now", "please apply"]:
                continue
            
            line_no_images = re.sub(r'!\[.*?\]\(.*?\)', '', line).strip()
            
            if line_no_images:
                if "[Back to jobs]" in line_no_images:
                        line_no_images = line_no_images.replace("[Back to jobs]", "")
                        line_no_images = re.sub(r'\(http.*?\)', '', line_no_images).strip()
                
                if line_no_images:
                    description_lines.append(line_no_images)

    clean_text = '\n'.join(description_lines).strip()
    
    print(f"\nExtracted: {extracted}")
    print(f"Clean Text Length: {len(clean_text)}")
    print(f"Clean Text Preview: {clean_text[:200]}")
    
    if extracted and len(clean_text) > 100:
        if job_title and job_title.lower() not in clean_text.lower()[:200]:
            clean_text = f"# {job_title}\n\n{clean_text}"
        return clean_text, "clean"
    
    if not extracted and end_index > 0:
        fallback_lines = lines[:end_index]
        fallback_text = '\n'.join(fallback_lines).strip()
        if len(fallback_text) > 100:
            return fallback_text, "fallback"

    return content.strip(), "full_page_content"

# Reproduce Case
job_title = "Change Management Consultant"
raw_content = """Title: Change Management Consultant

URL Source: https://job-boards.greenhouse.io/levio/jobs/8422292002?gh_src=my.greenhouse.search

Markdown Content:
Job Application for Change Management Consultant at Levio
===============

[![Image 1: Levio Logo](https://s2-recruiting.cdn.greenhouse.io/external_greenhouse_job_boards/logos/400/164/800/original/Logo_levio_bilingue.png?1685735908)](https://levio.ca/carrieres/?gh_src=my.greenhouse.search)

Create a Job Alert

Interested in building your career at Levio? Get future opportunities sent straight to your email.

[Create alert](https://my.greenhouse.io/users/sign_in?job_board=levio&source=job_alert_post)

Apply for this job
------------------

*

indicates a required field

First Name* 

Last Name* """

print(f"Testing Job Title: {job_title}")
result, method = extract_description_logic(raw_content, job_title)
print(f"\nFinal Result Method: {method}")
