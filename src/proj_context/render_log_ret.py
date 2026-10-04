import os
import requests
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

class RenderAPIClient:
    """
    A client to interact with the Render API.
    Provides tools to get logs, deployment history, services, and other details.
    """
    
    BASE_URL = "https://api.render.com/v1"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("RENDER_API_KEY")
        if not self.api_key:
            raise ValueError("Render API key is required. Set RENDER_API_KEY environment variable.")
            
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def get_services(self, limit: int = 20) -> List[Dict]:
        data = self._get("/services", params={"limit": limit})
        return [item.get("service", item) for item in data]

    def find_service_by_url(self, url: str) -> Optional[Dict]:
        services = self.get_services(limit=100)
        clean_url = url.replace("https://", "").replace("http://", "").rstrip("/")
        for service in services:
            service_url = service.get("serviceDetails", {}).get("url", "")
            if clean_url in service_url:
                return service
        return None

    def get_service_details(self, service_id: str) -> Dict:
        return self._get(f"/services/{service_id}")

    def get_deploys(self, service_id: str, limit: int = 20) -> List[Dict]:
        data = self._get(f"/services/{service_id}/deploys", params={"limit": limit})
        return [item.get("deploy", item) for item in data]

    def get_deploy_details(self, service_id: str, deploy_id: str) -> Dict:
        return self._get(f"/services/{service_id}/deploys/{deploy_id}")

    def get_env_vars(self, service_id: str) -> List[Dict]:
        data = self._get(f"/services/{service_id}/env-vars")
        return [item.get("envVar", item) for item in data]

    def get_logs(self, resource_id: str, owner_id: str, log_type: str = "app", limit: int = 100, **kwargs) -> List[Dict]:
        """
        Fetch logs from GET /logs endpoint.
        log_type can be 'app', 'build', or 'request'.
        """
        params = {"resource": resource_id, "ownerId": owner_id, "limit": limit}
        params.update(kwargs)
        
        try:
            # The Render API uses 'resource' and 'ownerId' query params
            data = self._get("/logs", params=params)
            return data
        except requests.exceptions.RequestException as e:
            # Try to catch 404s/403s cleanly if API differs slightly or access denied
            raise RuntimeError(f"Log retrieval failed: {str(e)}")

# --- Independent Retrieval Tools ---

def get_service_info(service_id: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve service status, runtime, config, region, branch, etc."""
    client = RenderAPIClient(api_key)
    try:
        details = client.get_service_details(service_id)
        return {
            "id": details.get("id"),
            "name": details.get("name"),
            "type": details.get("type"),
            "status": details.get("suspended", "active"),
            "repo": details.get("repo"),
            "branch": details.get("branch"),
            "ownerId": details.get("ownerId"),
            "created_at": details.get("createdAt"),
            "updated_at": details.get("updatedAt"),
            "service_details": details.get("serviceDetails", {})
        }
    except Exception as e:
        return {"error": str(e)}

def get_deployment_history(service_id: str, api_key: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
    """Retrieve recent deployments, status, commit info, timestamps, and triggers."""
    client = RenderAPIClient(api_key)
    try:
        deploys = client.get_deploys(service_id, limit=limit)
        normalized = []
        for d in deploys:
            normalized.append({
                "id": d.get("id"),
                "status": d.get("status"),
                "commit": d.get("commit", {}).get("id"),
                "commit_message": d.get("commit", {}).get("message"),
                "trigger": d.get("trigger"),
                "created_at": d.get("createdAt"),
                "started_at": d.get("startedAt"),
                "finished_at": d.get("finishedAt")
            })
        return {"deployments": normalized}
    except Exception as e:
        return {"error": str(e)}

def get_build_logs(service_id: str, api_key: Optional[str] = None, owner_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve recent build logs."""
    client = RenderAPIClient(api_key)
    try:
        if not owner_id:
            owner_id = client.get_service_details(service_id).get("ownerId")
        logs = client.get_logs(resource_id=service_id, owner_id=owner_id, log_type="build", limit=100)
        if isinstance(logs, dict) and "logs" in logs:
            logs = logs["logs"]
        return {"logs": logs}
    except Exception as e:
        return {"error": str(e)}

def get_runtime_logs(service_id: str, api_key: Optional[str] = None, owner_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve recent application/runtime logs."""
    client = RenderAPIClient(api_key)
    try:
        if not owner_id:
            owner_id = client.get_service_details(service_id).get("ownerId")
        logs = client.get_logs(resource_id=service_id, owner_id=owner_id, log_type="app", limit=100)
        if isinstance(logs, dict) and "logs" in logs:
            logs = logs["logs"]
        return {"logs": logs}
    except Exception as e:
        return {"error": str(e)}

def get_request_logs(service_id: str, api_key: Optional[str] = None, owner_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve HTTP request logs."""
    client = RenderAPIClient(api_key)
    try:
        if not owner_id:
            owner_id = client.get_service_details(service_id).get("ownerId")
        logs = client.get_logs(resource_id=service_id, owner_id=owner_id, log_type="request", limit=100)
        if isinstance(logs, dict) and "logs" in logs:
            logs = logs["logs"]
        return {"logs": logs}
    except Exception as e:
        return {"error": str(e)}

def get_metrics(service_id: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieve CPU, memory, HTTP latency metrics.
    Note: Standard v1 API does not expose a metrics endpoint. 
    """
    return {"metrics": {}, "message": "Metrics not directly exposed via Render v1 API."}

def get_environment_metadata(service_id: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve environment variables names/metadata only (no secret values)."""
    client = RenderAPIClient(api_key)
    try:
        env_vars = client.get_env_vars(service_id)
        metadata = []
        for ev in env_vars:
            metadata.append({
                "key": ev.get("key"),
                "has_value": bool(ev.get("value")),
                "value": "***REDACTED***"
            })
        return {"environment_variables": metadata}
    except Exception as e:
        return {"error": str(e)}

def extract_error_signals(service_id: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    (Legacy tool replaced by calculate_render_signals).
    """
    client = RenderAPIClient(api_key)
    signals = {
        "build_failure": False,
        "runtime_exception": False,
        "http_errors": False,
        "availability_failure": False,
        "resource_exhaustion": False,
        "database_or_external_dependency_error": False,
        "details": []
    }
    try:
        deploys = client.get_deploys(service_id, limit=5)
        latest_deploy = deploys[0] if deploys else {}
        
        if latest_deploy.get("status") in ("build_failed", "update_failed", "canceled"):
            signals["build_failure"] = True
            signals["details"].append(f"Latest deploy {latest_deploy.get('id')} failed with status {latest_deploy.get('status')}")
            
        return signals
    except Exception as e:
        signals["details"].append(f"Error fetching signals: {str(e)}")
        return signals

def calculate_render_signals(observation: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministically calculate signals using structured data and conservative pattern matching on logs.
    """
    signals = {
        "build_failure": False,
        "configuration_issue": False,
        "runtime_exception": False,
        "http_errors": False,
        "availability_failure": False,
        "resource_exhaustion": False,
        "database_or_external_dependency_error": False
    }
    
    evidence = {
        "build_failure": [],
        "configuration_issue": [],
        "runtime_exception": [],
        "http_errors": [],
        "availability_failure": [],
        "resource_exhaustion": [],
        "database_or_external_dependency_error": []
    }
    
    http_summary = {
        "total_requests": 0,
        "2xx": 0,
        "4xx": 0,
        "5xx": 0,
        "status_codes": {}
    }
    
    # 1. Analyze Deployment History for build failure
    latest_deploy = observation.get("deployment", {}).get("latest", {})
    if latest_deploy.get("status") in ("build_failed", "update_failed", "canceled"):
        signals["build_failure"] = True
        evidence["build_failure"].append(f"Deployment {latest_deploy.get('id')} status is {latest_deploy.get('status')}")

    # Helper function to extract text from log entries
    def get_log_text(log_entry):
        if isinstance(log_entry, dict):
            return log_entry.get("message", log_entry.get("text", str(log_entry)))
        return str(log_entry)

    # 2. Analyze Build Logs
    build_logs = observation.get("build", {}).get("logs", [])
    for log in build_logs:
        text = get_log_text(log)
        lower_text = text.lower()
        if re.search(r"build failed|compilation error|syntax error|error:|npm ERR!|ModuleNotFoundError", text, re.IGNORECASE):
            signals["build_failure"] = True
            evidence["build_failure"].append(text[:200])

    # 3. Analyze Runtime Logs
    runtime_logs = observation.get("runtime", {}).get("logs", [])
    for log in runtime_logs:
        text = get_log_text(log)
        lower_text = text.lower()
        
        # Runtime Exceptions
        if re.search(r"Traceback|Exception:|Error:|KeyError:|TypeError:|AttributeError:|ValueError:|SyntaxError:", text):
            signals["runtime_exception"] = True
            evidence["runtime_exception"].append(text[:200])
            
        # Resource Exhaustion
        if re.search(r"out of memory|oom|exit code 137|memory limit exceeded|worker timeout", lower_text):
            signals["resource_exhaustion"] = True
            evidence["resource_exhaustion"].append(text[:200])
            
        # Database or External API
        if re.search(r"connection refused|database|postgresql|postgres|psycopg2|redis|connection timeout|pool exhaustion|timeout|ECONNREFUSED", lower_text):
            signals["database_or_external_dependency_error"] = True
            evidence["database_or_external_dependency_error"].append(text[:200])
            
        # Configuration Issues
        if re.search(r"command not found|address already in use|port is already allocated|missing required environment variable|no module named", lower_text):
            signals["configuration_issue"] = True
            evidence["configuration_issue"].append(text[:200])

    # 4. Analyze HTTP Logs
    request_logs = observation.get("http", {}).get("requests", [])
    for log in request_logs:
        text = get_log_text(log)
        
        # Sometimes status code is explicitly in the dict
        status_code = None
        if isinstance(log, dict) and "status" in log:
            status_code = str(log.get("status"))
        else:
            # Fallback regex extraction for typical HTTP log (e.g. "... HTTP/1.1" 500 ...)
            match = re.search(r"HTTP/\d\.\d\"\s+(\d{3})", text)
            if match:
                status_code = match.group(1)

        if status_code:
            http_summary["total_requests"] += 1
            http_summary["status_codes"][status_code] = http_summary["status_codes"].get(status_code, 0) + 1
            
            if status_code.startswith("2"):
                http_summary["2xx"] += 1
            elif status_code.startswith("4"):
                http_summary["4xx"] += 1
            elif status_code.startswith("5"):
                http_summary["5xx"] += 1
                signals["http_errors"] = True
                evidence["http_errors"].append(text[:200])
        else:
            # Check for generic 5xx mentions in text if no explicit code found
            if "500 Internal Server Error" in text or "502 Bad Gateway" in text or "503 Service Unavailable" in text:
                signals["http_errors"] = True
                evidence["http_errors"].append(text[:200])
                http_summary["5xx"] += 1
                
    # Also check availability from logs
    for text in [get_log_text(l) for l in runtime_logs + request_logs]:
        if "service unavailable" in text.lower() or "health check failed" in text.lower():
            signals["availability_failure"] = True
            evidence["availability_failure"].append(text[:200])

    return {
        "signals": signals,
        "signal_evidence": {k: v[:5] for k, v in evidence.items() if v}, # Limit evidence lines
        "http_summary": http_summary
    }

# --- Orchestration Function ---

def collect_render_observation(service_id: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Systematically call appropriate Render retrieval tools and combine 
    results into a single normalized RenderObservation JSON object for triage.
    """
    observation = {
        "service": {},
        "deployment": {
            "latest": {},
            "recent": []
        },
        "build": {"logs": [], "errors": []},
        "runtime": {"logs": [], "errors": []},
        "http": {"requests": [], "error_summary": {}},
        "resources": {"cpu": {}, "memory": {}, "http_metrics": {}},
        "configuration": {
            "runtime": {},
            "docker": {},
            "health_check": {},
            "environment_variables": []
        },
        "signals": {},
        "signal_evidence": {},
        "collection_metadata": {
            "collected_at": datetime.utcnow().isoformat() + "Z",
            "time_range": {},
            "sources_available": {},
            "collection_errors": []
        }
    }

    try:
        # 1. Service Info
        service_info = get_service_info(service_id, api_key)
        if "error" in service_info:
            observation["collection_metadata"]["collection_errors"].append(f"Service Info Error: {service_info['error']}")
        else:
            observation["service"] = {
                "id": service_info.get("id"),
                "name": service_info.get("name"),
                "status": service_info.get("status"),
                "repo": service_info.get("repo"),
                "branch": service_info.get("branch"),
                "ownerId": service_info.get("ownerId")
            }
            sd = service_info.get("service_details", {})
            observation["configuration"]["runtime"] = sd.get("runtime", "unknown")
            observation["configuration"]["health_check"] = sd.get("healthCheckPath", "")
            observation["configuration"]["docker"] = sd.get("envSpecificDetails", {})
            
        # 2. Deployment History
        deploy_history = get_deployment_history(service_id, api_key, limit=5)
        if "error" in deploy_history:
            observation["collection_metadata"]["collection_errors"].append(f"Deploy History Error: {deploy_history['error']}")
        else:
            deploys = deploy_history.get("deployments", [])
            observation["deployment"]["recent"] = deploys
            if deploys:
                observation["deployment"]["latest"] = deploys[0]

        # 3. Environment Metadata
        env_meta = get_environment_metadata(service_id, api_key)
        if "error" in env_meta:
            observation["collection_metadata"]["collection_errors"].append(f"Env Metadata Error: {env_meta['error']}")
        else:
            observation["configuration"]["environment_variables"] = env_meta.get("environment_variables", [])

        # 4. Logs Collection
        owner_id = observation["service"].get("ownerId")
        
        build_logs = get_build_logs(service_id, api_key, owner_id)
        if "error" in build_logs:
            observation["collection_metadata"]["collection_errors"].append(f"Build Logs Error: {build_logs['error']}")
        else:
            observation["build"]["logs"] = build_logs.get("logs", [])
            
        runtime_logs = get_runtime_logs(service_id, api_key, owner_id)
        if "error" in runtime_logs:
            observation["collection_metadata"]["collection_errors"].append(f"Runtime Logs Error: {runtime_logs['error']}")
        else:
            observation["runtime"]["logs"] = runtime_logs.get("logs", [])
            
        request_logs = get_request_logs(service_id, api_key, owner_id)
        if "error" in request_logs:
            observation["collection_metadata"]["collection_errors"].append(f"Request Logs Error: {request_logs['error']}")
        else:
            observation["http"]["requests"] = request_logs.get("logs", [])

        # 5. Metrics Collection
        metrics = get_metrics(service_id, api_key)
        observation["collection_metadata"]["sources_available"]["metrics"] = metrics.get("message", "Attempted")

        # 6. Calculate Signals deterministically based on collected evidence
        calculated = calculate_render_signals(observation)
        observation["signals"] = calculated["signals"]
        observation["signal_evidence"] = calculated["signal_evidence"]
        observation["http"]["error_summary"] = calculated["http_summary"]

    except Exception as e:
        observation["collection_metadata"]["collection_errors"].append(f"Orchestration Error: {str(e)}")

    return observation

# Backward compatibility for the previously written tools
def fetch_deployment_history_by_url(api_key: str, url: str, limit: int = 10) -> Dict[str, Any]:
    client = RenderAPIClient(api_key)
    try:
        service = client.find_service_by_url(url)
        if not service:
            return {"error": f"Service with URL '{url}' not found."}
        return {"service": service, "deployments": client.get_deploys(service["id"], limit=limit)}
    except Exception as e:
        return {"error": str(e)}

def fetch_service_environment_by_url(api_key: str, url: str) -> Dict[str, Any]:
    client = RenderAPIClient(api_key)
    try:
        service = client.find_service_by_url(url)
        if not service:
            return {"error": f"Service with URL '{url}' not found."}
        return {"service_id": service["id"], "service_name": service["name"], "env_vars": client.get_env_vars(service["id"])}
    except Exception as e:
        return {"error": str(e)}

def analyze_deployment_failure(api_key: str, url: str) -> Dict[str, Any]:
    client = RenderAPIClient(api_key)
    try:
        service = client.find_service_by_url(url)
        if not service:
            return {"error": f"Service with URL '{url}' not found."}
        deploys = client.get_deploys(service["id"], limit=20)
        failed = [d for d in deploys if d.get("status") in ("build_failed", "update_failed", "canceled")]
        if not failed:
            return {"status": "No failed deployments found in recent history.", "recent_deploys": deploys[:3]}
        return {"service_name": service["name"], "failed_deployment": client.get_deploy_details(service["id"], failed[0]["id"])}
    except Exception as e:
        return {"error": str(e)}
