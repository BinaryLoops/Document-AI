import os
import firebase_admin
from firebase_admin import credentials, firestore

_app = None

def init_firebase():
    global _app
    if _app is None:  # guard against double-init
        cred = credentials.Certificate(os.environ["FIREBASE_CREDENTIALS_PATH"])
        _app = firebase_admin.initialize_app(cred)
    return _app

def get_db():
    init_firebase()
    return firestore.client()