# How to Switch to a Real LLM

## Current Problem:
You're using `LocalLLM` which is just pattern matching. It cannot understand arbitrary questions.

## Solution: Use a Real Language Model

---

## 🚀 **Quick Start: Use OpenAI (Easiest)**

### Step 1: Install OpenAI
```bash
pip install openai
```

### Step 2: Get API Key
1. Go to https://platform.openai.com/
2. Sign up / Log in
3. Go to API Keys
4. Create new key
5. Copy the key

### Step 3: Update `main.py`

Replace this:
```python
from llm.model import create_llm
llm = create_llm()
```

With this:
```python
import os
from openai import OpenAI

class OpenAILLM:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
    
    def generate_response(self, prompt: str, max_tokens: int = 512) -> str:
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return "I encountered an error while processing your question."

# Use it:
llm = OpenAILLM(api_key=os.getenv("OPENAI_API_KEY", "your-key-here"))
```

### Step 4: Set API Key
```bash
# Windows PowerShell:
$env:OPENAI_API_KEY = "sk-..."

# Or hardcode in main.py (NOT recommended for production):
llm = OpenAILLM(api_key="sk-proj-...")
```

### Step 5: Restart Server
```bash
python main.py
```

### ✅ Result:
Now you can ask **ANY question** and get intelligent answers!

---

## 🚀 **Alternative: Use Ollama (FREE, Local)**

### Step 1: Install Ollama
**Windows**: Download from https://ollama.ai

### Step 2: Pull a Model
```bash
ollama pull llama2
# Or for better quality:
ollama pull mistral
```

### Step 3: Start Ollama Server
```bash
ollama serve
```

### Step 4: Update `main.py`

Add this class:
```python
import requests

class OllamaLLM:
    def __init__(self, model: str = "llama2", base_url: str = "http://localhost:11434"):
        self.model = model
        self.url = f"{base_url}/api/generate"
    
    def generate_response(self, prompt: str, max_tokens: int = 512) -> str:
        try:
            response = requests.post(self.url, json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": 0.3
                }
            })
            return response.json().get("response", "").strip()
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return "I encountered an error while processing your question."

# Use it:
llm = OllamaLLM(model="llama2")
```

### Step 5: Install requests
```bash
pip install requests
```

### Step 6: Restart Server
```bash
python main.py
```

### ✅ Result:
FREE, runs locally, no internet needed, can answer any question!

---

## 🚀 **Alternative: Use HuggingFace (FREE tier available)**

### Step 1: Get API Token
1. Go to https://huggingface.co/
2. Sign up / Log in
3. Go to Settings → Access Tokens
4. Create new token
5. Copy token

### Step 2: Your code already has `ServerlessLLM`!

Update `main.py`:
```python
from llm.serverless_model import ServerlessLLM

llm = ServerlessLLM(
    api_endpoint="https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2",
    api_key=os.getenv("HUGGINGFACE_API_KEY", "your-token-here")
)
```

### Step 3: Set Token
```bash
# Windows PowerShell:
$env:HUGGINGFACE_API_KEY = "hf_..."
```

### Step 4: Restart Server

### ✅ Result:
FREE (with limits), good quality, works over internet

---

## 📊 **Which Should You Use?**

### For Quick Demo:
✅ **Ollama** - Free, works offline, no signup needed

### For Best Quality:
✅ **OpenAI GPT-3.5** - $0.01 per document, excellent quality

### For Production (Free):
✅ **HuggingFace** - Free tier, good quality

---

## 🎯 **Why This is Better:**

### Current (LocalLLM):
```
Q: "What color is the apple?"
A: ❌ "I don't have enough information"
(Because we didn't add a color pattern)
```

### With Real LLM:
```
Q: "What color is the apple?"
A: ✅ "The apple is red in colour."

Q: "How sweet are the apples?"
A: ✅ "The apples are very sweet."

Q: "Summarize the document"
A: ✅ "The document describes red apples that are very sweet."

Q: "What's the total number of apples?"
A: ✅ "The document doesn't clearly specify the number of apples."
```

**ANY question works!** No need to add patterns!

---

## 🚀 **My Recommendation:**

1. **For Now (Demo)**: Use Ollama (free, easy, works offline)
2. **For Production**: Use OpenAI GPT-3.5-turbo (best quality/cost)

---

## 📝 **Next Steps:**

1. Choose an option above
2. Follow the installation steps
3. Update `main.py` with the LLM class
4. Restart server
5. Ask ANY question - it will work!

---

**Want me to help you set up one of these?** Let me know which option you prefer!
