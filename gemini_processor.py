"""
This module defines the GeminiProcessor class for interacting with the Google Gemini API.
Responsibilities:
- Load prompt templates from markdown files.
- Upload PDF resumes to Gemini.
- Generate and save structured content via prompts.
- Handle logging and cleanup.

"""
import os
import re
from datetime import datetime
from utils import get_logger
from typing import Optional, List
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Set up logging

logger = get_logger(__name__)

class GeminiProcessor:
    """
    ## GeminiProcessor

    Handles all interactions with the Google Gemini API for resume parsing.

    ### Responsibilities
    - Loads prompt templates (from markdown files) for structured extraction.
    - Uploads resumes as files to Gemini.
    - Sends prompts and receives structured LLM output.
    - Handles file cleanup and logging.
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
        
    def _setup_api_client(self, api_key: Optional[str]) -> None:
        """Set up the Gemini API client."""
        if api_key is None:
            load_dotenv()
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("No API key provided and GEMINI_API_KEY not found in environment")
        
        self.client = genai.Client(api_key=api_key)
    
    def _setup_tools(self, enable_google_search: bool) -> List[types.Tool]:
        """
        Set up tools for the Gemini API.

        Args:
            enable_google_search (bool): Whether to enable Google Search.

        Returns:
            List[types.Tool]: List of enabled tools.
        """
        tools = []
        if enable_google_search:
            tools.append(types.Tool(google_search=types.GoogleSearch()))
        # Add more tools here as they become available
        return tools
    
    def load_prompt_template(self, prompt_file_path: str) -> str:
        """
        Load a prompt template from a markdown file (between triple backticks).

        Args:
            prompt_file_path (str): Path to the prompt template file.

        Returns:
            str: The loaded prompt template.

        Raises:
            FileNotFoundError: If the file is missing.
            ValueError: If no triple-backtick block is found.
        """
        try:
            with open(prompt_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract the prompt template between triple backticks
            prompt_match = re.search(r'```\n(.*?)\n```', content, re.DOTALL)
            if prompt_match:
                self.prompt_template = prompt_match.group(1) # Strip leading/trailing whitespace and backticks
                logger.info(f"Successfully loaded prompt template from {prompt_file_path}")
                return self.prompt_template
            else:
                raise ValueError(f"Could not find prompt template (between ```) in {prompt_file_path}")
        except FileNotFoundError:
            logger.error(f"Prompt template file not found: {prompt_file_path}")
            return None
        except Exception as e:
            logger.error(f"Error loading prompt template: {e}")
            raise
    
    def upload_file(self, document_path: str) -> types.FileData:
        """
        Upload a file (PDF resume) to Gemini.

        Args:
            document_path (str): Path to the file.

        Returns:
            types.FileData: The uploaded file object.

        Raises:
            FileNotFoundError: If the file does not exist.
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
        """
        Delete the uploaded file from Gemini (cleanup after processing).
        """
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
        Generate content using Gemini (prompt + uploaded file).

        Args:
            prompt (Optional[str]): Custom prompt to use (default: loaded template).

        Returns:
            types.GenerateContentResponse: The LLM's response.

        Raises:
            ValueError: If no prompt or file is available.
        """
        if not self.uploaded_resume_file:
            raise ValueError("No file has been uploaded")
            
        if prompt is None:
            if not self.prompt_template:
                raise ValueError("No prompt template loaded and no custom prompt provided")
            prompt = self.prompt_template
            
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt, self.uploaded_resume_file],
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                    tools=self.tools
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
        finally:
            # Cleanup uploaded file
            self.delete_uploaded_file()
    
    def save_generated_content(self, response: types.GenerateContentResponse, output_path: str) -> None:
        """
        Save the generated content to a file.
        
        Args:
            response (types.GenerateContentResponse): The response from the Gemini API
            output_path (str): Path to save the generated content
            
        Returns:
            None
        """
        if response.text:
            logger.info("Content generation successful.")
            # Save raw response to file for debugging
            try:
                os.makedirs("text_output", exist_ok=True)
                timestamp_str = datetime.now().strftime("%d-%m-%y_%H-%M")
                base_name = os.path.splitext(os.path.basename(self.file_name))[0]
                output_filename = f"{base_name}_{timestamp_str}.txt"
                output_path = os.path.join("text_output", output_filename)
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
            output_file_path = os.path.join("text_output", f"{self.file_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            response = self.generate_content()
            self.save_generated_content(output_path=output_file_path, response=response)
            return response
        except Exception as e:
            logger.error(f"Error processing file: {e}")
            raise ValueError(f"Failed to process file {file_path}: {e}")
        finally:
            if self.uploaded_resume_file:
                self.delete_uploaded_file()


