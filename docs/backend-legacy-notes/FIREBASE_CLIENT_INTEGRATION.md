# 🔥 Firebase Integration Guide (Client Side)

## 📋 Overview

Your backend **already supports Firebase** - no code changes needed! Firebase is **optional** and the system works fine without it.

---

## 🏗️ **Architecture**

```
┌─────────────┐         ┌─────────────┐         ┌──────────────┐
│   Client    │ ────▶   │   Backend   │ ────▶   │   Firebase   │
│ (React/Web) │  HTTP   │   (Python)  │  Admin  │   (Cloud)    │
└─────────────┘         └─────────────┘   SDK   └──────────────┘
                                                   - Firestore
                                                   - Storage
```

### **What Backend Does:**
- ✅ Uploads documents to **Firebase Storage**
- ✅ Stores metadata in **Firestore Database**
- ✅ Tracks processing status
- ✅ Falls back gracefully if Firebase not configured

### **What Client Does:**
- ✅ Authenticate users (Firebase Auth)
- ✅ Upload files via backend API
- ✅ Monitor document status in real-time (Firestore listener)
- ✅ Display user's documents

---

## 🔧 **Backend Setup (One-Time)**

### Step 1: Create Firebase Project

1. Go to: https://console.firebase.google.com/
2. Click "Add project"
3. Name: "SIH Document Intelligence"
4. Enable Google Analytics (optional)
5. Create project

### Step 2: Get Service Account Key

1. In Firebase Console → Project Settings (⚙️)
2. Go to "Service accounts" tab
3. Click "Generate new private key"
4. Save as: `firebase-credentials.json`
5. **KEEP THIS SECURE!** Don't commit to Git!

### Step 3: Enable Firestore

1. In Firebase Console → Firestore Database
2. Click "Create database"
3. Start in **production mode**
4. Choose location (closest to your users)

### Step 4: Enable Storage

1. In Firebase Console → Storage
2. Click "Get started"
3. Use default rules for now
4. Storage bucket created automatically

### Step 5: Configure Backend

```bash
# Set environment variables
$env:FIREBASE_CREDENTIALS_PATH = "C:\path\to\firebase-credentials.json"
$env:FIREBASE_STORAGE_BUCKET = "your-project-id.appspot.com"
```

**Or in `.env` file:**
```
FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json
FIREBASE_STORAGE_BUCKET=your-project-id.appspot.com
```

### Step 6: Install Firebase Admin SDK

```bash
pip install firebase-admin
```

### Step 7: Restart Backend

```bash
python main.py
```

You should see:
```
✓ Firebase client available
```

---

## 💻 **Client Side Integration**

### **Option 1: React/Next.js Client**

#### Install Firebase SDK

```bash
npm install firebase
```

#### Initialize Firebase

```javascript
// src/lib/firebase.js
import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';

const firebaseConfig = {
  apiKey: "your-api-key",
  authDomain: "your-project.firebaseapp.com",
  projectId: "your-project-id",
  storageBucket: "your-project-id.appspot.com",
  messagingSenderId: "123456789",
  appId: "your-app-id"
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app);
```

**Get config from:** Firebase Console → Project Settings → General → Your apps → Web app

---

#### Upload Document

```javascript
// src/services/documentService.js
const uploadDocument = async (file, userId) => {
  const formData = new FormData();
  formData.append('file', file);
  
  // Upload to your backend
  const response = await fetch('http://localhost:8000/upload', {
    method: 'POST',
    body: formData,
    headers: {
      'Authorization': `Bearer ${userToken}` // If using auth
    }
  });
  
  const result = await response.json();
  
  // Backend automatically saves to Firebase!
  return result.document_id;
};
```

---

#### Monitor Document Status (Real-time)

```javascript
// src/hooks/useDocumentStatus.js
import { doc, onSnapshot } from 'firebase/firestore';
import { db } from '../lib/firebase';
import { useState, useEffect } from 'react';

export const useDocumentStatus = (documentId) => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    if (!documentId) return;
    
    // Real-time listener
    const unsubscribe = onSnapshot(
      doc(db, 'documents', documentId),
      (doc) => {
        setStatus(doc.data());
        setLoading(false);
      }
    );
    
    return () => unsubscribe();
  }, [documentId]);
  
  return { status, loading };
};
```

**Usage in component:**
```javascript
const { status, loading } = useDocumentStatus(documentId);

if (loading) return <div>Loading...</div>;

return (
  <div>
    <p>Status: {status.status}</p>
    <p>Type: {status.document_type}</p>
    <p>Confidence: {status.classification_confidence}</p>
  </div>
);
```

---

#### List User's Documents

```javascript
// src/services/documentService.js
import { collection, query, where, getDocs } from 'firebase/firestore';
import { db } from '../lib/firebase';

export const getUserDocuments = async (userId) => {
  const q = query(
    collection(db, 'documents'),
    where('userId', '==', userId)
  );
  
  const snapshot = await getDocs(q);
  return snapshot.docs.map(doc => ({
    id: doc.id,
    ...doc.data()
  }));
};
```

---

#### Query Documents

```javascript
// src/services/queryService.js
export const queryDocuments = async (query) => {
  const response = await fetch('http://localhost:8000/query', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ query })
  });
  
  return await response.json();
};
```

---

### **Option 2: Vanilla JavaScript**

```html
<!DOCTYPE html>
<html>
<head>
  <title>Document Upload</title>
</head>
<body>
  <input type="file" id="fileInput" />
  <button onclick="uploadFile()">Upload</button>
  <div id="status"></div>

  <script type="module">
    import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js';
    import { getFirestore, doc, onSnapshot } from 'https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js';

    const firebaseConfig = {
      // Your config here
    };

    const app = initializeApp(firebaseConfig);
    const db = getFirestore(app);

    window.uploadFile = async () => {
      const fileInput = document.getElementById('fileInput');
      const file = fileInput.files[0];
      
      const formData = new FormData();
      formData.append('file', file);
      
      // Upload to backend
      const response = await fetch('http://localhost:8000/upload', {
        method: 'POST',
        body: formData
      });
      
      const result = await response.json();
      const docId = result.document_id;
      
      // Listen for status updates
      onSnapshot(doc(db, 'documents', docId), (doc) => {
        const data = doc.data();
        document.getElementById('status').innerHTML = `
          Status: ${data.status}<br>
          Type: ${data.document_type}<br>
          Confidence: ${data.classification_confidence}
        `;
      });
    };
  </script>
</body>
</html>
```

---

## 📊 **Firestore Data Structure**

Your backend stores this structure:

```javascript
// Collection: documents
{
  "document_id": "uuid-here",
  "filename": "test.png",
  "status": "PROCESSING", // or "COMPLETED", "FAILED"
  "document_type": "Application",
  "classification_confidence": 0.85,
  "upload_timestamp": "2026-08-18T22:00:00Z",
  "storage_path": "documents/uuid-here.png",
  "extracted_fields": {
    "applicant_name": "John Doe",
    "date_filed": "18/08/2026"
  }
}
```

---

## 🔐 **Firebase Security Rules**

### Firestore Rules:

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

### Storage Rules:

```javascript
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    match /documents/{documentId} {
      // Users can read their own documents
      allow read: if request.auth != null;
      
      // Backend service account can write
      allow write: if request.auth.token.admin == true;
    }
  }
}
```

---

## 🎯 **Integration Flow**

### **With Firebase:**

```
1. Client uploads file to Backend
   ↓
2. Backend processes document (OCR, classification, extraction)
   ↓
3. Backend saves file to Firebase Storage
   ↓
4. Backend saves metadata to Firestore
   ↓
5. Client listens to Firestore for real-time updates
   ↓
6. Client displays results
```

### **Without Firebase:**

```
1. Client uploads file to Backend
   ↓
2. Backend processes document
   ↓
3. Backend returns results immediately
   ↓
4. Client displays results
```

**Both work perfectly!** Firebase is just for:
- ✅ Persistent storage
- ✅ Real-time updates
- ✅ Multi-device access
- ✅ Document history

---

## 📝 **Environment Variables Summary**

### Backend (.env):
```bash
FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json
FIREBASE_STORAGE_BUCKET=your-project-id.appspot.com
```

### Client (.env.local):
```bash
NEXT_PUBLIC_FIREBASE_API_KEY=your-api-key
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=your-project-id
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=your-project-id.appspot.com
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=123456789
NEXT_PUBLIC_FIREBASE_APP_ID=your-app-id
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## ✅ **Testing Integration**

### Test 1: Check Firebase Status

```bash
# Call health endpoint
curl http://localhost:8000/health
```

Response should include:
```json
{
  "firebase_enabled": true
}
```

### Test 2: Upload with Firebase

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@test.png"
```

Response includes:
```json
{
  "firebase_enabled": true,
  "document_id": "uuid-here"
}
```

### Test 3: Check Firestore

Go to Firebase Console → Firestore → documents collection
You should see your uploaded document!

---

## 🚫 **Without Firebase (Still Works!)**

If you don't set Firebase credentials, the system works fine:

- ✅ OCR still works
- ✅ Classification still works
- ✅ Field extraction still works
- ✅ Query system still works
- ❌ No persistent storage
- ❌ No real-time updates
- ❌ No multi-device sync

**Perfect for:** Development, testing, demos, standalone use

---

## 📦 **Complete React Example**

```javascript
// src/App.jsx
import { useState } from 'react';
import { useDocumentStatus } from './hooks/useDocumentStatus';

function App() {
  const [documentId, setDocumentId] = useState(null);
  const { status, loading } = useDocumentStatus(documentId);
  
  const handleUpload = async (e) => {
    const file = e.target.files[0];
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch('http://localhost:8000/upload', {
      method: 'POST',
      body: formData
    });
    
    const result = await response.json();
    setDocumentId(result.document_id);
  };
  
  const handleQuery = async () => {
    const response = await fetch('http://localhost:8000/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: 'What is the document about?' })
    });
    
    const result = await response.json();
    alert(result.response);
  };
  
  return (
    <div>
      <h1>Document Intelligence</h1>
      
      <input type="file" onChange={handleUpload} />
      
      {loading && <p>Processing...</p>}
      
      {status && (
        <div>
          <h2>Document Processed!</h2>
          <p>Type: {status.document_type}</p>
          <p>Confidence: {status.classification_confidence}</p>
          <button onClick={handleQuery}>Ask Question</button>
        </div>
      )}
    </div>
  );
}

export default App;
```

---

## 🎯 **Summary**

### **Backend (Already Done!):**
- ✅ Firebase support already implemented
- ✅ Graceful fallback if not configured
- ✅ No code changes needed

### **Client Side (Your Job!):**
- 📱 Initialize Firebase SDK
- 🔐 Add authentication (optional)
- 📤 Upload files via backend API
- 👂 Listen to Firestore for updates
- 🎨 Display results in UI

### **Firebase Setup (One-Time):**
- 🔥 Create project
- 🔑 Get credentials
- ⚙️ Set environment variables
- 🚀 Restart backend

---

**Your backend is Firebase-ready! No code changes needed!** 🎉
