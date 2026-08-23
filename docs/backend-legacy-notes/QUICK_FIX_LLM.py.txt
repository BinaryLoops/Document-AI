"""
QUICK FIX: Replace LocalLLM with Real OpenAI GPT
This will make your system answer ANY question intelligently!
"""

import os
from openai import OpenAI

class OpenAILLM:
    """Real LLM using OpenAI GPT-3.5-turbo"""
    
    def __init__(self, api_key: str = None):
        # Get API key from parameter or environment variable
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required! Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter.\n"
                "Get your key from: https://platform.openai.com/api-keys"
            )
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-3.5-turbo"
    
    def generate_response(self, prompt: str, max_tokens: int = 512) -> str:
        """Generate response using OpenAI GPT"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that answers questions based on provided document context. Be concise and accurate."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.3  # Lower = more focused answers
            )
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            print(f"❌ OpenAI API error: {e}")
            return f"I encountered an error while processing your question: {str(e)}"


# INSTRUCTIONS TO USE:
# 
# 1. Install OpenAI:
#    pip install openai
#
# 2. Get API Key:
#    - Go to https://platform.openai.com/
#    - Sign up/login
#    - Go to API Keys section
#    - Create new secret key
#    - Copy the key (starts with "sk-")
#
# 3. Set API Key (choose one):
#    
#    Option A - Environment Variable (recommended):
#    # Windows PowerShell:
#    $env:OPENAI_API_KEY = "sk-proj-your-key-here"
#    
#    # Windows CMD:
#    set OPENAI_API_KEY=sk-proj-your-key-here
#    
#    Option B - Hardcode (NOT recommended for production):
#    llm = OpenAILLM(api_key="sk-proj-your-key-here")
#
# 4. Update main.py (around line 48):
#    
#    REPLACE:
#    from llm.model import create_llm
#    llm = create_llm()
#    
#    WITH:
#    from QUICK_FIX_LLM import OpenAILLM
#    llm = OpenAILLM()  # Reads from environment variable
#
# 5. Restart server:
#    python main.py
#
# 6. Test with ANY question:
#    {"query": "What color is the apple?"}
#    {"query": "How many apples are there?"}
#    {"query": "Summarize the document"}
#    {"query": "What is the sweetness of the apples?"}
#    
#    ALL WILL WORK! ✅

# Cost: ~$0.01 per document query (very cheap!)
