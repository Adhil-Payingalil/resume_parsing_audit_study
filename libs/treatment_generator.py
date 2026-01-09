"""
Treatment Generator Module
==========================

This module contains the core logic for Phase 2: Resume Treatment Generation.
It handles:
1.  Loading Treatment Data (CEC/CWE) from CSVs.
2.  Interfacing with Gemini for styling and content generation.
3.  Calculating similarity scores.
4.  Applying treatments to resume data.

It is designed to be "Headless" (no UI), expecting any manual inputs (like company research) 
to be passed in as arguments.
"""

import os
import sys
import time
import copy
import json
import random
import pandas as pd
import datetime
from typing import Dict, List, Optional, Any, Union
from sklearn.metrics.pairwise import cosine_similarity

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from libs.gemini_processor import GeminiProcessor
from libs.mongodb import _get_mongo_client, get_all_file_ids, get_document_by_fileid, _clean_raw_llm_response
from utils import get_logger

logger = get_logger(__name__)

# Constants
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
PHASE_2_DIR = os.path.join(PROJECT_ROOT, "Phase 2 Workflow")

# Configuration Defaults (can be overridden)
DEFAULTS = {
    "REFINER_MODEL": "gemini-2.5-pro",
    "RESEARCH_MODEL": "gemini-2.5-pro",
    "TREATMENT_MODEL": "gemini-2.5-pro",
    "TEMPERATURE": 0.6,
    "FOCUSED_SIMILARITY_THRESHOLD": 0.60,
    "API_INITIAL_RETRY_DELAY": 5.0,
    "API_MAX_RETRY_DELAY": 120.0,
}

STYLE_MODIFIERS = [
    "using strong, action-oriented verbs and focusing on quantifiable outcomes",
    "using a direct, concise, and professional tone, prioritizing clarity and brevity",
    "by emphasizing collaborative efforts and cross-functional teamwork",
    "by describing the technical aspects of the work with more precision and detail",
    "by framing the accomplishments as a narrative of challenges, actions, and results"
]

class TreatmentGenerator:
    """
    Core logic for generation of treated resumes.

    This class orchestrates the interaction between the local data files (CSVs),
    the Google Gemini API (for text rephrasing and generation), and the local 
    SentenceTransformer model (for semantic similarity validation).

    Attributes:
        sector (str): The industry sector code (e.g., 'ITC').
        data_dir (str): Path to the directory containing 'models', 'education_credentials.csv', etc.
                        If None, tries to find 'Phase 2 Workflow' relative to project root.
    """
    
    def __init__(self, sector: str, data_dir: str = None):
        """
        Initialize the Treatment Generator.

        Args:
            sector (str): The target sector (e.g., "ITC").
            data_dir (str, optional): The absolute path to the directory containing 
                                      the 'models' folder and treatment CSVs.
                                      If not provided, defaults to finding 'Phase 2 Workflow'.
        """
        self.sector = sector.upper().strip()
        self.mongo_client = _get_mongo_client()
        self.db = self.mongo_client["Resume_study"]
        
        # Determine Data Directory (Dynamic to support folder renaming)
        if data_dir:
            self.data_dir = data_dir
        else:
            # Fallback for manual/legacy usage
            self.data_dir = os.path.join(PROJECT_ROOT, "Phase 2 Workflow")
            
        logger.info(f"Initialized TreatmentGenerator for sector {self.sector} using resources in: {self.data_dir}")
        
        # Treatment Dataframes
        self.cec_df = None
        self.cwe_df = None
        
        # Models (Lazy loaded)
        self.similarity_model = None
        self.control_refiner_model = None
        self.treatment_model = None
        self.company_research_model = None
        
        # Prompts (Loaded on init)
        self._load_prompts()
        self._load_csv_data()

    def _load_prompts(self):
        """Initialize Gemini models and load prompts."""
        prompts_dir = os.path.join(self.data_dir, "Prompts")
        
        # 1. Control Refiner
        self.control_refiner_model = GeminiProcessor(
            model_name=DEFAULTS["REFINER_MODEL"],
            temperature=DEFAULTS["TEMPERATURE"],
            enable_google_search=False
        )
        self.control_refiner_prompt = self.control_refiner_model.load_prompt_template(
            os.path.join(prompts_dir, "prompt_control_refiner.md")
        )
        
        # 2. Treatment Generator
        self.treatment_model = GeminiProcessor(
            model_name=DEFAULTS["TREATMENT_MODEL"],
            temperature=DEFAULTS["TEMPERATURE"],
            enable_google_search=False
        )
        self.treatment_prompt = self.treatment_model.load_prompt_template(
            os.path.join(prompts_dir, "prompt_treatment_generation.md")
        )
        
        # 3. Company Research (For manual UI usage mostly, but available here)
        self.company_research_model = GeminiProcessor(
            model_name=DEFAULTS["RESEARCH_MODEL"],
            temperature=DEFAULTS["TEMPERATURE"],
            enable_google_search=True
        )
        self.company_research_prompt = self.company_research_model.load_prompt_template(
            os.path.join(prompts_dir, "prompt_similar_company_generation.md")
        )
        
    def _load_csv_data(self):
        """Load and filter CEC/CWE CSV files."""
        try:
            cec_path = os.path.join(self.data_dir, "education_credentials.csv")
            cwe_path = os.path.join(self.data_dir, "work_experience_credentials.csv")
            
            cec_df = pd.read_csv(cec_path)
            cwe_df = pd.read_csv(cwe_path)
            
            # Filter by sector
            self.cec_df = cec_df[cec_df['sector'] == self.sector].reset_index(drop=True)
            self.cwe_df = cwe_df[cwe_df['sector'] == self.sector].reset_index(drop=True)
            
            logger.info(f"Loaded {len(self.cec_df)} CEC and {len(self.cwe_df)} CWE treatments for {self.sector}")
            
        except Exception as e:
            logger.error(f"Failed to load treatment CSVs: {e}")
            raise

    def get_similarity_model(self):
        """
        Lazy loads the SentenceTransformer model for semantic similarity.

        Logic:
        1. Checks for a local model in `{data_dir}/models/all-MiniLM-L6-v2`.
        2. If found, loads from disk (fast, offline, consistent).
        3. If not found, downloads from HuggingFace (internet required) 
           but does NOT save it locally to the models folder automatically 
           (unless HuggingFace cache is configured).

        Returns:
            SentenceTransformer: The loaded model.
        """
        if self.similarity_model is None:
            logger.info("Loading SentenceTransformer model...")
            from sentence_transformers import SentenceTransformer
            
            # Check for local model
            local_model_path = os.path.join(self.data_dir, "models", "all-MiniLM-L6-v2")
            
            if os.path.exists(local_model_path):
                logger.info(f"Found local model at: {local_model_path}")
                self.similarity_model = SentenceTransformer(local_model_path)
            else:
                logger.warning(f"Local model not found at {local_model_path}. Downloading from HuggingFace...")
                self.similarity_model = SentenceTransformer("all-MiniLM-L6-v2")
                
        return self.similarity_model

    # ------------------------------------------------------------------------
    # Helper Logic
    # ------------------------------------------------------------------------
    def extract_company_and_position_list(self, resume_data: dict) -> dict:
        """Extracts work experience for company research."""
        # Handle nesting
        resume = resume_data
        if 'resume_data' in resume and isinstance(resume['resume_data'], dict):
            resume = resume['resume_data']
            if 'resume_data' in resume and isinstance(resume['resume_data'], dict):
                resume = resume['resume_data']
        
        work_history = resume.get('work_experience', [])
        entries = []
        for job in work_history:
            if job.get('company') or job.get('position'):
                entries.append({
                    'company': job.get('company'),
                    'position': job.get('position'),
                    'location': job.get('location')
                })
        return {'work_experience_entries': entries}

    def research_companies_headless(self, resume_data: dict) -> list:
        """Generate company mappings WITHOUT UI (Pure Gemini)."""
        work_data = self.extract_company_and_position_list(resume_data)
        prompt = self.company_research_prompt.replace('{company_names}', str(work_data))
        
        try:
            response = self.company_research_model.generate_content(
                prompt=prompt,
                max_retries=3
            )
            return _clean_raw_llm_response(response.text)
        except Exception as e:
            logger.error(f"Company research failed: {e}")
            return []

    def remove_north_american_elements(self, source_resume_data: dict) -> dict:
        """Removes NA elements using Gemini."""
        prompt = self.control_refiner_prompt.replace('{JSON_resume_object}', str(source_resume_data))
        try:
            response = self.control_refiner_model.generate_content(
                prompt=prompt, max_retries=3
            )
            return _clean_raw_llm_response(response.text)
        except Exception as e:
            logger.error(f"Control refiner failed: {e}")
            raise

    def replace_companies_and_positions(self, resume_data: dict, mappings: list, treatment_type: str) -> dict:
        """Applies the company/position replacement logic."""
        if not mappings: return resume_data
        
        # Build Lookup
        lookup = {}
        for entry in mappings:
            orig = entry.get("Original_company")
            if not orig: continue
            
            # Find replacement for this type
            replacement = None
            for var in entry.get("Variations", []):
                if treatment_type in var:
                    replacement = var[treatment_type]
                    break
            
            if replacement:
                lookup[orig.lower()] = replacement

        # Apply
        new_data = copy.deepcopy(resume_data)
        for exp in new_data.get("resume_data", {}).get("work_experience", []):
            orig_comp = exp.get("company", "").lower()
            if orig_comp in lookup:
                rep = lookup[orig_comp]
                if rep.get('company'): exp["company"] = rep['company']
                if rep.get('position'): exp["position"] = rep['position']
        
        return new_data

    def prepare_treatment_prompts(self, source_resume_data: dict):
        """Selects random treatments and prepares prompts for Type I, II, III."""
        if self.cec_df.empty or self.cwe_df.empty:
            logger.error("No treatments available.")
            return None

        # 1. Sample Treatments
        try:
            cec_sample = self.cec_df.sample(n=2, replace=False).to_dict('records')
            cwe_sample = self.cwe_df.sample(n=2, replace=False).to_dict('records')
            self._clean_cwe_sample(cwe_sample) # Helper to clean keys
        except ValueError:
            return None

        # 2. Sample Styles
        if len(STYLE_MODIFIERS) < 3: return None
        styles = random.sample(STYLE_MODIFIERS, 3)

        # 3. Build Prompts
        prompts = {}
        base_prompt = self.treatment_prompt.replace("{JSON_resume_object}", str(source_resume_data))

        # Type I (CEC)
        cec = cec_sample[0]
        prompts["Type_I"] = {
            "prompt": self._fill_prompt(base_prompt, cec, "Type_I", styles[0]),
            "treatment_applied": {"Canadian_Education": cec}
        }

        # Type II (CWE)
        cwe = cwe_sample[0]
        prompts["Type_II"] = {
            "prompt": self._fill_prompt(base_prompt, cwe, "Type_II", styles[1]),
            "treatment_applied": {"Canadian_Work_Experience": cwe}
        }

        # Type III (Mixed) - Use the *other* samples
        mixed = {
            "task": "ADD_EDUCATION_AND_EXPERIENCE",
            "payload": {"education": cec_sample[1], "experience": cwe_sample[1]}
        }
        prompts["Type_III"] = {
            "prompt": self._fill_prompt(base_prompt, mixed, "Type_III", styles[2]),
            "treatment_applied": {"Canadian_Education": cec_sample[1], "Canadian_Work_Experience": cwe_sample[1]}
        }
        return prompts

    def _fill_prompt(self, base, obj, type_str, style):
        p = base.replace("{Treatment_object}", str(obj))
        p = p.replace("{treatment_type}", type_str)
        p = p.replace("{style_guide}", style)
        return p

    def _clean_cwe_sample(self, cwe_list):
        """Cleans CWE CSV keys to match JSON expectations."""
        for t in cwe_list:
            if 'Position' in t: t['position'] = t.pop('Position')
            if 'Name of Organization Providing Project' in t: t['company'] = t.pop('Name of Organization Providing Project')
            if 'Title of Experiential Learning Project' in t: t.pop('Title of Experiential Learning Project')
            if 'Duration' in t: t['duration'] = t.pop('Duration')
            if 'Location ' in t: t['location'] = t.pop('Location ')
            # Merge highlights
            hl = []
            for i in range(1, 4):
                k = f'highlight_{i}'
                if k in t: hl.append(t.pop(k))
            t['highlights'] = hl

    def calculate_similarity(self, control_data, treated_data, treatment_type=None):
        """Calculates focused cosine similarity."""
        try:
            # Logic to skip first job for Type II/III
            skip = treatment_type in ["Type_II", "Type_III"]
            
            def extract_text(d, s=False):
                parts = []
                try:
                    # Safely access resume_data key if it exists
                    # Logic: If d has 'resume_data', use it. Else assume d IS the data.
                    data = d.get('resume_data', d) if isinstance(d, dict) else {}
                    
                    if 'basics' in data and 'summary' in data['basics']: 
                        parts.append(data['basics']['summary'])
                        
                    if 'work_experience' in data:
                        start = 1 if s else 0
                        for job in data['work_experience'][start:]:
                             if 'highlights' in job and isinstance(job['highlights'], list):
                                 parts.extend(job['highlights'])
                             elif 'highlights' in job and isinstance(job['highlights'], str):
                                 parts.append(job['highlights'])
                except Exception as e:
                     logger.error(f"Text extraction warning: {e}")
                return " ".join(parts)

            t1 = extract_text(control_data, False)
            t2 = extract_text(treated_data, skip)
            
            if not t1 or not t2:
                logger.warning("  -> Skipping similarity (empty text)")
                return 0.0
            
            model = self.get_similarity_model()
            emb1 = model.encode(t1)
            emb2 = model.encode(t2)
            score = cosine_similarity([emb1], [emb2])[0][0]
            return score
        except Exception as e:
            logger.error(f"Similarity calc failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return 0.0

    def generate_treatment(self, prompt: str):
        """Calls Gemini to generate the treated resume."""
        try:
            resp = self.treatment_model.generate_content(prompt, max_retries=3)
            return _clean_raw_llm_response(resp.text)
        except Exception:
            return None
