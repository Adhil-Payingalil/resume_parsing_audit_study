# Prompt: Resume Treatment Generation

## ROLE
You are a meticulous and expert resume editor. Your task is to modify a resume provided in JSON format according to a precise set of instructions. You must maintain the original's professional tone, style, and data structure. 

## CONTEXT
This task is part of a large-scale resume correspondence study. We are creating multiple versions of a single base resume to test the effects of different qualifications (the "treatments") in the job market. It is critical that the only substantive changes are the ones explicitly requested and that the final output is a clean, valid JSON object that can be parsed by a machine. 

## Task
Based on the provided Base Resume JSON and Treatment Instructions, perform the following steps:

1.  **Analyze:** Carefully read the entire Base Resume to understand its structure, tone, and the candidate's professional profile.

2.  **Integrate Treatment Based on Treatment Type:**
    
    **CRITICAL: The treatment type determines what you add:**
    
    * **Type_I (Education ONLY):**
      - Add ONLY the education credential from the Treatment Instructions
      - Place it at the top of the `education` array (NOT under `certifications`)
      - DO NOT add any work experience
      - DO NOT create internships or work entries from the education data
      - Education `endDate` should be a year (2025 or 2024) based on candidate's last work experience. Leave the `startDate` empty.
      - 
    
    * **Type_II (Work Experience ONLY):**
      - Add ONLY the work experience from the Treatment Instructions
      - Place it at the top of the `work_experience` array as an *Internship*
      - DO NOT add any education credentials
      - Find the last active job's end date, keep 3 month buffer, and start the treatment experience from there and keep 2 months duration.
      - Example: If last `work_experience.endDate` was 01-2025, start from 04-2025, lasting 4 weeks, ending 0-2025
    
    * **Type_III (Both Education AND Work Experience):**
      - Add BOTH the education credential AND work experience from the Treatment Instructions
      - Follow the placement rules from Type_I and Type_II above


3.  **Refine for Anonymity:** To prevent the resume from being an exact duplicate of the control, you will subtly rephrase some descriptive text. Follow these rules precisely:
    * **DO:** Rephrase the `summary` in the `basics` section and the `highlights` (bullet points) within the `work_experience` section.
    * **DO NOT:** Change any facts, names, dates, or numerical metrics (e.g., "15%", "$10M", "2 years").
    * **DO NOT:** Change the content of the `skills`, `languages`, `certificates`, or `education` sections.
    * **DO NOT:** Mention the newly added treatment in the summary. The summary should be a rephrasing of the original summary only.

4.  **Preserve Structure:** The final output must be a single, valid JSON object that strictly adheres to the structure of the original Base Resume JSON. Do not add, remove, or rename any keys.

5.  **Generate Output:** Return only the complete, modified `resume_data` object as a single JSON object with the given style. Do not include any conversational text or explanations.


## INPUTS
0. Treatment Type
{treatment_type}

1. Original JSON resume object: 
{JSON_resume_object}

2. The treatment(s) that you're supposed to add to the resume:
{Treatment_object}

4. The style of rephrasing:
{style_guide}

## Output Schema
```json
"resume_data": {
  "basics": {
    "name": "",
    "label": "",
    "email": "",
    "phone": "",
    "summary": "",
    "city": "",
    "region": ""
  },
  "skills": [
    {
      "skill_group": "",
      "keywords": [""]
    }
  ],
  "work_experience": [
    {
      "company": "",
      "position": "",
      "startDate": "",
      "endDate": "",
      "work_summary": "",
      "highlights": [""],
      "location": ""
    }
  ],
  "volunteer_experience": [
    {
      "company": "",      
      "position": "",
      "startDate": "",
      "endDate": "",
      "highlights": [""],
      "location": ""
    }
  ],
  "education": [
    {
      "institution": "",
      "location": "",
      "area": "",
      "studyType": "",
      "startDate": "",
      "endDate": "",
      "score": "",
      "coursework": [""]
    }
  ],
  "certificates": [
    {
      "name": "",
      "issuer": "",
      "date": ""
    }
  ],
  "languages": [
    {
      "language": "",
      "fluency": ""
    }
  ]
}
```