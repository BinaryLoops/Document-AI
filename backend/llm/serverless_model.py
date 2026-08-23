"""
Serverless LLM implementation for improved question answering.
"""

import logging
import os
import json
import requests
from typing import Optional, Dict, Any, List
from .model import BaseLLM

# Configure logging
logger = logging.getLogger(__name__)

class ServerlessLLM(BaseLLM):
    """LLM implementation that uses serverless API endpoints for inference."""
    
    def __init__(
        self, 
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize the serverless LLM.
        
        Args:
            api_endpoint: Optional endpoint URL (defaults to HuggingFace inference API)
            api_key: API key for authentication
        """
        self.api_endpoint = api_endpoint or "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"
        self.api_key = api_key or os.environ.get("HUGGINGFACE_API_KEY")
        self.headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        self.available = self.api_key is not None
    
    def generate_response(self, prompt: str, max_tokens: int = 512) -> str:
        """
        Generate a response using the serverless API.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum number of tokens to generate
            
        Returns:
            Generated response
        """
        if not self.available:
            return "Serverless LLM is not available. Please provide an API key."
        
        # Create a properly formatted prompt for instruction-following models
        formatted_prompt = self._format_instruction_prompt(prompt)
        
        try:
            # Call the API
            payload = {
                "inputs": formatted_prompt,
                "parameters": {
                    "max_new_tokens": max_tokens,
                    "temperature": 0.1,
                    "top_p": 0.95,
                    "repetition_penalty": 1.15,
                    "do_sample": True
                }
            }
            
            response = requests.post(
                self.api_endpoint, 
                headers=self.headers, 
                json=payload,
                timeout=30
            )
            
            # Check for errors
            if response.status_code != 200:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return f"Error calling API: {response.status_code}"
            
            # Parse response based on the API format
            try:
                # For HuggingFace Inference API
                result = response.json()
                if isinstance(result, list) and len(result) > 0 and "generated_text" in result[0]:
                    return result[0]["generated_text"].strip()
                elif isinstance(result, dict) and "generated_text" in result:
                    return result["generated_text"].strip()
                else:
                    return str(result)
            except Exception as e:
                logger.error(f"Error parsing API response: {e}")
                return f"Error parsing API response: {str(e)}"
                
        except Exception as e:
            logger.error(f"Error generating response with serverless LLM: {e}")
            return f"Error generating response: {str(e)}"
    
    def _format_instruction_prompt(self, prompt: str) -> str:
        """
        Format the prompt for instruction-following models.
        
        Args:
            prompt: Raw prompt with context and question
            
        Returns:
            Formatted prompt
        """
        # Extract context and question from RAG prompt
        context = ""
        question = prompt
        
        if "Context:" in prompt and "Question:" in prompt:
            context_parts = prompt.split("Context:")[1].split("Question:")[0].strip()
            question_part = prompt.split("Question:")[-1].strip()
            
            # Format for a Mistral-style instruction prompt
            return f"""<s>[INST] You are a helpful, accurate assistant. Please answer the following question using only the provided context. If the context doesn't contain the answer, say "I don't have enough information to answer that question."

Context:
{context_parts}

Question:
{question_part} [/INST]</s>"""
        else:
            # If not in expected format, use a simpler prompt
            return f"""<s>[INST] {prompt} [/INST]</s>"""


class HuggingFaceInferenceAPI(ServerlessLLM):
    """Specialized class for HuggingFace Inference API."""
    
    def __init__(
        self,
        model_name: str = "mistralai/Mistral-7B-Instruct-v0.2",
        api_key: Optional[str] = None
    ):
        """
        Initialize the HuggingFace Inference API client.
        
        Args:
            model_name: Model identifier on HuggingFace
            api_key: HuggingFace API token
        """
        api_endpoint = f"https://api-inference.huggingface.co/models/{model_name}"
        super().__init__(api_endpoint=api_endpoint, api_key=api_key)
        self.model_name = model_name


# Update the factory function in model.py
def create_serverless_llm(
    model_type: str = "huggingface",
    model_name: Optional[str] = None,
    api_key: Optional[str] = None
) -> BaseLLM:
    """
    Create a serverless LLM instance.
    
    Args:
        model_type: Type of serverless model ("huggingface")
        model_name: Model name or identifier
        api_key: API key
        
    Returns:
        ServerlessLLM instance
    """
    if not model_name:
        model_name = "mistralai/Mistral-7B-Instruct-v0.2"
    
    # Try to get API key from environment if not provided
    if not api_key:
        if model_type.lower() == "huggingface":
            api_key = os.environ.get("HUGGINGFACE_API_KEY")
        
    # Create the appropriate model
    if model_type.lower() == "huggingface":
        return HuggingFaceInferenceAPI(model_name=model_name, api_key=api_key)
    else:
        # Default to Hugging Face
        return HuggingFaceInferenceAPI(model_name=model_name, api_key=api_key)
