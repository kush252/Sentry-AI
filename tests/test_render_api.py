import os
import json
from dotenv import load_dotenv

# Import the tools we wrote
from src.proj_context.render_log_ret import (
    collect_render_observation,
    RenderAPIClient
)

def main():
    # Load the environment variables from .env
    load_dotenv()
    
    api_key = os.getenv("RENDER_API_KEY")
    if not api_key:
        print("Error: RENDER_API_KEY not found in .env file")
        return

    # Replace this with the actual URL of your deployed render service
    target_url = "https://task-api-806e.onrender.com" 

    print(f"Testing new orchestration tool against URL: {target_url}\n")
    
    # We need the service ID first, so let's resolve it using the client
    client = RenderAPIClient(api_key)
    service = client.find_service_by_url(target_url)
    
    if not service:
        print(f"Could not find service matching URL: {target_url}")
        return
        
    service_id = service["id"]
    print(f"Resolved Service ID: {service_id}\n")

    # Test the new orchestration function
    print("--- Orchestration: collect_render_observation ---")
    observation = collect_render_observation(service_id, api_key)
    print(json.dumps(observation, indent=2))
    print("\n")

if __name__ == "__main__":
    main()
