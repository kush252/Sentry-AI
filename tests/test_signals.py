import json
from src.proj_context.render_log_ret import calculate_render_signals

def main():
    # 1. Create a mocked observation with some fake error logs
    mock_observation = {
        "deployment": {
            "latest": {"status": "live", "id": "dep-123"}
        },
        "build": {
            "logs": []
        },
        "runtime": {
            "logs": [
                {"message": "INFO: Application startup complete."},
                {"message": "ERROR: Traceback (most recent call last):"},
                {"message": "  File \"main.py\", line 10, in my_func"},
                {"message": "KeyError: 'user_id'"}
            ]
        },
        "http": {
            "requests": [
                {"message": "10.0.0.1 - \"POST /users HTTP/1.1\" 500 Internal Server Error"}
            ]
        }
    }

    print("--- Testing calculate_render_signals with Mock Error Logs ---")
    
    # 2. Run our deterministic signal calculation
    calculated = calculate_render_signals(mock_observation)
    
    # 3. Print the results
    print(json.dumps(calculated, indent=2))

if __name__ == "__main__":
    main()
