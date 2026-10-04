from src.agent.state import SentryState

def route_triage(state: SentryState) -> str:
    route = state.get("next_route", "INSUFFICIENT_EVIDENCE")
    if route == "NO_OBVIOUS_ISSUE":
        return "backend_discovery"
    if route == "INSUFFICIENT_EVIDENCE":
        return "final_report"
    return "investigator"

def route_investigator(state: SentryState) -> str:
    status = state.get("status", "NEED_MORE_EVIDENCE")
    iters = state.get("investigation_iterations", 0)
    MAX_ITERS = 5
    
    if status == "ROOT_CAUSE_READY":
        return "verifier"
    
    if iters >= MAX_ITERS:
        return "insufficient_evidence" 
        
    return "tool_executor"

def route_verifier(state: SentryState) -> str:
    verified = state.get("verification_result", False)
    iters = state.get("investigation_iterations", 0)
    MAX_ITERS = 5
    
    if verified:
        return "final_report"
    else:
        if iters >= MAX_ITERS:
            return "insufficient_evidence"
        return "investigator"

def route_analyzer(state: SentryState) -> str:
    if state.get("issue_found", False):
        return "investigator"
    return "final_report"
