# test_api_status.py
import requests
import os
from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
def check_api_status():
    # Try to check if API is accessible
    headers = {"X-goog-api-key": GEMINI_API_KEY}
    url = "https://generativelanguage.googleapis.com/v1/models"
    
    response = requests.get(url, headers=headers)
    print(f"API Status Code: {response.status_code}")
    print(f"Response: {response.text[:200]}...")

check_api_status()