# Prompt for Generating Similar Companies and Position Title Variations

You are a research assistant for a resume correspondence study. Your task is to generate similar companies AND equivalent position title variations for a given list of work experience entries. This is crucial because we are sending multiple resumes to the same job posting, each with different company names AND position titles to avoid detection by ATS systems and recruiters.

## Task Requirements:

### 1. Similar Companies
- Base similarity on industry and size (employee count, Fortune 500 status, multinational presence, publicly listed)
- For well-known companies, use your knowledge or search capabilities
- For smaller/less-known companies, generate fictional but plausible companies
- Ensure companies are from the same country/region as the original
- All companies must be distinct from each other

### 2. Position Title Variations
- Generate 3 equivalent position titles that maintain the SAME seniority level and role function
- Titles must be industry-appropriate and commonly used
- Variations should be subtle but distinct enough to avoid pattern detection

**CRITICAL:** Position titles MUST maintain equivalence:
- Senior → Senior/Lead/Principal (NOT Junior)
- Junior → Junior/Associate/Entry-level (NOT Senior)
- Director → Director/Head of/VP (NOT Manager)
- Manager → Manager/Team Lead/Supervisor (NOT Director)

### Position Variation Examples:
- "Senior Software Engineer" → "Senior Software Developer", "Lead Software Engineer", "Principal Engineer"
- "Data Analyst" → "Business Intelligence Analyst", "Analytics Specialist", "Data Insights Analyst"
- "Product Manager" → "Product Owner", "Product Lead", "Program Manager"
- "Marketing Coordinator" → "Marketing Specialist", "Marketing Associate", "Marketing Executive"

## Output Format:

```json
[
  {
    "Original_company": "Original Company Name",
    "Original_position": "Original Position Title",
    "Variations": [
      {
        "Type_I": {
          "company": "Similar Company 1",
          "position": "Equivalent Position 1"
        }
      },
      {
        "Type_II": {
          "company": "Similar Company 2",
          "position": "Equivalent Position 2"
        }
      },
      {
        "Type_III": {
          "company": "Similar Company 3",
          "position": "Equivalent Position 3"
        }
      }
    ]
  },
  ...
]
```

## Guidelines:

1. **Maintain Seniority:** Position variations MUST be at the same seniority level
2. **Industry Context:** Consider the company's industry when suggesting position titles
3. **Common Titles:** Use widely recognized position titles, avoid overly creative names
4. **Consistency:** Ensure company size matches position seniority (don't put "VP" at a startup)
5. **Distinctness:** All 3 company-position combinations should be distinct

## Error Handling:

If the original company is a placeholder (e.g., "XYZ Holdings Limited"), return the string: "Place holder company found"

## Examples:

### Example 1: Large Tech Company
```json
{
  "Original_company": "Amazon.com, Inc.",
  "Original_position": "Senior Data Analyst",
  "Variations": [
    {"Type_I": {"company": "Shopify Inc.", "position": "Senior Analytics Specialist"}},
    {"Type_II": {"company": "Salesforce", "position": "Lead Data Analyst"}},
    {"Type_III": {"company": "Adobe Inc.", "position": "Principal Data Analyst"}}
  ]
}
```

### Example 2: Consulting Firm
```json
{
  "Original_company": "Deloitte",
  "Original_position": "Management Consultant",
  "Variations": [
    {"Type_I": {"company": "PwC", "position": "Strategy Consultant"}},
    {"Type_II": {"company": "EY", "position": "Business Consultant"}},
    {"Type_III": {"company": "KPMG", "position": "Advisory Consultant"}}
  ]
}
```

### Example 3: Small Local Company (fictional variations)
```json
{
  "Original_company": "Acme Consulting Ltd.",
  "Original_position": "Junior Business Analyst",
  "Variations": [
    {"Type_I": {"company": "Beta Advisory Group", "position": "Associate Business Analyst"}},
    {"Type_II": {"company": "Gamma Consulting", "position": "Junior Data Analyst"}},
    {"Type_III": {"company": "Delta Partners", "position": "Entry-level Analyst"}}
  ]
}
```

## Input
The following work experience entries (with company, position, and location) need variations generated:

{company_names}

Note: The input will be provided as a dictionary with 'work_experience_entries' containing a list of jobs with their company, position, and location information.