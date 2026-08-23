# 🔥 Firebase Setup Guide - Complete Walkthrough

## ✅ Quick Checklist

- [ ] Create Firebase project
- [ ] Enable Firestore
- [ ] Enable Storage
- [ ] Download service account key
- [ ] Configure .env file
- [ ] Install firebase-admin
- [ ] Test connection

---

## 📋 **Step-by-Step Instructions**

### **Step 1: Create Firebase Project** (2 minutes)

1. Open: **https://console.firebase.google.com/**
2. Click **"Add project"** (or select existing project)
3. Enter project name: `SIH-Document-Intelligence`
4. Click **Continue**
5. **Disable** Google Analytics (not needed)
6. Click **Create project**
7. Wait ~30 seconds
8. Click **Continue** when ready

✅ **Result:** You're now in Firebase Console

---

### **Step 2: Enable Firestore Database** (1 minute)

1. In left sidebar: **"Firestore Database"** (🗄️ icon)
2. Click **"Create database"**
3. Select: **"Start in production mode"**
4. Click **Next**
5. Choose location: 
   - For India: **asia-south1 (Mumbai)**
   - For others: Select closest region
6. Click **Enable**
7. Wait ~1 minute

✅ **Result:** Firestore enabled - you'll see empty collections screen

---

### **Step 3: Enable Cloud Storage** (1 minute)

1. In left sidebar: **"Storage"** (📁 icon)
2. Click **"Get started"**
3. Keep default security rules (we'll update later)
4. Click **Next**
5. Choose **same location** as Firestore
6. Click **Done**

✅ **Result:** Storage enabled - you'll see empty files screen

---

### **Step 4: Get Service Account Key** (2 minutes)

⚠️ **IMPORTANT:** This file contains secrets - keep it secure!

1. Click **⚙️ Settings** icon (top left, next to "Project Overview")
2. Select **"Project settings"**
3. Go to **"Service accounts"** tab (at top)
4. Scroll down, click **"Generate new private key"**
5. In popup, click **"Generate key"**
6. File downloads: `your-project-xxxxx.json`
7. **Rename** file to: `firebase-credentials.json`
8. **Move** to: `back-end/` folder (same folder as main.py)

📁 **Final location:** `back-end/firebase-credentials.json`

✅ **Result:** You have the credentials file

---

### **Step 5: Get Your Storage Bucket Name** (30 seconds)

Still in **"Service accounts"** tab, scroll down and you'll see:

```
Admin SDK configuration snippet
```

Look for this line:
```
storageBucket: "your-project-id.appspot.com"
```

📝 **Copy this bucket name!** Example: `sih-document-intelligence.appspot.com`

---

### **Step 6: Configure Backend** (1 minute)

Open: `back-end/.env` (file already created)

Update with YOUR values:

```bash
# Firebase Configuration
FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json
FIREBASE_STORAGE_BUCKET=your-project-id.appspot.com
```

**Replace `your-project-id` with your actual project ID!**

Example:
```bash
FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json
FIREBASE_STORAGE_BUCKET=sih-document-intelligence.appspot.com
```

💾 **Save the file**

---

### **Step 7: Install Firebase Admin SDK** (30 seconds)

```bash
pip install firebase-admin
```

If already installed, upgrade:
```bash
pip install --upgrade firebase-admin
```

---

### **Step 8: Restart Backend** (10 seconds)

```bash
# Stop current server (Ctrl+C)

# Start again
cd back-end
python main.py
```

---

### **Step 9: Verify Firebase is Working** ✅

Look for these log messages:

```
✓ Loaded environment variables from .env
✓ Firebase client available
```

If you see this, **Firebase is working!** 🎉

---

## 🧪 **Test Firebase Integration**

### Test 1: Upload Document

1. Go to: http://localhost:8000/docs
2. Try `POST /upload`
3. Upload any image file
4. Check response:

```json
{
  "firebase_enabled": true  ← Should be true now!
}
```

### Test 2: Check Firestore

1. Go to Firebase Console
2. Click **Firestore Database**
3. You should see a new collection: **`documents`**
4. Click on it - you'll see your uploaded document metadata!

### Test 3: Check Storage

1. Go to Firebase Console
2. Click **Storage**
3. Navigate to **`documents/`** folder
4. You should see your uploaded file!

---

## 🔧 **Troubleshooting**

### Error: "Firebase not available"

**Check:**
1. Is `firebase-credentials.json` in `back-end/` folder?
2. Is `.env` file configured correctly?
3. Did you restart the server?

**Fix:**
```bash
# Verify file exists
ls firebase-credentials.json

# Verify .env
cat .env

# Restart server
python main.py
```

---

### Error: "Could not load credentials"

**Check:**
1. File name is exactly: `firebase-credentials.json`
2. File is valid JSON (open in notepad - should start with `{`)
3. Path in .env is correct: `./firebase-credentials.json`

**Fix:**
Re-download credentials from Firebase Console

---

### Error: "Storage bucket not found"

**Check:**
1. Bucket name in `.env` matches Firebase Console
2. No typos in bucket name
3. Bucket name ends with `.appspot.com`

**Fix:**
Copy exact bucket name from Firebase Console → Project Settings → General

---

### Error: "Permission denied"

**Fix Firestore Rules:**

Go to Firestore → Rules tab → Replace with:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} {
      allow read, write: if true;  // For development only!
    }
  }
}
```

**Fix Storage Rules:**

Go to Storage → Rules tab → Replace with:

```javascript
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    match /{allPaths=**} {
      allow read, write: if true;  // For development only!
    }
  }
}
```

⚠️ **Note:** These rules allow all access - only for development!

---

## 🔐 **Security (Production)**

For production, update rules:

### Firestore:
```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /documents/{documentId} {
      // Users can only read their own documents
      allow read: if request.auth != null && 
                     resource.data.userId == request.auth.uid;
      
      // Backend service account can write
      allow write: if request.auth.token.admin == true;
    }
  }
}
```

### Storage:
```javascript
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    match /documents/{documentId} {
      allow read: if request.auth != null;
      allow write: if request.auth.token.admin == true;
    }
  }
}
```

---

## 📊 **What You Get With Firebase**

### ✅ **Enabled Features:**

1. **Persistent Storage**
   - Documents saved permanently
   - Survive server restarts
   - Access from anywhere

2. **Cloud Storage**
   - Files stored in Firebase Storage
   - Scalable and reliable
   - Built-in CDN

3. **Real-time Updates**
   - Client can listen to document status
   - Instant notifications
   - No polling needed

4. **Multi-device Access**
   - Same documents on all devices
   - Sync across clients
   - Shared access

5. **Document History**
   - Track all uploads
   - View past documents
   - Search and filter

---

## 🎯 **Client Integration (Later)**

Your Firebase is now ready! When you build the frontend:

### Get Web App Config:

1. Firebase Console → Project Settings
2. Scroll to **"Your apps"**
3. Click **"Web"** icon (</> symbol)
4. Register app name: `SIH-Web-Client`
5. Copy the `firebaseConfig` object

You'll get something like:
```javascript
const firebaseConfig = {
  apiKey: "AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
  authDomain: "your-project.firebaseapp.com",
  projectId: "your-project-id",
  storageBucket: "your-project-id.appspot.com",
  messagingSenderId: "123456789",
  appId: "1:123456789:web:xxxxxxxxxxxxx"
};
```

Use this in your React/Next.js client!

---

## ✨ **Summary**

After setup, you have:

- ✅ Firebase project created
- ✅ Firestore database enabled
- ✅ Cloud storage enabled
- ✅ Backend configured
- ✅ Service account connected
- ✅ Documents saved to cloud
- ✅ Ready for client integration

**Next Steps:**
1. Test upload → Check Firestore
2. Test query → Verify it works
3. Build frontend when ready
4. Use Firebase SDK in client

---

## 📞 **Need Help?**

Check logs:
```bash
python main.py
```

Look for:
- ✓ **"Firebase client available"** = Good!
- ⚠️ **"Firebase not available"** = Check setup
- ❌ **Error messages** = Follow troubleshooting guide

---

**Firebase is now fully integrated and ready! 🔥**
