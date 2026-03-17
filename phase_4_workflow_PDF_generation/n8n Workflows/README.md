# Phase 4: n8n Workflows for PDF Generation & Logging

This directory contains the n8n workflows responsible for the core text processing, agentic tailoring, PDF generation, and data logging for Phase 4 of the audit study.

## Workflows Overview

There are two primary workflows included in this phase:

1. **V4 Combined PDF Generation Workflow**
2. **Batch Logger (MongoDB to Sheets)**

---

### 1. V4 Combined PDF Generation Workflow
(`V4 Combined PDF Generation Workflow.json`)

This is the primary automated pipeline triggered via a webhook. It takes a raw resume and a target job description, optimizes the resume for ATS and human readability, formats it into Markdown, generates a PDF, and logs the process.

**Key Steps & Components:**
- **Trigger & Initialization:** Triggered via Webhook. Immediately returns an `accepted` response to the caller so the heavy processing can happen asynchronously.
- **Data Retrieval:** Queries the `V2_treated_resumes` MongoDB collection for style guides and base resume information.
- **LLM Processing (Google Gemini 2.5):**
  - **Keyword Extractor:** Extracts ATS-relevant keywords and buckets them (e.g., planning, measurement, collaboration) from the target Job Description (JD).
  - **Doc Tailoring Agent:** Tailors the base JSON resume to the JD, integrating the extracted keywords naturally while adhering to strict rules regarding identity integrity and treatment types (`control`, `Type_I`, `Type_II`, `Type_III`).
  - **Resume Validation:** Runs a rigorous QA check on the tailored resume to provide a `quality_score`, checking for placeholders, AI filler, and JD alignment.
- **Markdown Formatting:** Based on the `markdown_template` variable specified (1 or 2), an AI agent structures the validated resume data into a polished Markdown document.
- **PDF Generation & Storage:** 
  - Sanitizes the intended filename.
  - Connects to Google Drive to check for existing applicant folders, creating them if necessary.
  - Passes the formatted Markdown to **APITemplate.io** to render the final PDF document.
  - Uploads the newly constructed PDF to the specified Google Drive folder.
- **Database Logging:** Initializes a log entry in the `n8n_resume_render_log` MongoDB collection during the run, and eventually updates the record with the final generated PDF Google Drive and Download links.

---

### 2. Batch Logger (MongoDB to Sheets)
(`Batch Logger ( MongoDB to Sheets ).json`)

This is a supplementary administrative workflow used to export generated workflow data out of MongoDB into a format accessible to researchers.

**Key Steps & Components:**
- **Manual Trigger:** This workflow is executed manually.
- **Database Query:** Searches the `n8n_resume_render_log` MongoDB collection for given cycle criteria (e.g., specific application cycles, such as cycle 14).
- **Google Sheets Export:** Takes the resulting documents (which include the resume text, matching metadata, treatment type, validation scores, and drive links) and safely appends them as individual rows to a configured Google Sheet (`Audit_study_application_data`).

## Prerequisites & Credentials

To successfully import and run these workflows in your own n8n instance, you must configure the following node credentials within the n8n environment:
- **MongoDB** (for document retrieval and logging updates)
- **Google Gemini (PaLM) API** (for LLM tailoring, extraction, and validation)
- **APITemplate.io** (for Markdown-to-PDF Rendering)
- **Google Drive & Google Sheets OAuth2 APIs** (for document storage and logging output)
- **Microsoft OneDrive** (optional, depending on specific storage configurations in the workflow)
