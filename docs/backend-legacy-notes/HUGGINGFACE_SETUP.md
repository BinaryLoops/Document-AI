# 🚀 HuggingFace Setup (FREE!)

## ✅ Your System is Now Configured for HuggingFace!

Just need to get your **FREE token** (takes 30 seconds):

---

## 📝 **Step 1: Get Your FREE Token**

### 1. Open browser and go to:
👉 **https://huggingface.co/join**

### 2. Sign up (FREE account):
- Enter email, username, password
- Verify email
- **No credit card needed!** ✅

### 3. Get your token:
- Go to: **https://huggingface.co/settings/tokens**
- Click **"New token"**
- Name it: `SIH_Document_System`
- Role: **Read** (default)
- Click **"Generate a token"**
- Copy the token (starts with `hf_...`)

---

## 🔧 **Step 2: Set Your Token**

### Windows PowerShell:
```powershell
$env:HUGGINGFACE_API_KEY = "hf_your_token_here"
```

### Windows CMD:
```cmd
set HUGGINGFACE_API_KEY=hf_your_token_here
```

---

## 🚀 **Step 3: Restart Server**

```bash
# Stop server (Ctrl+C in the terminal running python main.py)

# Start server again:
cd back-end
python main.py
```

You should see:
```
✓ HuggingFace LLM created (FREE tier)
```

---

## 🧪 **Step 4: Test Real AI!**

Go to: http://localhost:8000/docs

### Test Query 1: Color Question
```json
{"query": "What color is the apple?"}
```

**Expected Response:**
```json
{
  "response": "The apple is red in colour.",
  ...
}
```

### Test Query 2: Descriptive Question
```json
{"query": "How sweet are the apples?"}
```

**Expected Response:**
```json
{
  "response": "The apples are very sweet.",
  ...
}
```

### Test Query 3: Open-Ended Question
```json
{"query": "Tell me about the apples"}
```

**Expected Response:**
```json
{
  "response": "The document mentions apples that are red in colour and very sweet.",
  ...
}
```

---

## 💰 **Pricing:**

✅ **FREE Tier:**
- No credit card required
- Rate limits: ~1000 requests per day
- Perfect for development and demos!

✅ **If you need more:**
- Upgrade to Pro: $9/month (unlimited requests)
- Still way cheaper than OpenAI!

---

## 🎯 **What Changed:**

### Before (LocalLLM):
```python
# Pattern matching - only worked for pre-programmed questions
if "name" in query:
    return "Jane Smith"
else:
    return "I don't have enough information"
```

### Now (HuggingFace AI):
```python
# Real AI - understands ANY question!
llm = HuggingFaceInferenceAPI(
    model_name="mistralai/Mistral-7B-Instruct-v0.2",
    api_key=hf_token
)
# Can answer: colors, counts, descriptions, summaries, etc.
```

---

## 🔧 **Troubleshooting:**

### Issue: "HUGGINGFACE_API_KEY not set"
**Solution:** Set the environment variable before starting server:
```powershell
$env:HUGGINGFACE_API_KEY = "hf_..."
python main.py
```

### Issue: "Model is loading, please retry"
**Solution:** First request might take 20-30 seconds while model loads. Just wait and retry!

### Issue: "Rate limit exceeded"
**Solution:** 
- Wait a few minutes
- Or upgrade to HuggingFace Pro ($9/month)
- Or switch to Ollama (100% free, no limits)

### Issue: Slow responses
**Solution:** First request is slow (~20 seconds), then gets faster (~5 seconds). This is normal for serverless models!

---

## ✨ **What You Can Now Ask:**

- ✅ **Color questions:** "What color is X?"
- ✅ **Count questions:** "How many Y?"
- ✅ **Descriptive questions:** "Tell me about Z"
- ✅ **Summary questions:** "Summarize the document"
- ✅ **Comparison questions:** "What's the difference between X and Y?"
- ✅ **Extraction questions:** "What is the address/name/date?"
- ✅ **Open-ended questions:** "Describe the apples"

**ANY question works now!** 🎉

---

## 🚀 **Model Info:**

**Using:** `mistralai/Mistral-7B-Instruct-v0.2`
- ✅ Fast (5-10 seconds per query)
- ✅ Accurate (similar to GPT-3.5)
- ✅ Good at following instructions
- ✅ Free tier available

**Alternative models you can try:**
```python
# In main.py, change model_name to:

# Option 1: Smaller, faster (but less accurate)
model_name="google/flan-t5-large"

# Option 2: Bigger, better (but slower)  
model_name="meta-llama/Llama-2-13b-chat-hf"

# Option 3: Best quality (slowest)
model_name="mistralai/Mixtral-8x7B-Instruct-v0.1"
```

---

## 📞 **Need Help?**

Check the logs when you start the server:
```bash
python main.py
```

Look for:
- ✓ **"HuggingFace LLM created"** = Good!
- ⚠️ **"HUGGINGFACE_API_KEY not set"** = Need to set token
- ❌ **API errors** = Check token is valid

---

**You're all set! Get your token and test it!** 🎉
