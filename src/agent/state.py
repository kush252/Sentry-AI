from typing import TypedDict, Any, Dict, List, Optional
from typing import Annotated
import operator

class SentryState(TypedDict, total=False):
    observation: Dict[str, Any]
    signals: Dict[str, Any]
    signal_evidence: Dict[str, Any]
    messages: Annotated[List[Any], operator.add]
    
    next_route: str
    
    investigation_context: str
    evidence_history: Annotated[List[str], operator.add]
    hypotheses: Annotated[List[str], operator.add]
    current_hypothesis: str
    
    tool_request: Dict[str, Any]
    status: str
    candidate_root_cause: str
    
    evidence_sufficient: bool
    verification_result: bool
    investigation_iterations: int
    final_report: str
    backend_context: Dict[str, Any]
    test_plan: Dict[str, Any]
    test_results: List[Dict[str, Any]]
    active_investigation_summary: Dict[str, Any]
    issue_found: bool
    analyzer_summary: str
