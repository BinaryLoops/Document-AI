"""
Language model integration for generating responses.
"""

import os
import logging
import re
from typing import Optional, Dict, Any, List
import json

# Configure logging
logger = logging.getLogger(__name__)


class BaseLLM:
    """Base class for language models."""
    
    def generate_response(self, prompt: str, max_tokens: int = 512) -> str:
        """
        Generate a response to a prompt.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum number of tokens to generate
            
        Returns:
            Generated response
        """
        raise NotImplementedError("Subclasses must implement generate_response")


class OpenAIModel(BaseLLM):
    """OpenAI language model integration."""
    
    def __init__(
        self,
        model_name: str = "gpt-3.5-turbo",
        api_key: Optional[str] = None,
        temperature: float = 0.2
    ):
        """
        Initialize the OpenAI model.
        
        Args:
            model_name: Name of the OpenAI model
            api_key: OpenAI API key (defaults to OPENAI_API_KEY environment variable)
            temperature: Sampling temperature (0-1)
        """
        self.model_name = model_name
        self.temperature = temperature
        
        # Get API key
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("No OpenAI API key provided, model will not be functional")
        
        # Lazy import to avoid dependency issues
        try:
            import openai
            self.openai = openai
            self.openai.api_key = self.api_key
            self.available = True
        except ImportError:
            logger.warning("OpenAI package not installed, functionality will be limited")
            self.available = False
    
    def generate_response(self, prompt: str, max_tokens: int = 512) -> str:
        """
        Generate a response using the OpenAI API.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum number of tokens to generate
            
        Returns:
            Generated response
        """
        if not self.available or not self.api_key:
            return "OpenAI integration not available. Please check your API key and dependencies."
        
        try:
            response = self.openai.ChatCompletion.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that answers questions based on the provided context."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=max_tokens
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error generating response with OpenAI: {e}")
            return f"Error generating response: {str(e)}"
    
    def generate_openai_response(self, prompt: str, max_tokens: int = 512) -> str:
        """Alias for generate_response for compatibility."""
        return self.generate_response(prompt, max_tokens)


class LocalLLM(BaseLLM):
    """Simple local language model for when no external API is available."""
    
    def __init__(self):
        """Initialize the local LLM."""
        self.available = True
    
    def generate_response(self, prompt: str, max_tokens: int = 512) -> str:
        """
        Generate a simple response based on retrieved context.
        
        Args:
            prompt: Input prompt containing context and query
            max_tokens: Maximum response length (ignored in this simple implementation)
            
        Returns:
            Generated response summarizing the context
        """
        # Check for context and question in the prompt
        if "Context:" not in prompt or "Question:" not in prompt:
            logger.warning("Prompt missing required Context or Question sections")
            return "I don't have enough information to answer this question."
        
        try:
            # Extract context and question from prompt
            context_part = prompt.split("Context:")[1].split("Question:")[0].strip()
            question_part = prompt.split("Question:")[1].strip().split("\n")[0].strip()
            
            # Log what we extracted
            logger.info(f"Extracted context of length {len(context_part)} chars and question: {question_part}")
            
            # Check if context is empty or too short
            if not context_part or len(context_part) < 20:
                logger.warning("No context found in prompt or context too short")
                return "I don't have enough information to answer this question."
            
            # Count document chunks in context
            num_chunks = context_part.count("Document ")
            logger.info(f"Found {num_chunks} document chunks in context")
            
            # Extract content from document chunks
            chunks = []
            if num_chunks > 0:
                # Try to split by document markers
                doc_parts = context_part.split("Document ")
                # Skip the first empty part
                for part in doc_parts[1:]:
                    # Extract the document content
                    if "[Source:" in part:
                        # Extract text after the source indicator
                        content = part.split("[Source:")[1].split("]", 1)[1].strip()
                        chunks.append(content)
                    else:
                        # If no source indicator, just take the whole part
                        chunks.append(part.strip())
            else:
                # If no document markers, use the whole context
                chunks = [context_part]
            
            # Log extracted chunks
            logger.info(f"Extracted {len(chunks)} chunks from context")
            for i, chunk in enumerate(chunks[:2]):  # Log just first 2 chunks
                logger.info(f"Chunk {i+1} preview: {chunk[:100]}...")
            
            # If no usable chunks, return default response
            if not chunks or all(len(chunk.strip()) < 20 for chunk in chunks):
                logger.warning("No usable chunks found in context")
                return "I don't have enough information to answer this question."
            
            # For summarization questions
            if any(term in question_part.lower() for term in ['summarize', 'summary', 'overview', 'main points']):
                return self._generate_summary(chunks)
            
            # For comparison questions
            elif any(term in question_part.lower() for term in ['compare', 'contrast', 'difference between', 'similarities']):
                return self._generate_comparison(chunks, question_part)
            
            # For general questions
            else:
                return self._generate_answer(chunks, question_part)
                
        except Exception as e:
            logger.error(f"Error generating response in LocalLLM: {e}", exc_info=True)
            return "I encountered an error while processing your question."
    
    def _generate_summary(self, chunks: List[str]) -> str:
        """Generate a summary from document chunks."""
        # Create a simple summary based on the chunks
        if not chunks:
            return "There isn't enough information to provide a summary."
        
        response = "Based on the provided documents, here's a summary:\n\n"
        
        # Look for key sentences in each chunk
        for i, chunk in enumerate(chunks[:3]):  # Limit to first 3 chunks
            # Extract first sentence or two from each chunk
            sentences = chunk.split('.')
            summary_sentences = '. '.join(sentences[:min(3, len(sentences))]) + '.'
            
            response += f"- {summary_sentences}\n\n"
        
        return response
    
    def _generate_comparison(self, chunks: List[str], question: str) -> str:
        """Generate a comparison from document chunks."""
        if len(chunks) < 2:
            return "I don't have enough different document sections to make a comparison."
        
        response = "Comparing the information in the documents:\n\n"
        
        # Add information from first two chunks
        response += f"First section discusses: {chunks[0][:200]}...\n\n"
        response += f"Second section covers: {chunks[1][:200]}...\n\n"
        
        response += "In comparing these sections, they both relate to the topic but focus on different aspects."
        
        return response
    
    def _generate_answer(self, chunks: List[str], question: str) -> str:
        """Generate an answer to a question from document chunks."""
        # Clean up chunks - remove extra quotes
        cleaned_chunks = []
        for chunk in chunks:
            # Remove leading/trailing quotes and whitespace
            cleaned = chunk.strip().strip('"').strip("'").strip()
            if cleaned:
                cleaned_chunks.append(cleaned)
        
        if not cleaned_chunks:
            return "I don't have enough information to answer that specific question."
        
        # Combine all chunks for comprehensive search
        combined_text = ' '.join(cleaned_chunks)
        combined_lower = combined_text.lower()
        question_lower = question.lower()
        
        # Extract key terms from the question (remove stop words)
        stop_words = {'what', 'is', 'the', 'a', 'an', 'are', 'how', 'where', 'when', 'who', 'why', 'which', 'do', 'does', 'can', 'could', 'would', 'should'}
        question_words = [w.lower() for w in question.split() if w.lower() not in stop_words and len(w) > 2]
        
        # Define field mappings - map question terms to document field names
        field_mappings = {
            'applicant': 'name',
            'name': 'name',
            'address': 'address',
            'date of birth': 'date of birth',
            'dob': 'date of birth',
            'birth': 'date of birth',
            'license type': 'license type',
            'type': 'license type',
            'application date': 'application date',
            'filed': 'application date',
            'date filed': 'application date',
            'color': 'colour',
            'colour': 'colour',
        }
        
        # Try to find which field is being asked about
        asked_field = None
        for term, field in field_mappings.items():
            if term in question_lower:
                asked_field = field
                break
        
        if asked_field:
            # Look for the field value in the text using various patterns
            field_patterns = [
                rf'{re.escape(asked_field)}\s*[:=]\s*([^\n]+?)(?:\s+[A-Z][a-z]+:|$)',  # Stop at next field or end
                rf'(?:applicant\s+)?{re.escape(asked_field)}\s*[:=]\s*([^\n]+?)(?:\s+[A-Z][a-z]+:|$)',
                # Special patterns for each field
                r'name\s*[:=]\s*([^\n]+?)(?:\s+Date|$)' if asked_field == 'name' else None,
                r'date\s+of\s+birth\s*[:=]\s*([^\n]+?)(?:\s+Address|$)' if asked_field == 'date of birth' else None,
                r'address\s*[:=]\s*([^\n]+?)(?:\s+License|$)' if asked_field == 'address' else None,
                r'license\s+type\s*[:=]\s*([^\n]+?)(?:\s+Application|$)' if asked_field == 'license type' else None,
                r'class\s+([A-Z])(?:\s|,|$)' if asked_field == 'license type' else None,
                r'application\s+date\s*[:=]\s*([^\n]+?)(?:\s+[A-Z]|$)' if asked_field == 'application date' else None,
                # Color patterns
                r'(?:is|are)\s+(red|blue|green|yellow|orange|purple|pink|black|white|brown|grey|gray)(?:\s|,|\.|$)' if asked_field in ['color', 'colour'] else None,
                r'(red|blue|green|yellow|orange|purple|pink|black|white|brown|grey|gray)\s+(?:in\s+)?colou?r' if asked_field in ['color', 'colour'] else None,
                r'colou?r\s*[:=]?\s*(red|blue|green|yellow|orange|purple|pink|black|white|brown|grey|gray)' if asked_field in ['color', 'colour'] else None,
            ]
            
            # Remove None patterns
            field_patterns = [p for p in field_patterns if p]
            
            for pattern in field_patterns:
                match = re.search(pattern, combined_text, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    # Clean up the value - remove trailing punctuation and extra spaces
                    value = re.sub(r'\s+', ' ', value)  # Normalize spaces
                    value = value.rstrip(',.')  # Remove trailing punctuation
                    
                    # Format the answer nicely
                    if asked_field == 'name':
                        return f"The applicant name is {value}."
                    elif asked_field == 'address':
                        return f"The address is {value}."
                    elif asked_field == 'date of birth':
                        return f"The date of birth is {value}."
                    elif asked_field == 'license type':
                        return f"The license type is {value}."
                    elif asked_field == 'application date':
                        return f"The application date is {value}."
                    elif asked_field in ['color', 'colour']:
                        return f"The color is {value}."
                    else:
                        return f"The {asked_field} is {value}."
        
        # Fallback: Handle "what" questions generically
        if question_lower.startswith('what'):
            # Extract what's being asked about
            asked_about = question_lower.replace('what is', '').replace('what', '').replace('the', '').replace('?', '').strip()
            
            # Handle "what type of X?" questions
            if 'type of' in question_lower or 'type' in question_lower:
                # Look for common type patterns
                type_patterns = [
                    r'(?:license\s+)?type\s*[:=]\s*([^,.\n]+)',
                    r'type\s+of\s+license\s*[:=]\s*([^,.\n]+)',
                    r'class\s+([A-Z])',  # License classes like "Class B"
                ]
                
                for pattern in type_patterns:
                    match = re.search(pattern, combined_text, re.IGNORECASE)
                    if match:
                        answer_value = match.group(1).strip()
                        return f"The license type is {answer_value}."
            
            # Handle standard "what is X?" questions
            elif asked_about:
                # Look for "X: value" or "X = value" pattern in the text
                # Pattern: word followed by colon or equals, then value
                pattern = rf'{re.escape(asked_about)}\s*[:=]\s*([^,.\n]+)'
                match = re.search(pattern, combined_lower)
                
                if match:
                    answer_value = match.group(1).strip()
                    # Find the actual case-sensitive version from original text
                    original_match = re.search(rf'{re.escape(asked_about)}\s*[:=]\s*([^,.\n]+)', combined_text, re.IGNORECASE)
                    if original_match:
                        answer_value = original_match.group(1).strip()
                    return f"The {asked_about} is {answer_value}."
        
        # Try to find sentences containing the question words
        relevant_sentences = []
        for chunk in cleaned_chunks:
            # Split by common sentence delimiters
            sentences = re.split(r'[.!?]\s+', chunk)
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                    
                sentence_lower = sentence.lower()
                # Check if sentence contains any question keywords
                if any(word in sentence_lower for word in question_words):
                    relevant_sentences.append(sentence)
        
        # If we found relevant sentences, return them
        if relevant_sentences:
            answer_text = '. '.join(relevant_sentences[:2])
            if not answer_text.endswith('.'):
                answer_text += '.'
            return f"Based on the documents, {answer_text}"
        
        # Fallback: return the most relevant chunk
        best_chunk = None
        best_score = 0
        
        for chunk in cleaned_chunks:
            chunk_lower = chunk.lower()
            # Count question word matches
            score = sum(1 for word in question_words if word in chunk_lower)
            
            # Even if score is 0, use the chunk if we only have one
            if score > best_score or (len(cleaned_chunks) == 1 and best_chunk is None):
                best_score = score
                best_chunk = chunk
        
        if best_chunk:
            # Return the chunk with some context
            sentences = re.split(r'[.!?]\s+', best_chunk)
            relevant_text = '. '.join(s.strip() for s in sentences[:3] if s.strip())
            if relevant_text:
                if not relevant_text.endswith('.'):
                    relevant_text += '.'
                return f"Based on the documents, {relevant_text}"
        
        return "I don't have enough information to answer that specific question."
    
    def generate_huggingface_response(self, prompt: str, max_tokens: int = 512) -> str:
        """Alias for generate_response for compatibility."""
        return self.generate_response(prompt, max_tokens)


class ChainOfThoughtLLM(BaseLLM):
    """LLM wrapper that applies chain-of-thought reasoning."""
    
    def __init__(self, base_llm: BaseLLM):
        """
        Initialize with a base LLM.
        
        Args:
            base_llm: The underlying LLM to use
        """
        self.base_llm = base_llm
        self.available = base_llm.available
    
    def generate_response(self, prompt: str, max_tokens: int = 512) -> str:
        """
        Generate a response using chain-of-thought reasoning.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated response with reasoning
        """
        logger.info("Generating response using Chain of Thought reasoning")
        
        # First pass: generate reasoning steps
        reasoning_response = self.base_llm.generate_response(prompt, max_tokens=max_tokens)
        
        # Extract reasoning
        reasoning = reasoning_response
        
        # Second pass: generate final answer based on reasoning
        final_prompt = prompt + "\n\n" + reasoning + "\n\nFinal answer:"
        final_response = self.base_llm.generate_response(final_prompt, max_tokens=max_tokens//2)
        
        # Format the complete response
        complete_response = f"""
Step-by-step reasoning:
{reasoning}

Therefore, my answer is:
{final_response}
"""
        
        return complete_response
    
    def generate_openai_response(self, prompt: str, max_tokens: int = 512) -> str:
        """Pass through to base LLM for OpenAI responses."""
        if hasattr(self.base_llm, "generate_openai_response"):
            return self.generate_response(prompt, max_tokens)
        return self.generate_response(prompt, max_tokens)
    
    def generate_huggingface_response(self, prompt: str, max_tokens: int = 512) -> str:
        """Pass through to base LLM for HuggingFace responses."""
        if hasattr(self.base_llm, "generate_huggingface_response"):
            return self.generate_response(prompt, max_tokens)
        return self.generate_response(prompt, max_tokens)


# NOTE: ServerlessLLM / HuggingFaceInferenceAPI used to be duplicated here.
# The canonical implementation now lives in llm/serverless_model.py — imported
# lazily inside create_llm() below to avoid a circular/heavy import at module load.


# Factory function to create LLM instances
def create_llm(
    model_type: str = "local",
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs
) -> BaseLLM:
    """
    Create a language model instance.
    
    Args:
        model_type: Type of model ('openai', 'huggingface', 'serverless', 'local')
        model_name: Name of the model
        api_key: API key for the service
        **kwargs: Additional model parameters
        
    Returns:
        Language model instance
    """
    # Try to get config
    try:
        from config import LLM_MODEL_NAME, LLM_API_KEY, HUGGINGFACE_API_KEY, HUGGINGFACE_MODEL
        
        # Set defaults from config if not provided
        if model_name is None:
            if model_type == "openai":
                model_name = LLM_MODEL_NAME
            elif model_type in ["huggingface", "serverless"]:
                model_name = HUGGINGFACE_MODEL
        
        if api_key is None:
            if model_type == "openai":
                api_key = LLM_API_KEY
            elif model_type in ["huggingface", "serverless"]:
                api_key = HUGGINGFACE_API_KEY
    except (ImportError, AttributeError):
        # Use defaults if config not available
        if model_name is None:
            if model_type == "openai":
                model_name = "gpt-3.5-turbo"
            elif model_type in ["huggingface", "serverless"]:
                model_name = "mistralai/Mistral-7B-Instruct-v0.2"
    
    # Try to get API key from Streamlit secrets if available
    try:
        import streamlit as st
        if api_key is None and model_type == "openai":
            api_key = st.secrets.get("OPENAI_API_KEY")
        elif api_key is None and model_type in ["huggingface", "serverless"]:
            api_key = st.secrets.get("HUGGINGFACE_API_KEY")
    except:
        pass
        
    # Create model based on type
    if model_type.lower() == "openai":
        return OpenAIModel(model_name=model_name, api_key=api_key, **kwargs)
    elif model_type.lower() in ("serverless", "huggingface", "hf"):
        from llm.serverless_model import HuggingFaceInferenceAPI
        return HuggingFaceInferenceAPI(model_name=model_name, api_key=api_key)
    else:
        # Default to local model
        return LocalLLM()


# Function to create a Chain of Thought wrapper around any LLM
def create_cot_llm(base_llm: Optional[BaseLLM] = None) -> ChainOfThoughtLLM:
    """
    Create a Chain of Thought wrapper around an LLM.
    
    Args:
        base_llm: Base LLM to wrap (creates a new one if None)
        
    Returns:
        Chain of Thought LLM wrapper
    """
    if base_llm is None:
        base_llm = create_llm()
    
    return ChainOfThoughtLLM(base_llm)