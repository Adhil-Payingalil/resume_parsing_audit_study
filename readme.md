# Resume Parsing Audit Study Pipeline

This repository hosts an end-to-end pipeline for a Resume Parsing Audit Study. The system is designed to automate the process of data extraction, treatment generation, job matching, and response tracking for correspondence studies on immigrant employment.

## Project Overview

The study aims to assess bias in resume parsing systems. This pipeline automates the generation of resume variations, parsing of these resumes, matching them with relevant job postings, and tracking the responses.

## Tech Stack

The project utilizes a robust set of tools and APIs to handle various stages of the pipeline:

-   **Google Gemini API**: Utilized for advanced natural language processing tasks, including resume parsing, data extraction, and content generation.
-   **MongoDB**: Serves as the central database for storing resume data, job postings, and experiment results.
-   **n8n**: Orchestrates complex workflows, particularly in the PDF generation and file handling phases (Phase 4).
-   **AgentQL & Playwright**: Power the job scraping capabilities (Phase 3), enabling robust data collection from dynamic web pages.
-   **Jina AI**: Integrated API for enhanced search and retrieval capabilities.
-   **PySide6**: Used for building local UI components for manual review and configuration steps.
-   **APItemplate.io**: Integrated within n8n for standardized resume formatting and PDF generation.
-   **Python**: The core logic is implemented in Python, leveraging a class-based architecture.

## Project Structure

The project is organized into distinct phases, each handling a specific part of the audit workflow. Detailed documentation for each phase can be found within its respective directory.

### [Phase 1: Data Extraction](phase_1_workflow_data_extraction)
*Directory: `phase_1_workflow_data_extraction`*
Focuses on ingesting raw resume data (PDF/Docx) and extracting structured information using the Gemini API. This phase establishes the baseline data for the study.

### [Phase 2: Treatment Generation](phase_2_workflow_treatment_generation)
*Directory: `phase_2_workflow_treatment_generation` and `Phase_2.1_workflow_framework_2_treatment_generation`*
Handles the creation of resume treatments (variations). This involves applying specific modifications to the base resumes (e.g., changing names, education) to test for bias.
-   **Phase 2.1** introduces updated workflows for more granular control over changing treatment logic as part of a second framework.

### [Phase 3: Job Matching](phase_3_workflow_job_matching)
*Directory: `phase_3_workflow_job_matching`*
Responsible for scraping job postings (using JINA AI/AgentQL/Playwright) and matching them with the generated resume treatments using vector search. This phase ensures that resumes are sent to relevant job openings.

### [Phase 4: PDF Generation](phase_4_workflow_PDF_generation)
*Directory: `phase_4_workflow_PDF_generation`*
Converts the structured resume data (JSON) into high-quality PDF documents suitable for application. This phase heavily utilizes **n8n** for workflow automation and **APItemplate.io** for PDF generation.

### [Phase 5: Gmail Response Tracking](phase_5_workflow_gmail_response_tracking)
*Directory: `phase_5_workflow_gmail_response_tracking`*
Tracks and analyzes employer responses to submitted applications.
-   **Gmail Scraper**: Fetches emails from study accounts using IMAP.
-   **Email Classifier**: Categorizes emails into "Application Updates" (Interviews, Rejections) vs. other types using keyword matching and LLM validation.

## Setup & usage

*(Note: Detailed verification of setup instructions is in progress. Please refer to the specific phase folders for granular setup steps.)*

1.  **Environment Setup**: Ensure you have Python installed and set up a virtual environment. Install dependencies from `requirements.txt`.
2.  **API Keys**: Configure your `.env` file with necessary API keys (Gemini, MongoDB, AgentQL, Jina AI, etc.).
3.  **Dependencies**: Install Node.js if required for specific n8n nodes or local testing.

---
*For detailed setup and specific tool usage, please refer to the README.md files within each phase directory.*