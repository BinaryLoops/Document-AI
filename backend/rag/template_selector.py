"""
Smart template selector for choosing the best prompt template based on the question and content.
"""

import logging
import re
from typing import Dict, List, Any, Optional

# Configure logging
logger = logging.getLogger(__name__)

class TemplateSelector:
    """Selects the appropriate prompt template based on the query and context."""
    
    def __init__(
        self,
        templates: Optional[Dict[str, str]] = None
    ):
        """
        Initialize the template selector.
        
        Args:
            templates: Dictionary of template names to template strings
        """
        self.templates = templates or {}
        self._load_default_templates()
        self.selected_template_name = "default"
    
    def _load_default_templates(self):
        """Load default templates if none were provided."""
        if not self.templates:
            try:
                from config import (
                    DEFAULT_PROMPT_TEMPLATE,
                    ENHANCED_PROMPT_TEMPLATE,
                    DOCUMENT_SUMMARY_TEMPLATE,
                    DOCUMENT_COMPARE_TEMPLATE,
                    TECHNICAL_DOCUMENT_TEMPLATE,
                    CHAIN_OF_THOUGHT_TEMPLATE
                )
                
                self.templates = {
                    "default": DEFAULT_PROMPT_TEMPLATE,
                    "enhanced": ENHANCED_PROMPT_TEMPLATE,
                    "summary": DOCUMENT_SUMMARY_TEMPLATE,
                    "compare": DOCUMENT_COMPARE_TEMPLATE,
                    "technical": TECHNICAL_DOCUMENT_TEMPLATE,
                    "chain_of_thought": CHAIN_OF_THOUGHT_TEMPLATE
                }
            except (ImportError, AttributeError):
                # Fall back to a basic template if config templates aren't available
                self.templates = {
                    "default": """
                    Answer the following question based ONLY on the provided context.
                    
                    Context:
                    {context}
                    
                    Question: {query}
                    
                    Answer:
                    """
                }
                logger.warning("Could not load templates from config, using basic template.")
    
    def select_template(
        self,
        query: str,
        context: str,
        metadata: Optional[List[Dict[str, Any]]] = None,
        use_reasoning: bool = False
    ) -> str:
        """
        Select the best template based on the query and context.
        
        Args:
            query: User's question
            context: Retrieved context
            metadata: Optional metadata for the retrieved documents
            use_reasoning: Whether to force use of chain-of-thought reasoning
            
        Returns:
            Selected template string
        """
        try:
            # Default to enhanced template
            self.selected_template_name = "enhanced"
            
            # Check for context size issues
            words_in_context = len(re.findall(r'\b\w+\b', context))
            if words_in_context < 30:  # Minimum threshold
                logger.warning(f"Context too short ({words_in_context} words) for reliable template selection")
                self.selected_template_name = "default"
                return self.templates.get("default", self.templates["enhanced"])
            
            # Check for summary requests
            summary_patterns = [
                r'summarize', r'summary', r'overview', r'main points',
                r'what is this (document|text|content) about',
                r'describe the (document|text|content)',
                r'key (points|findings|ideas|concepts)',
                r'tldr', r'gist', r'brief description'
            ]
            
            if any(re.search(pattern, query.lower()) for pattern in summary_patterns):
                self.selected_template_name = "summary"
                logger.info("Selected summary template based on query")
            
            # Check for comparison requests
            compare_patterns = [
                r'compare', r'contrast', r'difference', r'similarities',
                r'how does .+ differ from', r'what is the relationship between',
                r'versus', r'vs\.', r'similarities and differences'
            ]
            
            if any(re.search(pattern, query.lower()) for pattern in compare_patterns):
                self.selected_template_name = "compare"
                logger.info("Selected comparison template based on query")
            
            # Check for technical content
            technical_patterns = [
                r'code', r'function', r'api', r'class', r'method',
                r'implementation', r'how to implement', r'syntax',
                r'programming', r'algorithm', r'data structure',
                r'technical', r'configure', r'setup', r'install'
            ]
            
            # Check if context contains code-like content
            code_indicators = [
                r'def\s+\w+\s*\(', r'class\s+\w+', r'function\s+\w+',
                r'import\s+\w+', r'from\s+\w+\s+import', r'#include',
                r'<script', r'<style', r'<html', r'```python', r'```java',
                r'```javascript', r'```c', r'```cpp', r'```'
            ]
            
            if (any(re.search(pattern, query.lower()) for pattern in technical_patterns) or
                any(re.search(pattern, context) for pattern in code_indicators)):
                self.selected_template_name = "technical"
                logger.info("Selected technical template based on content and/or query")
            
            # Check for complex questions requiring reasoning
            complex_patterns = [
                r'why', r'how', r'explain', r'reason', r'analyze',
                r'what would happen if', r'implications', r'consequences',
                r'evaluate', r'assess', r'determine the cause'
            ]
            
            # If question appears complex or reasoning is explicitly requested, use chain of thought
            if use_reasoning or any(re.search(rf'\b{pattern}\b', query.lower()) for pattern in complex_patterns):
                self.selected_template_name = "chain_of_thought"
                logger.info("Selected chain of thought template for complex question")
            
            # Check metadata if provided
            if metadata:
                # Example: Use specific templates based on document source or type
                for meta in metadata:
                    if meta.get('source', '').lower().endswith(('.py', '.js', '.java', '.c', '.cpp', '.h')):
                        self.selected_template_name = "technical"
                        logger.info(f"Selected technical template based on source file: {meta.get('source')}")
                        break
            
            # Make sure template exists - fall back to default if selected template isn't found
            if self.selected_template_name not in self.templates:
                logger.warning(f"Template '{self.selected_template_name}' not found, using default")
                self.selected_template_name = "default"
            
            logger.info(f"Selected template: {self.selected_template_name}")
            return self.templates[self.selected_template_name]
            
        except Exception as e:
            logger.warning(f"Error in template selection: {e}")
            self.selected_template_name = "default"
            return self.templates.get("default", self.templates.get("enhanced", ""))