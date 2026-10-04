from pydantic import BaseModel, Field
from typing import List, Optional

class TriageOutput(BaseModel):
    route: str = Field(
        description="Must be exactly one of: BUILD_DEPLOYMENT, CONFIGURATION_ENVIRONMENT, RUNTIME_APPLICATION, AVAILABILITY_HTTP, RESOURCE_PERFORMANCE, DATABASE_EXTERNAL_DEPENDENCY, NO_OBVIOUS_ISSUE, INSUFFICIENT_EVIDENCE"
    )
    reason: str = Field(description="Short explanation for the route selection")
    supporting_signals: List[str] = Field(description="List of signals that support this decision", default_factory=list)

class ToolRequest(BaseModel):
    tool: str = Field(description="The name of the tool to request")
    arguments: dict = Field(description="The arguments to pass to the tool", default_factory=dict)

class InvestigatorOutput(BaseModel):
    status: str = Field(description="Must be exactly 'NEED_MORE_EVIDENCE' or 'ROOT_CAUSE_READY'")
    hypothesis: str = Field(description="Your working theory")
    reasoning_summary: str = Field(description="Why you think this hypothesis is correct")
    required_evidence: List[str] = Field(description="What evidence is missing, if any", default_factory=list)
    tool_request: Optional[ToolRequest] = Field(description="The tool request if more evidence is needed", default=None)
    candidate_root_cause: str = Field(description="The final root cause (leave blank if NEED_MORE_EVIDENCE)", default="")

class VerifierOutput(BaseModel):
    verified: bool = Field(description="True if the collected evidence fully supports the proposed root cause, False otherwise")
    supporting_evidence: List[str] = Field(description="Evidence supporting the root cause", default_factory=list)
    contradicting_evidence: List[str] = Field(description="Evidence contradicting the root cause", default_factory=list)
    remaining_uncertainty: List[str] = Field(description="Any remaining uncertainty", default_factory=list)
    verification_summary: str = Field(description="Summary of the verification decision")

class BackendSnapshot(BaseModel):
    service: dict = Field(description="Service info like name, url, deployment_id, commit")
    runtime: dict = Field(description="Inferred framework, server, runtime")
    api: dict = Field(description="API spec metadata")
    resources: List[dict] = Field(description="Grouped endpoints into logical resources")
    endpoints: List[dict] = Field(description="Normalized endpoints")
    authentication: dict = Field(description="Authentication types, protected endpoints, login endpoints")
    relationships: List[str] = Field(description="Inferred resource relationships")
    candidate_workflows: List[str] = Field(description="Possible workflows (e.g. login -> create task)")
    observations: List[str] = Field(description="Discrepancies or notable behaviors observed")
    unknowns: List[str] = Field(description="Explicit statements of what is NOT known")
    limitations: List[str] = Field(description="Explicit limitations of the discovery")
    confidence: dict = Field(description="Confidence levels (HIGH/MEDIUM/LOW) for various aspects")

class ActiveTestPlan(BaseModel):
    rationale: str = Field(description="Why these tests were chosen based on the Backend Context")
    tests_to_run: List[dict] = Field(description="List of specific HTTP tests or probes to execute. Should include method, endpoint, and intent.")
    expected_findings: List[str] = Field(description="What you expect to learn from these tests")

class ResultAnalyzerOutput(BaseModel):
    issue_found: bool = Field(description="Did any test actually fail and indicate a real issue?")
    issue_reproducible: bool = Field(description="Is the failure reproducible based on evidence?")
    issue_type: str = Field(description="Application behavior, contract violation, performance, dependency, or None?")
    investigate_first: str = Field(description="Which finding should be investigated first? (Leave blank if none)")
    additional_evidence_required: str = Field(description="What additional evidence is needed?")
    analyzer_summary: str = Field(description="Summary of the analysis")
