import os
from dotenv import load_dotenv
from src.agent.graph import build_sentry_graph

def test_routing():
    # Load env vars (GEMINI_API_KEY)
    load_dotenv()
    
    # 1. Compile the LangGraph app
    app = build_sentry_graph()
    
    # 2. Setup a mock state where we pretend there was a build_failure
    mock_state = {
        "observation": {
            "signal_evidence": {
                "build_failure": ["ERROR: No matching distribution found for this-package-does-not-exist-12345"]
            }
        },
        "signals": {
            "build_failure": True,
            "runtime_exception": False,
            "config_issue": False
        },
        "messages": [],
        "next_node": ""
    }
    
    print("--- Starting Graph Execution ---")
    
    # 3. Invoke the graph!
    final_state = app.invoke(mock_state)
    
    print("\n--- Final State ---")
    for msg in final_state.get("messages", []):
        print(f"Message: {msg}")

if __name__ == "__main__":
    test_routing()
