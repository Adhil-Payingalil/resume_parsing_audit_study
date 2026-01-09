# Phase 1: Resume Extraction & Standardization Workflow

This directory contains the workflow for **Phase 1**, which focuses on converting raw resumes (PDF/DOCX) into structured JSON data using the Gemini API.

## Directory Structure

*   **`extraction_multi_agent.py`**: The main script that runs the extraction pipeline.
*   **`Resume_inputs/`**: Place your raw resume files (PDF or DOCX) here. The script reads from this folder.
*   **`Prompts/`**: Contains the markdown prompt templates used by the Gemini agents.
    *   `prompt_std_resume_data.md`: For extracting raw data.
    *   `prompt_std_key_metrics.md`: For analyzing key metrics.
    *   `prompt_std_validation.md`: For validating the extraction quality.

## Outputs

The script generates outputs in the root `data/` directory (shared across the project):
*   **`data/Processed_resumes/`**: Successfully processed PDF files are moved here.
*   **`data/text_output/`**: Contains raw text responses from the LLM (for debugging).
*   **MongoDB**: The structured data is saved to the `Standardized_resume_data` collection in your MongoDB instance.

## Configuration

The script uses environment variables for configuration. You can set these in your `.env` file:

*   `GEMINI_API_KEY`: Required.
*   `MONGODB_URI`: Required.
*   `TEST_MODE`: Optional. Set to `True` to enable **Test Mode**.
    *   **Test Mode**: Skips saving to MongoDB and prints the extracted JSON to the terminal instead. Useful for debugging prompts.

## How to Run

1.  Ensure you have your `.env` file set up in the project root with `GEMINI_API_KEY` and `MONGODB_URI`.
2.  Place resume files in `Phase 1 Workflow/Resume_inputs`.
3.  Run the script from the project root or this directory:

```bash
# From Project Root
python "Phase 1 Workflow/extraction_multi_agent.py"
```

## Workflow Logic

The pipeline follows a **Multi-Agent** approach for each file:
1.  **Conversion**: Converts `.docx` files to PDF if necessary.
2.  **Pass 1 (Extraction)**: Extracts structured resume data.
3.  **Pass 2 (Key Metrics)**: Analyzes the resume for key details (years of experience, etc.).
4.  **Pass 3 (Validation)**: A separate agent validates the quality of the extraction.
    *   If the **Validation Score < 7**, the pipeline automatically **re-runs** (up to 2 times) to attempt a better extraction.
5.  **Embeddings**: Generates a vector embedding for the resume text.
6.  **Save**: Stores the final result in MongoDB.
