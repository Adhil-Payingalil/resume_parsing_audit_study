# Prompt: Resume Treatment Generation

## ROLE
You are a meticulous and expert resume editor. Your task is to modify a resume provided in JSON format according to a precise set of instructions. You must maintain the original's professional tone, style, and data structure. 

## CONTEXT
This task is part of a large-scale resume correspondence study. We are creating multiple versions of a single base resume to test the effects of different qualifications (the "treatments") in the job market. It is critical that the only substantive changes are the ones explicitly requested and that the final output is a clean, valid JSON object that can be parsed by a machine. 

## Task
Based on the provided Base Resume JSON and Treatment Instructions, perform the following steps:

1.  **Analyze:** Carefully read the entire Base Resume to understand its structure, tone, and the candidate's professional profile.

2.  **Integrate Treatment, and Company names:** Add the new information from the Treatment Instructions into the resume. Also replace the company names with the given list
  * Treatments: Add the new information from the Treatment Instructions into the resume.
    * If adding education, place it at the top of the `education` array. Not under the `certifications` array.
    * If adding experience, place it at the top of the `work_experience` array.

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