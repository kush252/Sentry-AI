import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        models = response.json().get('models', [])
        print("Available Models:")
        for m in models:
            print(f"- {m['name']} (supported methods: {m.get('supportedGenerationMethods', [])})")
    else:
        print(f"Error fetching models: {response.text}")
else:
    print("No API key found.")
