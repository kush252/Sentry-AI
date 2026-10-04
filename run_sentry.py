import os
import argparse
from dotenv import load_dotenv

from src.proj_context.render_log_ret import collect_render_observation, RenderAPIClient
from src.agent.graph import build_sentry_graph

def main():
    parser = argparse.ArgumentParser(description="Run the Sentry LangGraph pipeline on a Render service.")
    parser.add_argument("--url", type=str, help="The URL of the Render service (e.g. https://my-app.onrender.com)")
    parser.add_argument("--service-id", type=str, help="The Render Service ID (e.g. srv-cabc1234defg)")
    args = parser.add_argument_group("Either --url or --service-id is required.")
    
    parsed_args = parser.parse_args()
    
    # Load env for API keys
    load_dotenv()
    
    if not parsed_args.url and not parsed_args.service_id:
        print("Error: You must provide either --url or --service-id.")
        return

    service_id = parsed_args.service_id
    
    # If URL is provided, we need to find the service ID first
    if parsed_args.url:
        print(f"[*] Looking up Render service by URL: {parsed_args.url}")
        client = RenderAPIClient()
        service = client.find_service_by_url(parsed_args.url)
        if not service:
            print("Error: Could not find a Render service matching that URL.")
            return
        service_id = service["id"]
        print(f"[*] Found Service ID: {service_id} ({service.get('name')})")

    print(f"\n[1] Collecting Render Observation for {service_id}...")
    observation = collect_render_observation(service_id)
    
    signals = observation.get("signals", {})
    evidence = observation.get("signal_evidence", {})
    
    # Ensure the service URL is explicitly injected so Active Investigation can use it
    if "service" not in observation:
        observation["service"] = {}
    if parsed_args.url:
        observation["service"]["url"] = parsed_args.url
    elif "url" not in observation["service"]:
        # Best effort fallback if URL wasn't provided directly
        observation["service"]["url"] = f"https://{service_id}.onrender.com"
    
    print("[*] Signals Detected:", [k for k, v in signals.items() if v])
    
    # Setup initial state
    initial_state = {
        "observation": observation,
        "signals": signals,
        "signal_evidence": evidence
    }
    
    print("\n[2] Building and Executing Sentry Graph...\n")
    app = build_sentry_graph()
    
    # Stream the graph execution to see it thinking step by step
    final_state = None
    for output in app.stream(initial_state):
        for node_name, state in output.items():
            print(f"--- Node Executed: {node_name} ---")
            if "messages" in state and state["messages"]:
                last_msg = state["messages"][-1]
                msg_content = last_msg[1] if isinstance(last_msg, tuple) else last_msg.content if hasattr(last_msg, "content") else str(last_msg)
                print(f"-> {msg_content}\n")
            
            final_state = state

    print("=========================================")
    print("             FINAL REPORT")
    print("=========================================")
    print(final_state.get("final_report", "No report generated."))
    
    print("\nNote: Any raw tool execution data was saved to 'investigation_data.jsonl'")

if __name__ == "__main__":
    main()
