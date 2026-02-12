
import os
import sys
import json
from typing import Dict, Any, Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs.gemini_processor import GeminiProcessor
from utils import get_logger

logger = get_logger(__name__)

class GeminiClassifier:
    def __init__(self):
        self.processor = GeminiProcessor(
            model_name="gemini-2.5-flash",
            temperature=0.1,  # Low temperature for deterministic results
            enable_google_search=False
        )
        
    def validate_classification(self, email_content: str, current_classification: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and potentially correct the classification using Gemini.
        
        Args:
            email_content: The full text content of the email
            current_classification: The dictionary containing current category/subcategory
            
        Returns:
            Dictionary with keys: is_correct (bool), corrected_category, corrected_subcategory, reasoning
        """
        prompt = f"""
        You are an expert email classifier for a recruitment process.
        I will provide an email content and its current classification (category and subcategory).
        
        Your task is to VERIFY if the classification is correct.
        
        Focus specifically on:
        1. distinguishing "Interview Invitation" from "Rejection" or "Generic Update".
        2. distinguishing "Application Update" from "Application Submission" or "Other".
        
        Current Classification:
        Category: {current_classification.get('category')}
        Subcategory: {current_classification.get('subcategory')}
        
        Email Content:
        \"\"\"
        {email_content[:2000]}  # Truncate to avoid huge tokens, usually beginning is enough
        \"\"\"
        
        Valid Categories: application_update, application_submission, security_code, google_notification, other
        Valid Subcategories for application_update: interview_invitation, rejection, next_steps, status_update
        
        JSON Response format:
        {{
            "is_correct": boolean,
            "corrected_category": "string (or null if correct)",
            "corrected_subcategory": "string (or null if correct)",
            "reasoning": "string explaining why"
        }}
        
        Return ONLY valid JSON.
        """
        
        try:
            response = self.processor.generate_content(prompt=prompt)
            if response and response.text:
                # Clean code blocks if present
                text = response.text.strip()
                if text.startswith("```json"):
                    text = text[7:]
                if text.endswith("```"):
                    text = text[:-3]
                return json.loads(text.strip())
            return {"is_correct": True, "reasoning": "Gemini failed to generate response"}
            
        except Exception as e:
            logger.error(f"Gemini validation failed: {e}")
            return {"is_correct": True, "reasoning": f"Error: {str(e)}"}

# Singleton instance
_classifier = None

def validate_with_gemini(email: Dict[str, Any], classification: Dict[str, Any]) -> Dict[str, Any]:
    global _classifier
    if _classifier is None:
        _classifier = GeminiClassifier()
        
    # Prepare content
    subject = email.get("subject", "")
    body = (email.get("body_text", "") or email.get("body_html", "") or "")
    content = f"Subject: {subject}\n\nBody:\n{body}"
    
    return _classifier.validate_classification(content, classification)
