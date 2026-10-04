import traceback
from typing import Any, List, Optional
from pydantic import BaseModel, Field
from src.agent.state import SentryState
from src.llm.llm_factory import get_llm
from langchain_core.messages import SystemMessage, HumanMessage

from src.agent.schemas import TriageOutput, InvestigatorOutput, VerifierOutput, BackendSnapshot, ActiveTestPlan, ResultAnalyzerOutput
from src.tools.live_discovery import BackendDiscoveryTool
from src.tools.test_execution import TestExecutor

# --- Nodes ---

def triage_node(state: SentryState) -> SentryState:
    llm = get_llm("gemini-2.5-flash")
    structured_llm = llm.with_structured_output(TriageOutput)
    
    signals = state.get("signals", {})
    evidence = state.get("observation", {}).get("signal_evidence", {})
    if not evidence and "signal_evidence" in state:
        evidence = state["signal_evidence"]
    
    system_prompt = """You are a Triage Router for a Sentry/Observability agent.
Your job is ONLY to select exactly ONE investigation domain based on the deterministic signals and evidence.
Do NOT attempt to investigate or find the root cause."""

    import json
    human_prompt = f"Signals: {json.dumps(signals)}\nEvidence: {json.dumps(evidence)}\nWhich domain?"
    
    response = structured_llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)])
    
    if response:
        route = response.route
        reason = response.reason
    else:
        route = "INSUFFICIENT_EVIDENCE"
        reason = "Failed to parse structured output"
    
    valid_routes = [
        "BUILD_DEPLOYMENT", "CONFIGURATION_ENVIRONMENT", "RUNTIME_APPLICATION", 
        "AVAILABILITY_HTTP", "RESOURCE_PERFORMANCE", "DATABASE_EXTERNAL_DEPENDENCY",
        "NO_OBVIOUS_ISSUE", "INSUFFICIENT_EVIDENCE"
    ]
    if route not in valid_routes:
        route = "INSUFFICIENT_EVIDENCE"
        
    return {
        "next_route": route, 
        "messages": [("ai", f"Triage decision: Routing to {route} (Reason: {reason})")],
        "investigation_iterations": 0
    }

def investigator_node(state: SentryState) -> SentryState:
    llm = get_llm("gemini-2.5-flash")
    structured_llm = llm.with_structured_output(InvestigatorOutput)
    
    route = state.get("next_route", "UNKNOWN")
    evidence_history = state.get("evidence_history", [])
    signals = state.get("signals", {})
    
    system_prompt = f"""You are an Investigator for the {route} domain.
Your goal is to determine the root cause of the failure using evidence.

AVAILABLE TOOLS:
- get_build_logs: Retrieves raw build logs.
- get_runtime_logs: Retrieves raw application logs.
- get_file: Reads a file from GitHub (args: filepath).
- get_commit_diff: Reads recent code changes.

What is currently known? Look at the evidence_history.
If evidence is insufficient to confidently state a root cause, you MUST request a tool.
If evidence is sufficient, state the candidate root cause."""

    import json
    human_prompt = f"Route: {route}\nSignals: {json.dumps(signals)}\nEvidence History: {json.dumps(evidence_history)}\nWhat is the status?"
    
    response = structured_llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)])
    
    if response:
        status = response.status
        hypothesis = response.hypothesis
        
        # Convert Pydantic ToolRequest to dict for state compatibility
        tool_request = {}
        if response.tool_request:
            tool_request = {
                "tool": response.tool_request.tool,
                "arguments": response.tool_request.arguments
            }
            
        root_cause = response.candidate_root_cause
    else:
        status = "NEED_MORE_EVIDENCE"
        hypothesis = "Failed to parse output"
        tool_request = {}
        root_cause = ""
    
    return {
        "status": status,
        "tool_request": tool_request,
        "current_hypothesis": hypothesis,
        "hypotheses": [hypothesis] if hypothesis else [],
        "candidate_root_cause": root_cause,
        "messages": [("ai", f"Investigator ({status}): {hypothesis}")]
    }

def tool_executor_node(state: SentryState) -> SentryState:
    """A deterministic node to execute requested tools."""
    import json
    from src.proj_context.git_tools import GitHubAPIClient
    
    tool_req = state.get("tool_request", {})
    tool_name = tool_req.get("tool", "unknown_tool")
    args = tool_req.get("arguments", {})
    
    observation = state.get("observation", {})
    repo_url = observation.get("service", {}).get("repo", "")
    
    result = ""
    
    try:
        if tool_name == "get_file":
            filepath = args.get("filepath", "")
            if not repo_url:
                result = "Error: No repository URL found in observation to fetch from GitHub."
            else:
                client = GitHubAPIClient()
                content = client.get_file_content(repo_url, filepath)
                result = f"File {filepath} content:\n{content}"
                
        elif tool_name == "get_commit_diff":
            if not repo_url:
                result = "Error: No repository URL found in observation."
            else:
                client = GitHubAPIClient()
                latest_deploy = observation.get("deployment", {}).get("latest", {})
                commit_sha = latest_deploy.get("commit")
                if not commit_sha:
                    commit_sha = "HEAD"
                # Compare against the previous commit
                diff_data = client.get_commit_differences(repo_url, f"{commit_sha}~1", commit_sha)
                files = diff_data.get("files", [])
                diff_texts = [f"File: {f.get('filename')}\n{f.get('patch', '')}" for f in files]
                result = "Commit Diff:\n" + "\n".join(diff_texts)
                
        elif tool_name == "get_build_logs":
            logs = observation.get("build", {}).get("logs", [])
            log_texts = [l.get("message", l.get("text", str(l))) if isinstance(l, dict) else str(l) for l in logs]
            result = "Build Logs:\n" + "\n".join(log_texts)
            
        elif tool_name == "get_runtime_logs":
            logs = observation.get("runtime", {}).get("logs", [])
            log_texts = [l.get("message", l.get("text", str(l))) if isinstance(l, dict) else str(l) for l in logs]
            result = "Runtime Logs:\n" + "\n".join(log_texts)
            
        else:
            result = f"Error: Tool '{tool_name}' is not recognized or available."
            
    except Exception as e:
        result = f"Tool Execution Error ({tool_name}): {str(e)}\n{traceback.format_exc()}"
        
    # Store raw full output locally to JSON so we don't lose data, but keep LLM context clean
    with open("investigation_data.jsonl", "a", encoding="utf-8") as f:
        json.dump({"tool": tool_name, "args": args, "raw_result": result}, f)
        f.write("\n")
        
    # Smart truncation for the LLM to save tokens and prevent context overflow
    max_len = 2500
    if len(result) > max_len:
        # Keep start and end of the string (usually where the most important errors are)
        summarized_result = result[:1000] + f"\n\n...[TRUNCATED {len(result)-2000} chars. Full text saved to investigation_data.jsonl]...\n\n" + result[-1000:]
    else:
        summarized_result = result

    iters = state.get("investigation_iterations", 0) + 1
    
    return {
        "evidence_history": [f"Action: {tool_name}({args})\nResult:\n{summarized_result}"],
        "investigation_iterations": iters,
        "messages": [("system", f"Tool executed: {tool_name}")]
    }

def verifier_node(state: SentryState) -> SentryState:
    llm = get_llm("gemini-2.5-flash")
    structured_llm = llm.with_structured_output(VerifierOutput)
    
    root_cause = state.get("candidate_root_cause", "")
    evidence_history = state.get("evidence_history", [])
    
    system_prompt = """You are a strict Verifier.
Does the collected evidence actually support this proposed root cause? Do NOT invent evidence."""

    import json
    human_prompt = f"Candidate Root Cause: {root_cause}\nEvidence: {json.dumps(evidence_history)}\nIs it verified?"
    
    response = structured_llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)])
    
    if response:
        verified = response.verified
        summary = response.verification_summary
    else:
        verified = False
        summary = "Failed to parse structured output"
    
    return {
        "verification_result": verified,
        "messages": [("ai", f"Verifier decision: Verified={verified}. Summary: {summary}")]
    }

def final_report_node(state: SentryState) -> SentryState:
    route = state.get("next_route", "UNKNOWN")
    verified = state.get("verification_result", False)
    root_cause = state.get("candidate_root_cause", "None found")
    active_summary = state.get("active_investigation_summary", {})
    
    if route == "NO_OBVIOUS_ISSUE" and active_summary:
        report = (
            "Passive deployment analysis found no obvious issue.\n\n"
            "Active investigation:\n"
            f"- {active_summary.get('tests_planned')} tests planned\n"
            f"- {active_summary.get('tests_executed')} tests executed\n"
            f"- {active_summary.get('tests_passed')} tests passed\n"
            f"- {active_summary.get('tests_failed')} tests failed\n\n"
            "No reproducible application failure was observed.\n"
        )
    elif route == "NO_OBVIOUS_ISSUE":
        report = "Final Report: No obvious production issues detected."
    elif route == "INSUFFICIENT_EVIDENCE":
        report = "Final Report: Insufficient evidence to confidently diagnose the issue."
    else:
        report = f"Final Report\nDomain: {route}\nVerified: {verified}\nRoot Cause: {root_cause}"
        
    return {
        "final_report": report,
        "messages": [("ai", report)]
    }

def backend_discovery_node(state: SentryState) -> SentryState:
    llm = get_llm("gemini-2.5-flash")
    structured_llm = llm.with_structured_output(BackendSnapshot)
    
    observation = state.get("observation", {})
    service_url = observation.get("service", {}).get("url", "")
    if not service_url:
        return {"messages": [("ai", "Backend Discovery failed: No service_url found.")]}
        
    discovery_tool = BackendDiscoveryTool(service_url)
    raw_discovery = discovery_tool.run_discovery()
    
    system_prompt = """You are the Backend Understanding agent.
Your job is to read raw deterministic discovery data and construct a structured, compact Backend Snapshot.
Group endpoints logically into resources, infer relationships and workflows, identify unknowns, and assess confidence.
Do NOT invent endpoints that were not discovered."""

    import json
    human_prompt = f"Raw Discovery Data:\n{json.dumps(raw_discovery, indent=2)}\n\nBuild the BackendSnapshot."
    
    response = structured_llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)])
    
    if response:
        snapshot = response.dict()
    else:
        snapshot = {}
        
    return {
        "backend_context": snapshot,
        "messages": [("ai", "Backend Discovery completed. Snapshot generated.")]
    }

def active_investigation_planner_node(state: SentryState) -> SentryState:
    llm = get_llm("gemini-2.5-flash")
    structured_llm = llm.with_structured_output(ActiveTestPlan)
    
    context = state.get("backend_context", {})
    if not context:
        return {"messages": [("ai", "Test Planning failed: No Backend Context found.")]}
        
    system_prompt = """You are the Active Investigation Planner.
Your job is to read the Backend Snapshot created by the Discovery Node and formulate a targeted test plan.
You do NOT run the tests yourself. You just plan them.
Focus your tests on the 'candidate_workflows', 'unknowns', and any discrepancies found during discovery.
Do NOT invent tests for endpoints that do not exist in the snapshot."""

    import json
    human_prompt = f"Backend Snapshot:\n{json.dumps(context, indent=2)}\n\nGenerate the Active Test Plan."
    
    response = structured_llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)])
    
    if response:
        plan = response.dict()
    else:
        plan = {}
        
    return {
        "test_plan": plan,
        "messages": [("ai", f"Active Test Plan created with {len(plan.get('tests_to_run', []))} tests.\nRationale: {plan.get('rationale', '')}")]
    }

def test_execution_node(state: SentryState) -> SentryState:
    test_plan = state.get("test_plan", {})
    context = state.get("backend_context", {})
    observation = state.get("observation", {})
    service_url = observation.get("service", {}).get("url", "")
    
    if not service_url or not test_plan:
        return {"messages": [("system", "Test Execution skipped: Missing URL or Test Plan.")]}
        
    executor = TestExecutor(service_url, context)
    tests = test_plan.get("tests_to_run", [])
    
    results = []
    for test in tests:
        res = executor.run_test(test)
        results.append(res)
        
    return {
        "test_results": results,
        "messages": [("system", f"Executed {len(results)} tests deterministically.")]
    }

def test_result_aggregator_node(state: SentryState) -> SentryState:
    results = state.get("test_results", [])
    
    planned = len(state.get("test_plan", {}).get("tests_to_run", []))
    executed = len(results)
    passed = sum(1 for r in results if r.get("status") == "PASS")
    failed = sum(1 for r in results if r.get("status") in ["FAIL", "ERROR"])
    skipped = sum(1 for r in results if r.get("status") == "SKIPPED")
    inconclusive = sum(1 for r in results if r.get("status") == "INCONCLUSIVE")
    
    summary = {
        "tests_planned": planned,
        "tests_executed": executed,
        "tests_passed": passed,
        "tests_failed": failed,
        "tests_skipped": skipped,
        "tests_inconclusive": inconclusive,
        "overall_status": "ISSUES_FOUND" if failed > 0 else "NO_ISSUES"
    }
    
    return {
        "active_investigation_summary": summary,
        "messages": [("system", f"Aggregated results: {passed} passed, {failed} failed.")]
    }

def result_analyzer_node(state: SentryState) -> SentryState:
    llm = get_llm("gemini-2.5-flash")
    structured_llm = llm.with_structured_output(ResultAnalyzerOutput)
    
    context = state.get("backend_context", {})
    plan = state.get("test_plan", {})
    results = state.get("test_results", [])
    
    system_prompt = """You are the Result Analyzer.
Analyze the Backend Context, Test Plan, and raw Test Results.
Did any test actually fail? Distinguish between observed failures and possible explanations.
Do not invent root causes. Answer whether an issue was found and provide a summary."""

    import json
    # Truncate aggressively to fit inside Groq's 8K token per minute limit!
    plan_str = json.dumps(plan)[:1500]
    results_str = json.dumps(results)[:5000]
    human_prompt = f"Context:\n{json.dumps(context)[:1500]}\nPlan:\n{plan_str}\nResults:\n{results_str}\nAnalyze."
    
    response = structured_llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)])
    
    if response:
        issue_found = response.issue_found
        analyzer_summary = response.analyzer_summary
        
        if issue_found:
            return {
                "issue_found": True,
                "analyzer_summary": analyzer_summary,
                "next_route": "RUNTIME_APPLICATION",
                "evidence_history": [f"Active investigation found an issue: {analyzer_summary}"],
                "messages": [("ai", f"Analyzer: Issue Found. {analyzer_summary}")]
            }
        else:
            return {
                "issue_found": False,
                "analyzer_summary": analyzer_summary,
                "messages": [("ai", f"Analyzer: No Issue Found. {analyzer_summary}")]
            }
    else:
        return {"issue_found": False, "analyzer_summary": "Failed to parse analyzer output", "messages": [("ai", "Analyzer failed to parse.")]}
