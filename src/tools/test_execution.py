import time
import requests
from typing import Dict, Any

def execute_endpoint_test(base_url: str, test_def: Dict[str, Any]) -> Dict[str, Any]:
    target = test_def.get("target", "")
    parts = target.split(" ")
    method = parts[0] if len(parts) > 1 else "GET"
    path = parts[1] if len(parts) > 1 else target
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    
    start = time.time()
    try:
        resp = requests.request(method, url, timeout=5)
        latency = (time.time() - start) * 1000
        
        return {
            "test_id": test_def.get("id", "unknown"),
            "test_type": "endpoint",
            "target": target,
            "status": "PASS" if resp.status_code < 400 else "FAIL",
            "evidence": {
                "http_status": resp.status_code,
                "latency_ms": round(latency, 2),
                "response_content_type": resp.headers.get("Content-Type", ""),
                "response_shape": "object" if str(resp.text).strip().startswith("{") else ("array" if str(resp.text).strip().startswith("[") else "other")
            },
            "failures": [f"Received status {resp.status_code}"] if resp.status_code >= 400 else [],
            "observations": [],
            "limitations": []
        }
    except Exception as e:
        return {
            "test_id": test_def.get("id", "unknown"),
            "test_type": "endpoint",
            "target": target,
            "status": "ERROR",
            "evidence": {},
            "failures": [str(e)],
            "observations": [],
            "limitations": []
        }

def execute_contract_test(base_url: str, test_def: Dict[str, Any], backend_context: Dict[str, Any]) -> Dict[str, Any]:
    # In a real implementation, this would deeply compare OpenAPI schemas to the actual response.
    # For now, we perform a basic request and note the limitation.
    res = execute_endpoint_test(base_url, test_def)
    res["test_type"] = "contract"
    res["limitations"].append("Deep schema validation not fully implemented. Basic HTTP check performed.")
    return res

def execute_edge_case_test(base_url: str, test_def: Dict[str, Any]) -> Dict[str, Any]:
    cases = test_def.get("cases", [])
    target = test_def.get("target", "")
    
    results = []
    failures = []
    
    for case in cases:
        # Pseudo-execution of edge cases
        results.append({"case": case, "status": "SKIPPED"})
        failures.append(f"Case '{case}' skipped (safe mode)")
        
    return {
        "test_id": test_def.get("id", "unknown"),
        "test_type": "edge_case",
        "target": target,
        "status": "INCONCLUSIVE",
        "evidence": {"cases_executed": len(cases), "results": results},
        "failures": failures,
        "observations": [],
        "limitations": ["Edge case generation not fully wired. Safe mode skipped execution."]
    }

def execute_synthetic_flow_test(base_url: str, test_def: Dict[str, Any]) -> Dict[str, Any]:
    workflow = test_def.get("workflow", "unknown")
    steps = test_def.get("steps", [])
    
    return {
        "test_id": test_def.get("id", "unknown"),
        "test_type": "synthetic_flow",
        "target": workflow,
        "status": "INCONCLUSIVE",
        "evidence": {"steps_planned": len(steps)},
        "failures": ["Stateful multi-step execution not yet supported."],
        "observations": [],
        "limitations": ["Requires stateful executor credentials to safely execute workflows."]
    }

def execute_performance_probe(base_url: str, test_def: Dict[str, Any]) -> Dict[str, Any]:
    target = test_def.get("target", "")
    parts = target.split(" ")
    method = parts[0] if len(parts) > 1 else "GET"
    path = parts[1] if len(parts) > 1 else target
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    
    req_count = test_def.get("requests", 3)
    
    latencies = []
    errors = 0
    
    for _ in range(req_count):
        try:
            start = time.time()
            resp = requests.request(method, url, timeout=5)
            if resp.status_code >= 400:
                errors += 1
            latencies.append((time.time() - start) * 1000)
        except Exception:
            errors += 1
            
    if not latencies:
        return {
            "test_id": test_def.get("id", "unknown"),
            "test_type": "performance",
            "target": target,
            "status": "ERROR",
            "evidence": {},
            "failures": ["All performance requests failed."],
            "observations": [],
            "limitations": []
        }
        
    latencies.sort()
    p50 = latencies[len(latencies)//2]
    p95 = latencies[int(len(latencies) * 0.95)] if len(latencies) > 1 else p50
    max_ms = latencies[-1]
    
    return {
        "test_id": test_def.get("id", "unknown"),
        "test_type": "performance",
        "target": target,
        "status": "PASS" if errors == 0 else "FAIL",
        "evidence": {
            "requests": req_count,
            "successful_requests": req_count - errors,
            "error_requests": errors,
            "p50_ms": round(p50, 2),
            "p95_ms": round(p95, 2),
            "max_ms": round(max_ms, 2)
        },
        "failures": [] if errors == 0 else [f"{errors}/{req_count} requests failed."],
        "observations": [],
        "limitations": []
    }

def execute_dependency_check(base_url: str, test_def: Dict[str, Any]) -> Dict[str, Any]:
    target = test_def.get("target", "")
    res = execute_endpoint_test(base_url, test_def)
    res["test_type"] = "dependency"
    res["limitations"].append("Checked dependency blindly via endpoint proxy.")
    return res

class TestExecutor:
    """Deterministic routing to the appropriate test tool."""
    def __init__(self, base_url: str, backend_context: Dict[str, Any]):
        self.base_url = base_url
        self.backend_context = backend_context
        
    def run_test(self, test_def: Dict[str, Any]) -> Dict[str, Any]:
        test_type = test_def.get("type", "endpoint")
        
        if test_type == "endpoint":
            return execute_endpoint_test(self.base_url, test_def)
        elif test_type == "contract":
            return execute_contract_test(self.base_url, test_def, self.backend_context)
        elif test_type == "edge_case":
            return execute_edge_case_test(self.base_url, test_def)
        elif test_type == "synthetic_flow":
            return execute_synthetic_flow_test(self.base_url, test_def)
        elif test_type == "performance":
            return execute_performance_probe(self.base_url, test_def)
        elif test_type == "dependency":
            return execute_dependency_check(self.base_url, test_def)
        else:
            return {
                "test_id": test_def.get("id", "unknown"),
                "test_type": test_type,
                "target": test_def.get("target", "unknown"),
                "status": "SKIPPED",
                "evidence": {},
                "failures": [],
                "observations": [],
                "limitations": [f"Unknown test type '{test_type}' requested."]
            }
