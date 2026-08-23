# 🚀 Install Ollama (100% FREE, No Internet Needed!)

## ❌ HuggingFace Not Working?

If you see this error:
```
Failed to resolve 'api-inference.huggingface.co'
```

**Solution:** Use Ollama instead! It runs 100% locally, no internet needed.

---

## ✅ **Install Ollama (2 Minutes)**

### Step 1: Download Ollama

**Windows:**
1. Open browser: https://ollama.ai/download
2. Download Windows installer
3. Run the installer
4. Wait for installation to complete

**Alternative:** Use winget:
```powershell
winget install Ollama.Ollama
```

### Step 2: Verify Installation

Open PowerShell and run:
```powershell
ollama --version
```

You should see something like:
```
ollama version is 0.1.26
```

### Step 3: Pull a Model

**Option A - Fast & Good (Recommended):**
```powershell
ollama pull llama2
```
- Size: ~3.8GB
- Speed: Fast
- Quality: Very good

**Option B - Better Quality:**
```powershell
ollama pull mistral
```
- Size: ~4.1GB
- Speed: Fast
- Quality: Excellent

**Option C - Smallest & Fastest:**
```powershell
ollama pull phi
```
- Size: ~1.6GB
- Speed: Very fast
- Quality: Good

### Step 4: Start Ollama Server

```powershell
ollama serve
```

**Keep this terminal open!** This is your Ollama server.

### Step 5: Test Ollama

Open **another** PowerShell window and test:
```powershell
ollama run llama2 "What is 2+2?"
```

You should get a response like:
```
The answer is 4.
```

### Step 6: Start Your Document System

In **another** terminal:
```powershell
cd back-end
python main.py
```

You should see:
```
✓ Using Ollama LLM (Local, FREE, No Internet Needed)
```

---

## 🧪 **Test Your System**

Go to: http://localhost:8000/docs

### Upload document (test3.png)

### Query:
```json
{"query": "What color is the apple?"}
```

### Expected Response:
```json
{
  "response": "The apple is red in colour.",
  ...
}
```

---

## 💰 **Cost Comparison:**

| Solution | Cost | Internet | Speed | Quality |
|----------|------|----------|-------|---------|
| **Ollama** ⭐ | FREE | ❌ Not needed | Medium | ⭐⭐⭐⭐ |
| **OpenAI** | $0.01/query | ✅ Required | Fast | ⭐⭐⭐⭐⭐ |
| **HuggingFace** | FREE* | ✅ Required | Slow | ⭐⭐⭐ |

---

## 🔧 **Troubleshooting:**

### Issue: "ollama: command not found"
**Solution:** 
1. Close and reopen PowerShell (to refresh PATH)
2. Or restart your computer
3. Or add manually to PATH: `C:\Users\YourName\AppData\Local\Programs\Ollama`

### Issue: "Error: model 'llama2' not found"
**Solution:** 
```powershell
ollama pull llama2
```

### Issue: "connection refused"
**Solution:** Start Ollama server:
```powershell
ollama serve
```

### Issue: Slow first request
**Solution:** This is normal! First request loads the model (~20 seconds). After that it's fast (~2-5 seconds).

### Issue: Out of memory
**Solution:** 
1. Close other applications
2. Or use smaller model:
```powershell
ollama pull phi
```
3. Update main.py to use `phi`:
```python
llm = OllamaLLM(model="phi")
```

---

## 📊 **Model Recommendations:**

### For Demo/Testing:
✅ **llama2** (3.8GB) - Best balance

### For Production:
✅ **mistral** (4.1GB) - Best quality

### For Low-End PC:
✅ **phi** (1.6GB) - Smallest, still good

### For Best Quality (if you have RAM):
✅ **llama2:13b** (7.3GB) - Excellent quality, slower

---

## 🎯 **System Now Auto-Detects!**

Your system will now automatically:
1. ✅ Try Ollama first (local, no internet)
2. ⚠️ Fall back to HuggingFace if Ollama not available

You'll see in logs which one is being used:
```
✓ Using Ollama LLM (Local, FREE, No Internet Needed)
```
or
```
✓ Using HuggingFace LLM (Requires Internet)
```

---

## ✨ **Benefits of Ollama:**

- ✅ **100% FREE** forever
- ✅ **No API keys** needed
- ✅ **No internet** needed (after download)
- ✅ **No rate limits**
- ✅ **Privacy** - your data stays local
- ✅ **Fast** - after first request
- ✅ **Good quality** - similar to GPT-3.5

---

## 🚀 **Quick Commands:**

```powershell
# Install (if not done)
winget install Ollama.Ollama

# Pull model
ollama pull llama2

# Start server (keep running)
ollama serve

# In another terminal - start your app
cd back-end
python main.py

# Test query at http://localhost:8000/docs
```

---

**Ollama is the best free option! Install it now!** 🎉
