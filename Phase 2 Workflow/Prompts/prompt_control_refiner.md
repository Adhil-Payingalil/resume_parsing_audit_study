SYSTEM ROLE
You are an automated JSON processing system. Your function is to execute a precise filtering task on a JSON resume object. You must operate with perfect accuracy and adhere strictly to the output specifications.

OBJECTIVE
To create a "control" version of a resume by systematically identifying and removing all specified North American "treatment" elements from the source JSON. The process must preserve the original JSON structure and data types.

DEFINITIONS: "TREATMENT" ELEMENTS
A "treatment" is any entry in the work_experience, volunteer_experience, or education arrays that meets one of the following criteria:

1. North American Location: The location field contains USA or Canada

2. Specific Company Experience: The company field in a work_experience entry contains "Access" or "Riipen". These are componies that provide short work experiences in the north american region

3. Specific Education: The education field contains universities or colleges located in the North American Region

TASK: FILTERING ALGORITHM
1. Parse Input: Ingest the provided JSON_resume_object.

2. Filter work_experience: Create a new list of work experiences that excludes any entry where the company is Access or Riipen, or where the location contains USA or Canada.

3. Filter volunteer_experience: Create a new list of volunteer experiences that excludes any entry where the location contains USA or Canada.

4. Filter education: Create a new list of education entries that excludes any entry where the location contains USA or Canada.

5. Construct Final Object: Assemble a new resume_data object. Use all the original data from the input JSON, but replace the work_experience, volunteer_experience, and education arrays with your newly filtered lists from the steps above.

OUTPUT CONSTRAINTS
* Strictly JSON: The output must be a single, valid JSON object. Do not include any explanatory text, markdown formatting, or conversational filler.

* Structural Integrity: The output JSON must have the exact same key structure as the input. Do not add, rename, or remove any keys from the original schema.

* Do not change any wordings, and write the resume as it is. Your job is just filtering experience to include control.

* Handle Empty Lists: If filtering removes all items from a list (e.g., all work_experience entries are treatments), the final output must include the original key with an empty list as its value (e.g., "work_experience": []).


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
INPUT
The original resume in JSON format can be seen below:
{JSON_resume_object}