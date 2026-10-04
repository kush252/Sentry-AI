from langgraph.graph import StateGraph, END
from src.agent.state import SentryState
from src.agent.nodes import (
    triage_node, 
    investigator_node, 
    tool_executor_node, 
    verifier_node, 
    final_report_node,
    backend_discovery_node,
    active_investigation_planner_node,
    test_execution_node,
    test_result_aggregator_node,
    result_analyzer_node
)
from src.agent.router import (
    route_triage, 
    route_investigator, 
    route_verifier,
    route_analyzer
)

def build_sentry_graph():
    workflow = StateGraph(SentryState)
    
    # 1. Add all nodes
    workflow.add_node("triage", triage_node)
    workflow.add_node("investigator", investigator_node)
    workflow.add_node("tool_executor", tool_executor_node)
    workflow.add_node("verifier", verifier_node)
    workflow.add_node("final_report", final_report_node)
    workflow.add_node("backend_discovery", backend_discovery_node)
    workflow.add_node("active_investigation_planner", active_investigation_planner_node)
    workflow.add_node("test_execution", test_execution_node)
    workflow.add_node("test_result_aggregator", test_result_aggregator_node)
    workflow.add_node("result_analyzer", result_analyzer_node)
    
    # Custom node for handling iteration limit failures smoothly
    def insufficient_evidence_node(state: SentryState) -> SentryState:
        return {"next_route": "INSUFFICIENT_EVIDENCE", "messages": [("system", "Iteration limit reached. Force routing to INSUFFICIENT_EVIDENCE.")]}
    
    workflow.add_node("insufficient_evidence", insufficient_evidence_node)
    
    # 2. Set entry
    workflow.set_entry_point("triage")
    
    # 3. Add Edges
    workflow.add_conditional_edges(
        "triage",
        route_triage,
        {
            "final_report": "final_report",
            "backend_discovery": "backend_discovery",
            "investigator": "investigator"
        }
    )
    
    workflow.add_conditional_edges(
        "investigator",
        route_investigator,
        {
            "verifier": "verifier",
            "tool_executor": "tool_executor",
            "insufficient_evidence": "insufficient_evidence"
        }
    )
    
    workflow.add_edge("tool_executor", "investigator")
    
    workflow.add_conditional_edges(
        "verifier",
        route_verifier,
        {
            "final_report": "final_report",
            "investigator": "investigator",
            "insufficient_evidence": "insufficient_evidence"
        }
    )
    
    workflow.add_edge("insufficient_evidence", "final_report")
    workflow.add_edge("backend_discovery", "active_investigation_planner")
    workflow.add_edge("active_investigation_planner", "test_execution")
    workflow.add_edge("test_execution", "test_result_aggregator")
    workflow.add_edge("test_result_aggregator", "result_analyzer")
    
    workflow.add_conditional_edges(
        "result_analyzer",
        route_analyzer,
        {
            "investigator": "investigator",
            "final_report": "final_report"
        }
    )
    
    workflow.add_edge("final_report", END)
    
    return workflow.compile()
