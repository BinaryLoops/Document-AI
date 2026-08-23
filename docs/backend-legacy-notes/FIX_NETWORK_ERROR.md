# 🔴 Fix Network Error - HuggingFace Not Reachable

## ❌ Your Error:
```
Failed to resolve 'api-inference.huggingface.co'
HTTPSConnection Failed to resolve
```

**Cause:** Your computer can't reach HuggingFace servers (no internet / firewall / network issue)

---

## ✅ **SOLUTION: Use Local Ollama (2 Minutes)**

Ollama runs **100% locally** - no internet needed!

---

## 🚀 **Quick Fix (Automated):**

### Run this script:
```powershell
cd back-end
.\setup_ollama.ps1
```

This will:
1. ✅ Check if Ollama is installed
2. ✅ Install it (if needed)
3. ✅ Download llama2 model (~3.8GB)
4. ✅ Start Ollama server
5. ✅ Ready to use!

---

## 🚀 **Manual Setup (If Script Fails):**

### Step 1: Install Ollama
```powershell
# Option A - Using winget:
winget install Ollama.Ollama

# Option B - Manual download:
# Go to: https://ollama.ai/download
# Download and run Windows installer
```

### Step 2: Verify Installation
```powershell
# Close and reopen PowerShell, then:
ollama --version
```

### Step 3: Download Model
```powershell
ollama pull llama2
```
This downloads ~3.8GB (one-time only)

### Step 4: Start Ollama Server
```powershell
# Open a NEW terminal and keep it running:
ollama serve
```

### Step 5: Start Your Document System
```powershell
# In ANOTHER terminal:
cd back-end
python main.py
```

You should see:
```
✓ Using Ollama LLM (Local, FREE, No Internet Needed)
```

### Step 6: Test!
Go to: http://localhost:8000/docs

Upload document and query:
```json
{"query": "What color is the apple?"}
```

---

## ✨ **System Auto-Detects:**

Your code now tries:
1. ✅ **Ollama first** (local, no internet)
2. ⚠️ **HuggingFace fallback** (if Ollama not available)

---

## 💰 **Why Ollama is Better:**

| Feature | Ollama | HuggingFace |
|---------|--------|-------------|
| **Cost** | FREE forever | FREE (with limits) |
| **Internet** | ❌ Not needed | ✅ Required |
| **Speed** | Medium (2-5s) | Slow (10-20s) |
| **Rate Limits** | ❌ None | ✅ Yes (~1000/day) |
| **Privacy** | ✅ Local | ⚠️ Data sent to cloud |
| **Setup** | 2 minutes | Need API token |

---

## 🔧 **Troubleshooting:**

### "ollama: command not found"
**Fix:** Close and reopen PowerShell (refreshes PATH)

### "Error: model 'llama2' not found"
**Fix:** 
```powershell
ollama pull llama2
```

### "connection refused"
**Fix:** Start server:
```powershell
ollama serve
```

### First request is slow (20 seconds)
**Normal!** Model loads on first request. After that it's fast (2-5 seconds).

### Out of memory
**Fix:** Use smaller model:
```powershell
ollama pull phi  # Only 1.6GB
```

Then update `back-end/main.py`:
```python
llm = OllamaLLM(model="phi")
```

---

## 📊 **Model Options:**

| Model | Size | Speed | Quality | RAM Needed |
|-------|------|-------|---------|------------|
| **phi** | 1.6GB | ⚡⚡⚡ Fast | ⭐⭐⭐ | 4GB |
| **llama2** ⭐ | 3.8GB | ⚡⚡ Medium | ⭐⭐⭐⭐ | 8GB |
| **mistral** | 4.1GB | ⚡⚡ Medium | ⭐⭐⭐⭐⭐ | 8GB |
| **llama2:13b** | 7.3GB | ⚡ Slow | ⭐⭐⭐⭐⭐⭐ | 16GB |

**Recommended:** llama2 (good balance)

---

## ✅ **After Setup:**

You'll be able to ask **ANY question** and get smart answers:

```json
{"query": "What color is the apple?"}
→ "The apple is red in colour."

{"query": "How sweet are the apples?"}
→ "The apples are very sweet."

{"query": "Summarize the document"}
→ "The document describes red apples that are very sweet."

{"query": "What is Jane's address?"}
→ "Jane Smith's address is 123 Main Street, New York."
```

**No more pattern matching! Real AI!** 🎉

---

## 🎯 **Quick Commands:**

```powershell
# Setup (one-time)
cd back-end
.\setup_ollama.ps1

# Or manual:
winget install Ollama.Ollama
ollama pull llama2

# Start Ollama (keep running in one terminal)
ollama serve

# Start your app (in another terminal)
cd back-end
python main.py

# Test at:
# http://localhost:8000/docs
```

---

**Run the setup script now!** 🚀
