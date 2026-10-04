import requests
import time
from urllib.parse import urljoin

class BackendDiscoveryTool:
    """
    Implements Phase 1 of the Backend Discovery Node.
    Deterministically discovers the deployed backend without requiring the LLM to inspect the repository.
    """
    def __init__(self, service_url: str):
        self.service_url = service_url.rstrip("/")

    def run_discovery(self) -> dict:
        result = {
            "service_info": self._discover_service_info(),
            "api_spec": {},
            "normalized_endpoints": [],
            "authentication": {},
            "endpoint_probes": []
        }

        if not result["service_info"]["reachable"]:
            return result
        
        # 3. API Specification Discovery
        spec = self._discover_openapi()
        if spec:
            result["api_spec"] = {
                "specification_found": True,
                "specification_url": spec.get("_source_url", ""),
                "openapi_version": spec.get("openapi", spec.get("swagger", "unknown")),
                "api_title": spec.get("info", {}).get("title", "unknown"),
                "api_version": spec.get("info", {}).get("version", "unknown"),
            }
            # 4. Normalize the API Spec
            normalized = self._normalize_openapi(spec)
            
            # 5. Endpoint Classification
            normalized = self._classify_endpoints(normalized, spec)
            result["normalized_endpoints"] = normalized
            
            # 6. Authentication Discovery
            result["authentication"] = self._discover_authentication(normalized, spec)
            
            # 7. Basic Endpoint Probing
            result["endpoint_probes"] = self._probe_endpoints(normalized)
        else:
            result["api_spec"] = {"specification_found": False}
        
        return result

    def _discover_service_info(self):
        info = {
            "reachable": False,
            "http_status": None,
            "latency_ms": None,
            "redirects": 0,
            "tls_status": "unknown",
            "response_headers": {}
        }
        try:
            start_time = time.time()
            resp = requests.get(self.service_url, timeout=5, verify=True, allow_redirects=True)
            latency = (time.time() - start_time) * 1000
            
            info["reachable"] = True
            info["http_status"] = resp.status_code
            info["latency_ms"] = round(latency, 2)
            info["redirects"] = len(resp.history)
            info["tls_status"] = "valid" if self.service_url.startswith("https") else "none"
            info["response_headers"] = dict(resp.headers)
        except requests.exceptions.SSLError:
            info["reachable"] = True
            info["tls_status"] = "invalid"
        except requests.exceptions.RequestException:
            info["reachable"] = False
            
        return info

    def _discover_openapi(self):
        common_paths = [
            "/openapi.json",
            "/swagger.json",
            "/api/openapi.json",
            "/v1/openapi.json"
        ]
        
        for path in common_paths:
            try:
                url = urljoin(self.service_url + "/", path.lstrip("/"))
                resp = requests.get(url, timeout=3)
                if resp.status_code == 200:
                    if "application/json" in resp.headers.get("Content-Type", ""):
                        data = resp.json()
                        if "openapi" in data or "swagger" in data:
                            data["_source_url"] = url
                            return data
            except Exception:
                continue
        return None

    def _normalize_openapi(self, spec: dict):
        normalized = []
        paths = spec.get("paths", {})
        for path, methods in paths.items():
            for method, details in methods.items():
                if method.lower() not in ["get", "post", "put", "delete", "patch", "options"]:
                    continue
                
                req_schema = "unknown"
                if "requestBody" in details:
                    req_schema = "present"
                    
                resp_schema = {}
                for status, r_details in details.get("responses", {}).items():
                    resp_schema[status] = r_details.get("description", "")
                
                ep = {
                    "method": method.upper(),
                    "path": path,
                    "resource": path.strip("/").split("/")[0] if path.strip("/") else "root",
                    "tags": details.get("tags", []),
                    "request_schema": req_schema,
                    "responses": resp_schema,
                    "security_requirements": details.get("security", []),
                    "authentication": "UNKNOWN"
                }
                normalized.append(ep)
        return normalized

    def _classify_endpoints(self, normalized: list, spec: dict):
        global_security = spec.get("security", [])
        
        for ep in normalized:
            sec = ep.get("security_requirements", [])
            if sec:
                ep["authentication"] = "AUTH_REQUIRED"
            elif global_security and sec is not None and not (isinstance(sec, list) and len(sec) == 0 and "security" in ep):
                ep["authentication"] = "AUTH_REQUIRED"
            else:
                ep["authentication"] = "PUBLIC"
                
            if "401" in ep["responses"] or "403" in ep["responses"]:
                ep["authentication"] = "AUTH_REQUIRED"
                
        return normalized

    def _discover_authentication(self, normalized: list, spec: dict):
        auth = {
            "mechanisms": [],
            "login_endpoints": [],
            "protected_endpoints": []
        }
        
        sec_schemes = spec.get("components", {}).get("securitySchemes", {})
        for name, scheme in sec_schemes.items():
            auth["mechanisms"].append({
                "name": name,
                "type": scheme.get("type", "unknown"),
                "scheme": scheme.get("scheme", "unknown")
            })
            
        for ep in normalized:
            if ep["authentication"] == "AUTH_REQUIRED":
                auth["protected_endpoints"].append(f"{ep['method']} {ep['path']}")
                
            if ep["method"] == "POST" and any(term in ep["path"].lower() for term in ["login", "token", "auth", "register"]):
                auth["login_endpoints"].append(f"{ep['method']} {ep['path']}")
                
        return auth

    def _probe_endpoints(self, normalized: list):
        probes = []
        for ep in normalized:
            # Only probe safe GET endpoints without path params
            if ep["method"] == "GET" and "{" not in ep["path"]:
                url = urljoin(self.service_url + "/", ep["path"].lstrip("/"))
                try:
                    start_time = time.time()
                    resp = requests.get(url, timeout=3)
                    latency = (time.time() - start_time) * 1000
                    
                    probes.append({
                        "endpoint": f"GET {ep['path']}",
                        "observed": {
                            "status": resp.status_code,
                            "latency_ms": round(latency, 2),
                            "content_type": resp.headers.get("Content-Type", ""),
                            "response_shape": "object" if str(resp.text).strip().startswith("{") else ("array" if str(resp.text).strip().startswith("[") else "other")
                        }
                    })
                except Exception as e:
                    probes.append({
                        "endpoint": f"GET {ep['path']}",
                        "observed": {"error": str(e)}
                    })
        return probes
