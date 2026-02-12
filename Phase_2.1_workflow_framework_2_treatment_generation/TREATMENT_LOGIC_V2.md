# V2 Treatment Framework Documentation

This document outlines the logic, data sources, and workflow for the **Phase 2.1 Update**, which transitions the resume study to a new treatment framework with stricter controls and updated inputs.

## 1. Overview
The goal is to update existing `Treated_resumes` (now in `V2_treated_resumes`) by removing old treatments and applying new ones based on **Access Education Credentials (AEC)**, **Canadian Education Credentials (CEC)**, and **Canadian Work Experience (CWE)**.

Unlike the previous randomized approach, this framework uses **strict date logic** and applies specific combinations of credentials to 4 distinct types.

## 2. Treatment Types & Logic

### Control Group
*   **Components**: AEC Only.
*   **Logic**:
    *   **Work Experience (0)**: Update End Date to **Jun 2025** (2025-06) to bridge gap to AEC.
    *   **AEC**: Start **(Blank)**, End **Dec 2025**.
    *   *Note*: Acts as a baseline with minimal Canadian intervention (AEC).

### Type I
*   **Components**: AEC + CEC.
*   **Logic**:
    *   **Work Experience (0)**: Update End Date to **Jun 2024** (2024-06).
    *   **CEC**: Start **Sep 2024**, End **Aug 2025**.
    *   **AEC**: Start **(Blank)**, End **Dec 2025**.
    *   *Sequence*: CEC completes just before AEC starts.

### Type II
*   **Components**: AEC + CWE.
*   **Logic**:
    *   **Work Experience (0)**: Update End Date to **Dec 2024** (2024-12).
    *   **AEC**: Start **(Blank)**, End **May 2025**.
    *   **CWE**: Start **Jun 2025**, End **Dec 2025**.
    *   *Sequence*: AEC completes, then Canadian Work Experience begins immediately.

### Type III
*   **Components**: AEC + CEC + CWE.
*   **Logic**:
    *   **Work Experience (0)**: Update End Date to **Nov 2023** (2023-11).
    *   **CEC**: Start **Jan 2024**, End **Dec 2024**.
    *   **AEC**: Start **(Blank)**, End **May 2025**.
    *   **CWE**: Start **Jun 2025**, End **Dec 2025**.
    *   *Sequence*: A longer timeline spanning 2 years (2024-2025).

## 3. Data Sources
*   **AEC Data**: `AEC_ACESS_education_credentials.csv` (Bridging/Connections programs).
*   **CEC Data**: *Pending new CSV* (Canadian College/University credentials).
*   **CWE Data**: `work_experience_credentials.csv` (Canadian work placements).

## 4. Workflows

### Phase 1: Cleanup
**Script**: `step1_cleanup_treatments.py`
*   **Objective**: Remove pre-existing treatment entries from the resumes to ensure a clean slate.
*   **Method**: Identifies Education/Work entries using metadata (or position-based 0-index logic with safety checks) and removes them.

### Phase 2: AEC Application
**Script**: `step2_apply_aec.py`
*   **Objective**: Apply the **AEC** credential to **ALL** document types (Control, I, II, III).
*   **Logic**:
    *   Reads `treatment_type` from the document.
    *   Selects the AEC credential (persisting the original one if metadata exists, or assigning a new one from CSV).
    *   Inserts into `education[0]` with the **strict dates** defined above.

### Phase 3: CEC Application (Pending)
**Script**: `step3_apply_cec.py`
*   **Objective**: Apply **CEC** to **Type I** and **Type III**.
*   **Status**: Blocked waiting for data.

### Phase 4: CWE Application (Pending)
**Script**: `step4_apply_cwe.py`
*   **Objective**: Apply **CWE** to **Type II** and **Type III**.
*   **Status**: Pending.

## 5. Directory Structure
All scripts and data for this migration are located in:
`Phase_2.1_workflow_framework_2_treatment_generation/`
