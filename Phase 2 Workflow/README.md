# Phase 2: Treatment Generation Workflow

This workflow is responsible for taking "Standardized" resumes (from Phase 1) and generating "Treated" versions by injecting:
1.  **Canadian Education (CEC)**
2.  **Canadian Work Experience (CWE)**
3.  **Both (Mixed)**

The result is a set of 4 resumes for every 1 source resume: Control, Type I, Type II, Type III.

## Directory Structure

*   **`run_phase_2.py`**: The main entry point. Run this to start the process.
*   **`company_research_ui.py`**: A helper UI that pops up to let you manually validate company names before they are processed.
*   **`education_credentials.csv`**: Database of Canadian Education treatments.
*   **`work_experience_credentials.csv`**: Database of Canadian Work Experience treatments.
*   **`Prompts/`**: Markdown prompt templates for Gemini.
*   **`libs/treatment_generator.py`**: (Located in project root `libs/`) The core logic engine.

## Configuration & Usage

### 1. CSV Setup
Ensure your treatment CSVs are populated.
*   **`education_credentials.csv`**: columns [`sector`, `Degree`, `Institution`, `Location`, `Year`]
*   **`work_experience_credentials.csv`**: columns [`sector`, `company`, `position`, `highlights`, `duration`, `location`]

### 2. Run the Script

**Basic Run (With Manual UI Validation):**
This is the default recommended mode. It will pause for each resume and ask you to fix/approve company names.
```bash
python "Phase 2 Workflow/run_phase_2.py" --sector ITC
```

**Auto-Run (Headless / No UI):**
Use this if you trust the Gemini output 100% and want to run a bulk batch overnight.
```bash
python "Phase 2 Workflow/run_phase_2.py" --sector ITC --skip-ui
```

## Logic Flow

1.  **Fetch**: Gets a resume from MongoDB (`Standardized_resume_data`).
2.  **Research**: Uses Gemini to identify company names in the resume.
    *   *Manual Step*: You verify these names in the UI.
3.  **Clean**: Removes North American markers (locations, phone numbers).
4.  **Control**: Saves a "Control" version (Cleaned, Rephrased).
5.  **Treatments**:
    *   **Type I**: Adds Canadian Education.
    *   **Type II**: Adds Canadian Work Experience.
    *   **Type III**: Adds Both.
6.  **Save**: Stores all 4 versions in `Treated_resumes` collection.
