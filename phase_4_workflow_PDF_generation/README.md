# Phase 4: PDF Generation Workflow

This directory contains the `pdf_generation_workflow.ipynb` notebook, which manages the end-to-end process of generating treated resumes for the audit study. The workflow combines job match data from Phase 3 with randomized PII (Personally Identifiable Information) and specific design templates, and then triggers an external n8n webhook to render the final PDFs.

## Overview

The core purpose of this phase is to take successful job descriptions extracted from greenhouse boards, assign applicant PII and resume design templates based on geographical clusters, and generate the final PDFs holding the tailored resumes for submission. 

The workflow uses four experimental conditions:
* `control`
* `Type_I`
* `Type_II`
* `Type_III`

To ensure robustness, design templates are randomized separately from treatment assignments to ensure that visual design is not confounded with the content treatment.

## Prerequisites

### Environment Variables (.env)
You must define the following environment variables in a `.env` file before running the notebook:
* `TEST_WEBHOOK_URL` - Webhook URL for the single file test.
* `PRODUCTION_WEBHOOK_URL` - Webhook URL for full batch processing.
* `WEBHOOK_USERNAME` - Basic Auth Username for the webhook.
* `WEBHOOK_PASSWORD` - Basic Auth Password for the webhook.
* `MONGODB_URI` - Connection string for the MongoDB instance used to track processed resumes.

### Required Input Files
The scripts expect the following CSV files in the same directory:
1. **Job Matches File (e.g., `cycle_17_matches.csv`)** - Output from Phase 3 containing valid job descriptions and the `key_metrics.basics.likely_home_country` field.
2. **`country_cluster_mapping.csv`** - Maps country values to broad geographic clusters (e.g., "South Asia", "Sub-Saharan Africa").
3. **`PII_country_cluster_mapping.csv`** - Contains the pool of PII profiles (Names, Emails, Phones) segregated by Geographic Cluster and Treatment type.

## Execution Flow

### 1. File Selection & Idempotency Check
The script queries the `n8n_resume_render_log` MongoDB collection to identify which job-treatment combinations have **already** been successfully rendered. 
* By default, `REPROCESS_ALREADY_PROCESSED = False` ensures that we only trigger generation for missing treatments.
* This makes the script safe to re-run in case of network interruptions or failures.

### 2. PII & Template Randomization
For each job to be processed:
* The geographic cluster is determined based on the job's `likely_home_country`. If the country is unknown, it defaults to `Anglosphere`.
* The four available PII records (one for each treatment) for that cluster are extracted and randomly shuffled.
* The 4 available design templates (`AVAILABLE_TEMPLATES`) are also randomly shuffled and assigned to each treatment. This decouples template aesthetics from the specific treatment condition.
* Gender is randomly chosen, and unique first and last names are generated to avoid duplicate naming across the 4 applications for a single job match.

### 3. Execution (Webhook Invocation)
The script iterates through the finalized assignments and sends JSON payloads containing the PII, the job description, the chosen template logic, etc., to the n8n webhook.
* **Asynchronous Processing**: Webhook calls are configured to trigger async rendering on the n8n side to avoid blocking script execution.
* **Batch Rate-Limiting**: The workflow processes jobs in small batches (e.g., `BATCH_SIZE = 4`) and implements a sleep interval (e.g., `130 seconds`) between batches to respect API limits and allow n8n enough time to render PDFs under load.
* **Robust Error Handling**: The tool stops execution if consecutive failures (e.g., `max_consecutive_errors = 2`) occur to prevent blind firing on unresponsive endpoints.

## Testing

A **Single File Test** block is available at the end of the notebook. It allows you to dispatch a single file execution to your `TEST_WEBHOOK_URL` and manually assign a specific `Template ID` or `test_treatment` to verify the JSON packaging or webhook routing without spamming the production endpoints.

## Auditing and Validity
During processing, an Audit section prints a DataFrame showing exactly which PII, name, email, and Template ID were assigned to each treatment for each Job Posting. A validation step ensures that there are strictly zero duplicate first names sent across treatments for identical job IDs.

## n8n Workflows

The `n8n Workflows` directory contains the JSON definitions for the two n8n workflows that power the PDF generation and logging processes. These can be imported directly into an n8n instance.

### 1. V4 Combined PDF Generation Workflow (`V4 Combined PDF Generation Workflow.json`)
This is the core rendering workflow triggered by the `pdf_generation_workflow.ipynb` script via webhook.
* **Payload Reception**: Receives the async webhook payload containing PII, template configurations, and JD details.
* **LLM Markdown Cleaning**: Cleans any unexpected markdown formatting (like ````markdown`) from the base resume text stored in MongoDB.
* **Resume Tailoring (Doc Tailoring Agent)**: Employs a Google Gemini Chat Model (acting as an expert resume optimizer) to dynamically tailor the base resume JSON to match the Job Description (JD). It extracts high-value keywords and buckets from the JD, aligns accomplishments, and rewrites the professional summary while adhering strictly to ATS constraints and preserving factual integrity.
* **Markdown Formatting**: Routes the tailored JSON through one of three specific Langchain agents corresponding to the assigned `markdown_template` ID to output the final mapped markdown string.
* **Quality Validation**: A Resume Validation node grades the final resume quality out of 100, checking for AI filler, placeholders, and JD keyword alignment.
* **PDF Rendering and Storage**: Calls APITemplate.io to render the Markdown into a PDF using the assigned `Template ID`. The resulting PDF is uploaded to a specific folder in Google Drive (created dynamically per job if needed) and Microsoft OneDrive.
* **Database Update**: Finally, the document in the `n8n_resume_render_log` MongoDB collection is updated with the Drive links and marked as `successful`.

### 2. Batch Logger (MongoDB to Sheets) (`Batch Logger ( MongoDB to Sheets ).json`)
A utility workflow designed to manually export the processing results.
* **Data Retrieval**: Queries the `n8n_resume_render_log` MongoDB collection for processed records (currently filtered by cycle).
* **Google Sheets Export**: Iterates over the retrieved documents and appends them mapped exactly to the schema of the structured `Audit_study_application_data` Google Sheet. This enables quick audits and review of generated URLs and validation scores.

This is the final step in the resume parsing and generation pipeline. The next step is to submit the generated resumes to the respective job postings using an automated job application workflow.
