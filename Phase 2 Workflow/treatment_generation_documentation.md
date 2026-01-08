# Documentation for `treatment_generation.py`

This document provides an overview of the `treatment_generation.py` script, which automates the generation of treated resumes for a correspondence study. It covers the agents involved, the prompts used, how to run the script with arguments, and a textual flowchart of the overall process.

## 1. Agents and Their Roles

The script utilizes three distinct agents, each powered by a Gemini model, to process resumes. Below is a breakdown of the agents, their roles, and the number of calls they receive per resume:

- **Control Refiner Agent** (`control_refiner_model`):
  - **Role**: Removes North American-specific elements (e.g., company names and locations) from the source resume to create a neutral "control" version.
  - **Model**: `gemini-2.5-flash`
  - **Calls per Resume**: 1 call to process the source resume and generate the control version.
  - **Purpose**: Ensures the control resume is free of regional identifiers, providing a baseline for treatment comparisons.

- **Company Research Agent** (`company_research_model`):
  - **Role**: Generates a list of similar Canadian companies to replace original company names in the work experience section, reducing the risk of detection by Applicant Tracking Systems (ATS).
  - **Model**: `gemini-2.5-pro` with Google search enabled.
  - **Calls per Resume**: 1 call per resume, with potential retries if the user rejects the output in the UI validation step.
  - **Purpose**: Provides realistic, sector-specific company names to enhance treatment authenticity and avoid experiment detection.

- **Treatment Generation Agent** (`treatment_model`):
  - **Role**: Generates three treated resume versions (Type I: Canadian Education, Type II: Canadian Work Experience, Type III: Both) by applying treatments and rephrasing the resume with specific style modifiers.
  - **Model**: `gemini-2.5-pro`
  - **Calls per Resume**: Up to 3 calls per resume (one for each treatment type: Type I, Type II, Type III), with up to 2 retries per treatment if the similarity score is below the threshold (0.60). Maximum of 9 calls (3 treatments × 3 attempts).
  - **Purpose**: Creates varied resume versions with Canadian-specific treatments while ensuring stylistic differences through unique style modifiers.

**Total Calls per Resume**: 
- Minimum: 5 calls (1 control + 3 treatments + 1 company research, assuming no retries).
- Maximum: Up to 11 calls (1 control + 9 treatment calls with retries + 1 company research, plus potential company research retries).

## 2. Prompts and UI: Current Status and Limitations

The script uses three prompt templates stored in the `Prompts` directory, each tailored to a specific agent's task. Additionally, a UI component is used for validating company mappings. Below is an overview of their current standing and limitations:

### Prompts

- **Control Refiner Prompt** (`prompt_control_refiner.md`):
  - **Purpose**: Instructs the model to remove North American-specific elements (e.g., company names, locations) from the resume while preserving its structure and content.
  - **Status**: Functional, replaces regional identifiers with generic placeholders or removes them entirely.
  - **Limitations**:
    - Relies on the model's ability to accurately identify North American-specific elements, which may miss subtle references (e.g., culturally specific certifications or jargon).
    - No explicit validation step to ensure all regional elements are removed, which could lead to incomplete neutralization.
    - Assumes the input resume data is well-structured JSON, which may fail if the source data is malformed.

- **Company Research Prompt** (`prompt_similar_company_generation.md`):
  - **Purpose**: Generates a list of similar Canadian companies for each company in the resume’s work experience, validated via a UI dialog.
  - **Status**: Functional, with Google search enabled to ensure realistic company suggestions. User validation via `TextEditorDialog` ensures accuracy.
  - **Limitations**:
    - Dependent on external Google search, which may introduce inconsistencies if search results are unreliable or outdated.
    - The UI validation step introduces a manual bottleneck, requiring user interaction for each resume, which may be impractical for large-scale processing.
    - Risk of "placeholder" company names being generated, which requires manual correction to avoid experiment detection.

- **Treatment Generation Prompt** (`prompt_treatment_generation.md`):
  - **Purpose**: Guides the model to apply Canadian Education (CEC) and/or Canadian Work Experience (CWE) treatments, rephrase the resume, and apply a specific style modifier to ensure variation across treatments.
  - **Status**: Supports three treatment types (Type I: CEC, Type II: CWE, Type III: CEC + CWE) with randomized style modifiers to prevent identical rephrasing.
  - **Limitations**:
    - The model does not have access to previous treatments for context, which could lead to overlapping language across versions if style modifiers are insufficiently distinct.
    - The randomization of style modifiers (`STYLE_MODIFIERS`) is limited to five predefined styles, which may not be enough for large datasets to ensure unique rephrasing.
    - Cosine similarity validation may be unreliable (noted in TODO: similarity scores are currently 0), requiring QA to assess its effectiveness.

### UI for Company Mappings

- **Component**: `TextEditorDialog` (PySide6-based)
- **Purpose**: Presents the generated list of similar Canadian companies to the user for validation and editing before they are applied to the treated resumes.
- **Workflow**:
  - The Company Research Agent generates a JSON-formatted list of company mappings (original company names mapped to similar Canadian companies).
  - The UI displays this JSON in a text editor, allowing the user to review and modify the mappings.
  - The user has three options:
    - **Accept**: Confirms the mappings as-is, and the script proceeds to use them for company replacement in the treated resumes.
    - **Retry**: Rejects the current mappings and triggers the Company Research Agent to regenerate a new list, restarting the UI validation process.
    - **Cancel**: Aborts the processing of the current resume, logging it as a failed file and exiting the script.
  - The final validated mappings are parsed back into JSON for use in the `replace_companies` function.
- **Limitations**:
  - Manual validation is time-consuming and may not scale well for large datasets.
  - Requires user expertise to ensure the suggested companies are appropriate and realistic for the sector.
  - If the user cancels, the entire file is skipped, potentially leading to data loss unless manually restarted.
  - Invalid JSON edits by the user (e.g., syntax errors) cause the script to exit with an error, requiring careful user attention.

## 3. How to Use the Script with Arguments

The script accepts command-line arguments to specify the sector and optionally limit processing to specific files. Below are the usage details:

- **Command Structure**:
  ```bash
  python treatment_generation.py --sector <SECTOR> [--files <FILE_ID_1> <FILE_ID_2> ...]
  ```

- **Arguments**:
  - `--sector` (required):
    - Specifies the industry sector (e.g., "ITC", "HEALTHCARE") in all caps, matching the prefix used in the MongoDB collection.
    - Example: `--sector ITC`
  - `--files` (optional):
    - A space-separated list of specific file IDs (e.g., `ITC resume 01.pdf ITC resume 02.pdf`) to process. If omitted, the script processes all files for the specified sector.
    - Example: `--files "ITC resume 01.pdf" "ITC resume 02.pdf"`

- **Examples**:
  - Process all files for the ITC sector:
    ```bash
    python treatment_generation.py --sector ITC
    ```
  - Process specific files for the ITC sector:
    ```bash
    python treatment_generation.py --sector ITC --files "ITC resume 01.pdf" "ITC resume 02.pdf"
    ```

- **Notes**:
  - The script expects the MongoDB collections (`Standardized_resume_data` and `Treated_resumes`) to be set up and accessible via the configured `MONGO_CLIENT`.
  - Treatment data (Canadian Education and Work Experience) must be available in `Education_treatment_final.xlsx` and `Work_experience_final.xlsx` in the script directory, filtered by the specified sector.
  - The script opens a UI (`TextEditorDialog`) for validating company mappings, requiring user interaction unless canceled.

## 4. Overall Flowchart (Text-Based)

Below is a textual representation of the script’s workflow for processing each resume:

```
[Start]
   |
   v
[Parse Command-Line Arguments]
   - Read --sector (required) and --files (optional)
   - Validate sector and filter files
   |
   v
[Fetch Source Files from MongoDB]
   - If --files provided, use specified file IDs
   - Else, fetch all files for the sector from Standardized_resume_data
   - Exit if no files found
   |
   v
[For Each File in Sector Files]
   |
   v
[Retrieve Source Resume Data]
   - Fetch resume data from MongoDB using file_id
   - Skip if no resume data found (log error)
   |
   v
[Generate Control Resume]
   - Call Control Refiner Agent (1 call)
   - Remove North American elements
   - Save control resume to documents_to_save with metadata
   |
   v
[Prepare Treatment Prompts]
   - Select 2 CEC and 2 CWE treatments randomly
   - Assign unique style modifiers for Type I, II, III
   - Generate prompts for Type I (CEC), Type II (CWE), Type III (CEC + CWE)
   - Exit if treatments unavailable (log error)
   |
   v
[Generate Company Mappings]
   - Call Company Research Agent (1 call, potential retries)
   - Extract company names from source resume
   - Generate similar Canadian companies
   - Open UI (TextEditorDialog) for user validation
   - Retry if user selects "retry"; exit if "canceled"
   - Skip file if mappings invalid or contain placeholders (log error)
   |
   v
[Generate Treated Resumes]
   - For each treatment (Type I, II, III):
      - Call Treatment Generation Agent (up to 3 calls per treatment)
      - Apply treatment and style modifier
      - Validate with cosine similarity (threshold: 0.60)
      - Retry up to MAX_RETRIES (2) if similarity < threshold
      - Replace company names using company mappings
      - Save treated resume to documents_to_save with metadata
      - Log error and skip file if retries fail
   |
   v
[Save All Resumes to MongoDB]
   - Insert control and treated resumes to Treated_resumes collection
   - Log success or error
   |
   v
[Log Failed Files]
   - Report any files that failed processing or similarity checks
   |
   v
[End]
```

This flowchart outlines the sequential processing of each resume, including error handling, retries, and user validation steps to ensure robust treatment generation.