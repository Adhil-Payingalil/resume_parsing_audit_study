import os
import re
from datetime import datetime
import sys 

sys.path.append(".")
from utils import get_logger
from typing import Optional, List
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Testing
#from mongodb import get_all_file_ids, get_document_by_fileid, _get_mongo_client

# Set up logging

logger = get_logger(__name__)

class GeminiProcessor:
    """
    A class to handle interactions with the Google Gemini API.
    Provides methods for file processing, prompt management, and content generation.
    """
    
    def __init__(
        self,
        model_name: str = "gemini-1.5-flash",
        temperature: float = 0.4,
        api_key: Optional[str] = None,
        enable_google_search: bool = False,
    ):
        """
        Initialize the GeminiProcessor.

        Args:
            model_name (str): Name of the Gemini model to use
            temperature (float): Temperature setting for content generation
            api_key (Optional[str]): Gemini API key. If None, will try to load from environment
            enable_google_search (bool): Whether to enable the Google Search tool
            enable_think_tool (bool): Whether to enable the Think tool
        """
        self.model_name = model_name
        self.temperature = temperature
        self._setup_api_client(api_key)
        self.tools = self._setup_tools(enable_google_search)
        self.uploaded_resume_file = None
        self.prompt_template = None
        self.mongo_document = None
        self.file_name = None  # Ensure file_name is always defined
        
    def _setup_api_client(self, api_key: Optional[str]) -> None:
        """Set up the Gemini API client."""
        if api_key is None:
            load_dotenv()
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("No API key provided and GEMINI_API_KEY not found in environment")
        
        self.client = genai.Client(api_key=api_key)
    
    def _setup_tools(self, enable_google_search: bool) -> List[types.Tool]:
        """Set up the tools for the Gemini model."""
        tools = []
        if enable_google_search:
            tools.append(types.Tool(google_search=types.GoogleSearch()))
        # Add more tools here as they become available
        return tools
    
    def load_prompt_template(self, prompt_file_path: str) -> str:
        """
        Load a prompt template from a markdown file.
        
        Args:
            prompt_file_path (str): Path to the prompt template file
            
        Returns:
            str: The loaded prompt template
        """
        try:
            with open(prompt_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.prompt_template = content
            logger.info(f"Successfully loaded prompt template from {prompt_file_path}")
            return self.prompt_template
        except FileNotFoundError:
            logger.error(f"Prompt template file not found: {prompt_file_path}")
            return None
        except Exception as e:
            logger.error(f"Error loading prompt template: {e}")
            raise
    
    def upload_file(self, document_path: str) -> types.FileData:
        """
        Upload a file to be processed by Gemini.
        
        Args:
            file_path (str): Path to the file to upload
            
        Returns:
            types.FileData: The uploaded file object
        """
        if not os.path.exists(document_path):
            raise FileNotFoundError(f"File not found: {document_path}")


        try:
            self.file_name = os.path.splitext(os.path.basename(document_path))[0]
            self.uploaded_resume_file = self.client.files.upload(file=document_path)
            logger.info(f"Successfully uploaded file: {self.uploaded_resume_file.name}")
            return self.uploaded_resume_file
        except Exception as e:
            logger.error(f"Error uploading file {document_path}: {e}")
            raise

    
    def delete_uploaded_file(self) -> None:
        """Delete the currently uploaded file."""
        if self.uploaded_resume_file:
            try:
                self.client.files.delete(name=self.uploaded_resume_file.name)
                logger.info(f"Deleted uploaded file: {self.uploaded_resume_file.name}")
                self.uploaded_resume_file = None
            except Exception as e:
                logger.error(f"Error deleting uploaded file: {e}")
                raise

    
    def generate_content(self, prompt: Optional[str] = None) -> types.GenerateContentResponse:
        """
        Generate content using the Gemini model.
        
        Args:
            prompt (Optional[str]): Custom prompt to use. If None, uses loaded template
            
        Returns:
            types.GenerateContentResponse: The generated content
        """
            
        if prompt is None:
            if not self.prompt_template:
                raise ValueError("No prompt template loaded and no custom prompt provided")
            prompt = self.prompt_template

        contents = []
        if not self.uploaded_resume_file:
            logger.info("No file uploaded, using prompt only")
            contents.append(prompt)
        elif self.uploaded_resume_file:
            logger.info(f"Using uploaded file: {self.uploaded_resume_file.name}")
            contents.append(prompt)
            contents.append(self.uploaded_resume_file)
        elif self.mongo_document:
            logger.info("Using MongoDB document content")
            contents.append(prompt)
            contents.append(self.mongo_document)
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                    tools=self.tools,
                )
            )
            
            if response.text:
                logger.info("Content generation successful")
                return response
            else:
                raise ValueError("Gemini returned no text")
                
        except Exception as e:
            logger.error(f"Error during content generation: {e}")
            if hasattr(response, 'promptFeedback') and response.promptFeedback:
                logger.error(f"Prompt Feedback: {response.promptFeedback}")
                if hasattr(response, 'promptFeedback') and hasattr(response.promptFeedback, 'blockReason') and response.promptFeedback.blockReason:
                    logger.error(f"Block Reason: {response.promptFeedback.blockReason}")
    
    def save_generated_content(self, response: types.GenerateContentResponse, output_dir: str = "text_output") -> None:
        """
        Save the generated content to a file.
        
        Args:
            response (types.GenerateContentResponse): The response from the Gemini API
            output_dir (str): Path to save the generated content
            
        Returns:
            None
        """
        if response.text:
            logger.info("Content generation successful.")
            # Save raw response to file for debugging
            try:
                os.makedirs("text_output", exist_ok=True)
                timestamp_str = datetime.now().strftime("%d-%m-%y_%H-%M")
                if self.uploaded_resume_file and self.file_name:
                    base_name = os.path.splitext(os.path.basename(self.file_name))[0]
                else: 
                    base_name = "MongoDB_document"
                output_filename = f"{base_name}_{timestamp_str}.txt"
                output_path = os.path.join(output_dir, output_filename)
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(response.text)
            except Exception as e_write:
                logger.error(f"Error writing raw response to file: {e_write}")
            return response
        else:
            logger.error("Gemini returned no text.")
            return None
    
    def process_file(self, file_path: str, prompt_template_path: str) -> types.GenerateContentResponse:
        """
        Process a file using a prompt template. This is a convenience method that combines
        loading the template, uploading the file, and generating content.
        
        Args:
            file_path (str): Path to the file to process
            prompt_template_path (str): Path to the prompt template file
            
        Returns:
            types.GenerateContentResponse: The generated content
        """
        try:
            self.load_prompt_template(prompt_template_path)
            self.upload_file(file_path)
            output_dir = os.path.join("data","text_output")
            response = self.generate_content()
            self.save_generated_content(output_dir=output_dir, response=response)
            return response
        except Exception as e:
            logger.error(f"Error processing file: {e}")
            raise ValueError(f"Failed to process file {file_path}: {e}")
        finally:
            if self.uploaded_resume_file:
                self.delete_uploaded_file()


if __name__ == "__main__":
    # Example usage for mongoDB processing
    """
    Gemini = GeminiProcessor(
        model_name="gemini-1.5-flash",
        temperature=0.4,
        enable_google_search= False)
    Gemini.load_prompt_template("Prompt_templates\prompt_engineering_EDAvalidation.md")
    mongo_client = _get_mongo_client()
    all_files = get_all_file_ids(db_name="Resume_study", 
                                 collection_name="ITC_EDA", 
                                 mongo_client=mongo_client)
    test_file = get_document_by_fileid(db_name="Resume_study", 
                                       collection_name="ITC_EDA", 
                                       file_id=all_files[0], 
                                       mongo_client=mongo_client)
    Gemini.mongo_document = test_file
    response = Gemini.generate_content()
    Gemini.save_generated_content(response)
    """
    Gemini = GeminiProcessor(
        model_name="gemini-1.5-flash",
        temperature=0.4,
        enable_google_search= False)
    prompt = Gemini.load_prompt_template("Prompt_templates/prompt_engineering_eda.md")
    print(prompt)