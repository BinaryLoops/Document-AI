# DocuMind AI

DocuMind AI is a document intelligence platform for government workflows. It combines a FastAPI backend with a Flutter mobile app for document upload, OCR, verification, knowledge-graph analysis, grounded search, notifications, and official document generation.

## Project Structure

- `backend/` - FastAPI API, authentication, document processing, verification, RAG, generation, and storage
- `mobile_flutter/` - Flutter application for citizens and government roles
- `shared/` - Shared project resources
- `deployment/` - Docker Compose configuration
- `tests/` - Cross-project test resources

## Requirements

- Python 3.11+
- Flutter SDK
- Android device or emulator for the mobile app
- Tesseract OCR for image document processing
- Optional: Ollama, Hugging Face, Firebase, Neo4j

## Run The Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

The API is available at `http://localhost:8000`. Interactive documentation is at `http://localhost:8000/docs`.

The backend starts in degraded mode when optional Firebase, Ollama, or Hugging Face services are not configured. Local rule-based LLM fallback remains available.

## Run The Flutter App

```powershell
cd mobile_flutter
flutter pub get
flutter devices
flutter run -d <device-id> --dart-define=API_BASE_URL=http://<computer-lan-ip>:8000
```

For a physical Android phone, use the computer's Wi-Fi IPv4 address instead of `10.0.2.2`, which is reserved for Android emulators. The phone and computer must be on the same network.

## Authentication

The API uses JWT bearer tokens. Citizens authenticate with Aadhaar and phone OTP. Government officials, system administrators, and issuing authorities use their role-specific credentials and MFA configuration.

The mobile client stores access and refresh tokens securely. If the backend rejects a token with `401` or `403`, the client clears the local session and returns to login instead of treating cached profile data as authenticated.

## Citizen Document Requests

Citizens submit document applications through:

```text
POST /generate/request/{doc_type}
```

The request is saved as pending and can be reviewed by an issuing authority. Direct generation endpoints such as `POST /generate/land` and `POST /generate/passport` are restricted to users with the issuing permission.

## API Health Check

```powershell
Invoke-WebRequest http://localhost:8000/health -UseBasicParsing
```

## Security Notes

- Never commit `.env`, private keys, databases, vault contents, generated PDFs, or access tokens.
- Use `.env.example` or `.env.template` as configuration references.
- Replace development secrets before deployment.
- Configure HTTPS, restricted CORS, real malware scanning, and production authentication for deployment.

## License

Proprietary project code. See the repository owner for usage and distribution terms.
