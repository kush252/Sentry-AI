import os
import json
from dotenv import load_dotenv
from src.proj_context.render_log_ret import RenderAPIClient

def list_services():
    load_dotenv()
    api_key = os.getenv("RENDER_API_KEY")
    if not api_key:
        print("No RENDER_API_KEY found.")
        return
    
    client = RenderAPIClient(api_key)
    try:
        services = client.get_services(limit=50)
        print(f"Found {len(services)} services.")
        for s in services:
            print(f"- Name: {s.get('name')}")
            print(f"  ID: {s.get('id')}")
            print(f"  Type: {s.get('type')}")
            print(f"  Status: {s.get('suspended', 'active')}")
            print(f"  URL: {s.get('serviceDetails', {}).get('url', 'N/A')}")
            print("---")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_services()
