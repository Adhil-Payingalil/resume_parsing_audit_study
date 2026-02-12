# Phase 2.1: Workflow Framework 2 - Treatment Generation

This directory contains the scripts and data required to generate the **V2 Treatment Framework** for the resume parsing audit study. The workflow systematically applies specific credentials and work experiences to resumes based on their assigned treatment type (Control, Type I, Type II, Type III).

For a deep dive into the specific logic, date rules, and treatment definitions, please refer to [TREATMENT_LOGIC_V2.md](TREATMENT_LOGIC_V2.md).

## Overview

The goal of this phase is to transition from a randomized treatment application to a deterministic, structured framework. This ensures that:
- **Control Group**: Receives only Access Education Credentials (AEC).
- **Type I**: Receives AEC + Canadian Education Credentials (CEC).
- **Type II**: Receives AEC + Canadian Work Experience (CWE).
- **Type III**: Receives AEC + CEC + CWE.

All treatments are applied with strict date ranges to ensure logical consistency and timelines (e.g., AEC happens before CWE).

## Workflow Steps

The generation process is divided into 4 sequential steps. It is recommended to run them in order.

### Step 1: Cleanup
**Script:** `step1_cleanup_treatments.py`

*   **Purpose:** Removes any pre-existing treatment entries (AEC, CEC, CWE) from the resumes. This ensures a clean slate before applying the new V2 logic.
*   **Action:** Scans `education` and `work_experience` arrays for entries matching treatment keywords (e.g., "ACCES Employment", "Certificate") or specific positions (Control/Type I usually have AEC at index 0) and removes them.
*   **Usage:**
    ```bash
    python step1_cleanup_treatments.py [--dry-run]
    ```

### Step 2: Apply AEC (Access Education Credentials)
**Script:** `step2_apply_aec.py`

*   **Purpose:** Applies the foundational AEC credential to **ALL** document types.
*   **Action:**
    *   Inserts AEC into `education[0]`.
    *   **Crucially**, updates the `endDate` of the most recent *original* work experience (at `work_experience[0]`) to bridge the gap to the new treatment timeline.
    *   Dates are strictly defined based on the treatment type (e.g., Control end date is Jun 2025, Type I end date is Jun 2024).
*   **Usage:**
    ```bash
    python step2_apply_aec.py [--dry-run]
    ```

### Step 3: Apply CEC (Canadian Education Credentials)
**Script:** `step3_apply_cec.py`

*   **Purpose:** Applies Canadian College/University credentials.
*   **Target:** **Type I** and **Type III** only.
*   **Action:**
    *   Inserts CEC into `education[1]` (after AEC).
    *   Uses data from `CEC_ontario_college_graduate_certificates.csv`.
*   **Usage:**
    ```bash
    python step3_apply_cec.py [--dry-run]
    ```

### Step 4: Apply CWE (Canadian Work Experience)
**Script:** `step4_apply_cwe.py`

*   **Purpose:** Applies Canadian Work Experience placements.
*   **Target:** **Type II** and **Type III** only.
*   **Action:**
    *   Inserts CWE into `work_experience[0]`.
    *   Uses data from `CWE_work_experience_credentials.csv`.
*   **Usage:**
    ```bash
    python step4_apply_cwe.py [--dry-run]
    ```

## Data Sources

The scripts rely on the following CSV files located in this directory:

*   **`AEC_ACESS_education_credentials.csv`**: Contains data for Access Education Credentials (bridging programs).
*   **`CEC_ontario_college_graduate_certificates.csv`**: Contains data for Ontario College Graduate Certificates.
*   **`CWE_work_experience_credentials.csv`**: Contains data for Canadian Work Experience placements, including specific highlights and roles.
*   **`audit_dates.csv`**: (Optional) Used for auditing the final date ranges applied to resumes.

## Usage Notes

*   **Dry Run**: All scripts support a `--dry-run` flag. It is highly recommended to run with this flag first to view the proposed changes in the logs without modifying the database.
*   **Logging**: Logs are generated for each step, detailing exactly which document was modified and what was added/removed.
*   **Idempotency**: The scripts are designed to be idempotent where possible, checking if a treatment already exists before adding it again, but running `step1_cleanup_treatments.py` is the safest way to restart.
