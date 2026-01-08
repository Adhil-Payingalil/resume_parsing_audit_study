import os
import win32com.client

INPUT_DIR = "Resume_inputs"
OUTPUT_DIR = "just pdf"

os.makedirs(OUTPUT_DIR, exist_ok=True)

word = win32com.client.Dispatch("Word.Application")
word.Visible = False

for filename in os.listdir(INPUT_DIR):
    if filename.lower().endswith(".docx"):
        pdf_filename = os.path.splitext(filename)[0] + ".pdf"
        pdf_path = os.path.abspath(os.path.join(OUTPUT_DIR, pdf_filename))
        # Only convert if PDF doesn't already exist
        if not os.path.exists(pdf_path):
            docx_path = os.path.abspath(os.path.join(INPUT_DIR, filename))
            try:
                doc = word.Documents.Open(docx_path)
                doc.SaveAs(pdf_path, FileFormat=17)  # 17 = wdFormatPDF
                doc.Close()
                print(f"Converted: {filename} -> {pdf_filename}")
            except Exception as e:
                print(f"Failed to convert {filename}: {e}")
        else:
            print(f"Skipped (already exists): {pdf_filename}")

word.Quit()