import firebase_admin
from firebase_admin import credentials, auth, db, messaging
from django.conf import settings
import os
import json

def initialize_firebase():
    if not firebase_admin._apps:
        try:
            # Use environment variables instead of JSON file
            firebase_config = getattr(settings, 'FIREBASE_CONFIG', {})
            
            if firebase_config and all(firebase_config.values()):
                # Create credentials from environment variables
                cred = credentials.Certificate(firebase_config)
                firebase_admin.initialize_app(cred, {
                    'databaseURL': 'https://hydroponics-1bab7-default-rtdb.firebaseio.com'
                })
                print("Firebase initialized successfully with environment variables")
            else:
                print("Firebase configuration not found in environment variables")
                # Try initializing with application default credentials
                firebase_admin.initialize_app(options={
                    'databaseURL': 'https://hydroponics-1bab7-default-rtdb.firebaseio.com'
                })
                print("Firebase initialized with application default credentials")
        except Exception as e:
            print(f"Error initializing Firebase: {str(e)}")
            # Initialize with minimal configuration for database access only
            try:
                firebase_admin.initialize_app()
                print("Firebase initialized with minimal configuration")
            except Exception as nested_e:
                print(f"Failed to initialize Firebase with minimal configuration: {str(nested_e)}")

# Initialize Firebase when this module is imported
initialize_firebase()

# Reference to the root of the database
ref = db.reference('/')

def get_firebase_ref():
    """Get Firebase database reference"""
    return db.reference('/')

def is_fcm_available():
    """Check if FCM functionality is available"""
    try:
        # A simple test to verify FCM access
        app = firebase_admin.get_app()
        # Try to access messaging functionality
        messaging.Message(token="test_token", notification=messaging.Notification(title="Test", body="Test"))
        return True
    except Exception as e:
        print(f"FCM functionality check failed: {str(e)}")
        return False