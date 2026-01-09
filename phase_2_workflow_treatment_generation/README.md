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
python "phase_2_workflow_treatment_generation/run_phase_2.py" --sector ITC
```

**Auto-Run (Headless / No UI):**
Use this if you trust the Gemini output 100% and want to run a bulk batch overnight.
python "phase_2_workflow_treatment_generation/run_phase_2.py" --sector ITC --skip-ui
```

## Experimental Logic (Research Specific)

> [!NOTE]
> This workflow is designed specifically for an Audit Study. The logic below is complex and tailored to generating controlled variations of resumes to test for bias.

### 1. The Resume Generation Process
For every **Standardized Resume** (Source) input, this system generates **four (4)** distinct variations. The goal is to isolate the effect of "Canadian" credentials while keeping the rest of the resume identical semantically.

1.  **Normalization (Control Generation)**:
    *   The source resume is first cleaned of any specific "North American" markers  to create a neutral baseline.
    *   **Company Mappings**: We identify every company in the source resume and map it to a  placeholder or a non-Canadian equivalent (if applicable) to ensure the control is truly neutral.
    *   **Result**: This forms the **Control** document.

2.  **Treatment Injection**:
    *   **Type I (Canadian Education - CEC)**: We take the Control resume and *replace* the education section with a random entry from `education_credentials.csv` (matched by sector).
    *   **Type II (Canadian Work Experience - CWE)**: We take the Control resume and *inject* a Canadian job entry from `work_experience_credentials.csv` into the work history.
    *   **Type III (Mixed)**: Both CEC and CWE are applied.

### 2. Semantic Integrity Check (The "Drift" Test)
A major challenge with using LLMs (Gemini) to rephrase resumes is "Hallucination" or "Semantic Drift"—where the AI accidentally changes the candidate's skills or experience level.

*   **Mechanism**: We use a local SBERT model (`all-MiniLM-L6-v2`) to embed the text of the *Control* resume and the *Treated* resume.
*   **Threshold**: We calculate the **Cosine Similarity** between them.
*   **Logic**: If the similarity drop is too significant (e.g., < 0.95), it implies the LLM changed the resume too much, and the sample might need to be discarded or flagged. This ensures that the *only* significant variable changing is the Treatment (Education/Work), not the candidate's core competency.

### 3. Manual Company Validation (The Loop)
Automated Entity Recognition (NER) is not 100% accurate. If the system fails to correctly identify a company name (e.g., it thinks "Python" is a company), the anonymization step will fail.
*   **Human-in-the-Loop**: The `company_research_ui.py` pops up to force a human to verify.
*   **Why**: This validation is critical for the internal validity of the audit study.

## Workflow Steps

1.  **Fetch**: Gets a resume from MongoDB (`Standardized_resume_data`).
2.  **Research (Human Step)**: Gemini identifies companies -> Human confirms via UI.
3.  **Clean**: Removes location markers.
4.  **Generate**:
    *   Create **Control** (Cleaned Baseline).
    *   Create **Type I** (Education).
    *   Create **Type II** (Work).
    *   Create **Type III** (Both).
5.  **Validate**: Run SBERT similarity check.
6.  **Save**: Stores all 4 versions in `Treated_resumes`.

## Local Models (`all-MiniLM-L6-v2`)

This workflow uses a **Semantic Similarity** check to ensure the rephrased resumes haven't drifted too far from the original meaning.

*   **Model**: `all-MiniLM-L6-v2` (SentenceTransformer).
*   **Location**: `models/all-MiniLM-L6-v2/` (Inside this directory).

### Best Practices
1.  **Keep the Local Copy**: The script is configured to look for the model in the `models/` folder first. This prevents the script from downloading the model every time on a new machine or empty cache.
2.  **Versioning**: The local folder ensures everyone uses the exact same model version.
3.  **Missing Model**: If the `models` folder is deleted, the script *will* attempt to download the model from HuggingFace automatically. This  will be slower on the first run.

### Installation (If deleted)
If you need to restore the local model manually:
```bash
# In a python shell
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
model.save('models/all-MiniLM-L6-v2')
```
