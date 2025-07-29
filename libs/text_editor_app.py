import sys
import os
import time
import random
from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout, 
                               QTextEdit, QPushButton, QDialogButtonBox)

# --- New PySide6 Dialog Class ---

class TextEditorDialog(QDialog):
    """
    A PySide6 dialog window that allows editing text and provides
    'Retry' and 'Accept' options.
    """
    def __init__(self, initial_text):
        super().__init__()
        self.setWindowTitle("Validate and Edit Response")
        self.resize(800, 600)

        # Layout
        self.layout = QVBoxLayout(self)

        # Text Area
        self.text_area = QTextEdit()
        self.text_area.setPlainText(initial_text)
        self.layout.addWidget(self.text_area)

        # Buttons (Retry and Accept)
        button_box = QDialogButtonBox()
        self.accept_button = button_box.addButton("Accept and Continue", QDialogButtonBox.ButtonRole.AcceptRole)
        self.retry_button = button_box.addButton("Retry Generation", QDialogButtonBox.ButtonRole.RejectRole)
        self.layout.addWidget(button_box)

        # Connect button clicks to the dialog's built-in slots
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def get_text(self):
        """Returns the current text from the text area."""
        return self.text_area.toPlainText()

    def run(self):
        result = self.exec()

        if result == QDialog.Accepted:
            return "accepted", self.get_text()
        elif result == QDialog.Rejected:
            return "retry", None
        else:
            return "cancelled", None

# --- Mock LLM and Data (for a runnable example) ---
class MockLLM:
    def generate_content(self, prompt):
        print("\n[LLM_INFO] Generating content...")
        time.sleep(1) # Simulate API call delay
        response_text = f"""[
    {{ "Original_company": "Vosyn", "Similar_companies": ["TechSys", "Innovate Inc.", "DataCorp"] }},
    {{ "Original_company": "upskillable", "Similar_companies": ["LearnWell", "EduPro", "Skillify"] }}
    // Random number to show it's a new generation: {random.randint(100, 999)}
]"""
        return response_text

def _extract_company_name_list(source_resume_data):
    return ["Vosyn", "upskillable"]

def _clean_raw_llm_response(text):
    return text.strip()

# --- Your Main Function, Now Using PySide6 ---
def company_research_with_ui(source_resume_data, company_research_model, company_research_prompt):
    """
    Performs company research, then opens a UI for validation and editing.
    Allows the user to retry the generation or accept the result.
    """
    # This is required for any PySide/Qt application
    app = QApplication.instance() or QApplication(sys.argv)
    
    company_name_list = _extract_company_name_list(source_resume_data=source_resume_data)
    final_prompt = company_research_prompt.replace('{company_names}', str(company_name_list))

    while True:
        print("\n--- Preparing to generate content ---")
        raw_response = company_research_model.generate_content(prompt=final_prompt)
        llm_response = _clean_raw_llm_response(raw_response)
        
        print("[INFO] Content generated. Opening editor for validation...")

        dialog = TextEditorDialog(initial_text=llm_response)
        
        # .exec() shows the dialog and blocks until the user clicks a button
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            print("\n[SUCCESS] Content accepted by user.")
            final_text = dialog.get_text()
            return final_text
        else: # User clicked "Retry" or closed the window
            print("\n[ACTION] User chose to retry or cancelled. Regenerating...")
            continue

# --- How to Use It ---
if __name__ == "__main__":
    mock_resume_data = {"work_experience": [{"company": "Vosyn"}, {"company": "upskillable"}]}
    mock_prompt_template = "Find similar companies for: {company_names}"
    mock_model = MockLLM()

    final_company_data = company_research_with_ui(
        source_resume_data=mock_resume_data,
        company_research_model=mock_model,
        company_research_prompt=mock_prompt_template
    )

    if final_company_data:
        print("\n--- Final Processed Data ---")
        print(final_company_data)
    else:
        print("\n--- No data was returned. ---")