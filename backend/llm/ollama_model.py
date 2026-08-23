"""
Ollama LLM implementation - 100% FREE, runs locally, no internet needed!
"""

import logging
import requests
from typing import Optional
from .model import BaseLLM

logger = logging.getLogger(__name__)

class OllamaLLM(BaseLLM):
    """LLM implementation using local Ollama server."""
    
    def __init__(
        self, 
        model: str = "llama2",
        base_url: str = "http://localhost:11434"
    ):
        """
        Initialize Ollama LLM.
        
        Args:
            model: Model name (e.g., "llama2", "mistral", "phi")
            base_url: Ollama server URL
        """
        self.model = model
        self.base_url = base_url
        self.url = f"{base_url}/api/generate"
        
        # Check if Ollama is available
        try:
            response = requests.get(f"{base_url}/api/tags", timeout=2)
            self.available = response.status_code == 200
            if self.available:
                models = response.json().get("models", [])
                model_names = [m["name"] for m in models]
                if model not in [m.split(":")[0] for m in model_names]:
                    logger.warning(
                        f"⚠️  Model '{model}' not found. Available models: {model_names}"
                    )
                    logger.warning(f"Run: ollama pull {model}")
        except Exception as e:
            self.available = False
            logger.error(f"❌ Ollama not available: {e}")
            logger.error("Install from: https://ollama.ai")
    
    def generate_response(self, prompt: str, max_tokens: int = 512) -> str:
        """
        Generate response using Ollama.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum number of tokens to generate
            
        Returns:
            Generated response
        """
        if not self.available:
            return (
                "Ollama is not available. "
                "Install from https://ollama.ai and run: ollama serve"
            )
        
        try:
            # Format the prompt for better instruction following
            formatted_prompt = self._format_prompt(prompt)
            
            # Call Ollama API
            payload = {
                "model": self.model,
                "prompt": formatted_prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": 0.1,
                    "top_p": 0.85,
                    "repeat_penalty": 1.1,
                    "stop": ["Question:", "Context:", "\n\n\n"]
                }
            }
            
            response = requests.post(
                self.url,
                json=payload,
                timeout=120  # Ollama can be slow first time (increased to 2 minutes)
            )
            
            if response.status_code != 200:
                logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                return f"Error calling Ollama: {response.status_code}"
            
            result = response.json()
            answer = result.get("response", "").strip()
            
            # Clean up the answer
            answer = self._clean_answer(answer)
            
            return answer
            
        except requests.exceptions.Timeout:
            logger.error("Ollama timeout (first request can be slow)")
            return "Request timed out. Please try again (first request takes longer)."
        except Exception as e:
            logger.error(f"Error generating response with Ollama: {e}")
            return f"Error: {str(e)}"
    
    def _format_prompt(self, prompt: str) -> str:
        """Format prompt for better instruction following."""
        if "Context:" in prompt and "Question:" in prompt:
            return f"""You are a precise document assistant. Rules:
1. Answer ONLY what is asked — do not volunteer extra information.
2. Use ONLY the provided context. Never use outside knowledge.
3. Be direct and concise. One or two sentences maximum unless the question requires more.
4. If the answer is not in the context, say exactly: "This information is not in the document."

{prompt}

Answer (be concise, answer only what was asked):"""
        else:
            return f"""Answer concisely and accurately:

{prompt}

Answer:"""
    
    def _clean_answer(self, answer: str) -> str:
        """Clean up the generated answer."""
        # Remove common artifacts
        answer = answer.replace("Answer:", "").strip()
        
        # Remove repeated context
        if "Context:" in answer:
            answer = answer.split("Context:")[0].strip()
        if "Question:" in answer:
            answer = answer.split("Question:")[0].strip()
        
        return answer


# For easy import
def create_ollama_llm(model: str = "llama2") -> OllamaLLM:
    """
    Create an Ollama LLM instance.
    
    Args:
        model: Model name (default: "llama2")
        
    Returns:
        OllamaLLM instance
        
    Popular models:
    - "llama2": Good balance of speed and quality (3.8GB)
    - "mistral": Fast and accurate (4.1GB)
    - "phi": Smallest, fastest (1.6GB)
    - "llama2:13b": Better quality, slower (7.3GB)
    """
    return OllamaLLM(model=model)
