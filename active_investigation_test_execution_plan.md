Yes. At this point, Phase 3 should produce a structured `test_plan`, and that should become the direct input to the test execution section shown in your diagram.

The important change is that `Select Test Type` should not independently decide what to run. The **Backend Understanding/Test Planner from Phase 3 has already selected the tests**. The executor simply translates that plan into tool calls, executes only the selected tests, aggregates their results, and passes the evidence into the existing investigation/final-report flow.

Below is a plan you can give directly to your coding LLM.

```markdown
# Active Investigation — Test Execution Integration Plan

## Objective

Connect the output of the Backend Discovery / Backend Understanding phase to the existing Active Investigation test execution section.

The system should work as:

Backend Discovery
    ↓
Backend Snapshot
    ↓
LLM Backend Understanding
    ↓
Test Plan Generator
    ↓
Selective Test Execution
    ↓
Test Result Aggregation
    ↓
Issue / No Issue
    ↓
Existing Investigator OR Final Report

The system must NOT execute every available test.

The Test Planner decides which tests are relevant based on the discovered backend. The executor only executes those selected tests.

The six available test categories are:

1. Endpoint Testing
2. API Contract Testing
3. Edge Case Testing
4. Synthetic User Flows
5. Performance Probe
6. Dependency Checks

---

# Phase 1 — Build the Deterministic Test Tools

Before modifying the LangGraph routing, implement the actual tools that can perform each type of test.

The tools should be deterministic execution components.

The LLM should decide WHAT to test, but the tools should decide HOW to execute the actual HTTP/network operation.

Do not allow the LLM to directly perform arbitrary requests.

---

## 1. Endpoint Testing Tool

Create a tool:

`endpoint_test`

Purpose:

Test a specific discovered endpoint using information from the Backend Snapshot.

Input should contain information such as:

```json
{
  "method": "GET",
  "path": "/users",
  "base_url": "https://...",
  "authentication": "required",
  "parameters": {},
  "request_body": null
}
```

The tool should execute the request and return structured evidence.

Example:

```json
{
  "test_type": "endpoint",
  "endpoint": "GET /users",
  "status": "PASS",
  "http_status": 200,
  "latency_ms": 143,
  "response_content_type": "application/json",
  "response_shape": "array",
  "errors": []
}
```

Do not return only a boolean.

The result must contain enough information for the Result Analyzer and Final Report.

---

## 2. API Contract Testing Tool

Create:

`contract_test`

Purpose:

Compare the discovered OpenAPI contract against actual endpoint behavior.

Check things such as:

- expected HTTP status
- response schema
- required parameters
- request schema
- response content type
- documented authentication requirements
- documented error responses

Example:

```json
{
  "test_type": "contract",
  "endpoint": "POST /tasks",
  "status": "FAIL",
  "violations": [
    {
      "type": "status_code",
      "expected": 201,
      "actual": 500
    }
  ]
}
```

The tool should use the normalized OpenAPI information already stored in `backend_context`.

Do not make the tool rediscover OpenAPI.

---

## 3. Edge Case Testing Tool

Create:

`edge_case_test`

Purpose:

Execute safe edge cases selected by the Test Planner.

The planner should provide the test cases.

For example:

```json
{
  "endpoint": "POST /tasks",
  "cases": [
    "missing required field",
    "empty title",
    "invalid user_id",
    "wrong field type"
  ]
}
```

The executor translates these into deterministic HTTP requests.

The tool should record:

```json
{
  "test_type": "edge_case",
  "endpoint": "POST /tasks",
  "cases_executed": 4,
  "results": [],
  "failures": []
}
```

Do not let the LLM dynamically generate and execute arbitrary payloads during execution.

---

## 4. Synthetic User Flow Tool

Create:

`synthetic_flow_test`

Purpose:

Test multi-step backend workflows.

Example:

```text
POST /auth/login
        ↓
obtain token
        ↓
POST /tasks
        ↓
GET /tasks/{id}
        ↓
PUT /tasks/{id}
        ↓
DELETE /tasks/{id}
```

The Test Planner should specify the workflow.

The executor should execute the workflow deterministically.

The tool must maintain temporary state between steps.

For example:

```json
{
  "workflow": "task_crud",
  "steps": [
    "login",
    "create_task",
    "get_task",
    "update_task",
    "delete_task"
  ]
}
```

Return the result of every step.

Example:

```json
{
  "test_type": "synthetic_flow",
  "workflow": "task_crud",
  "status": "FAIL",
  "failed_step": "update_task",
  "steps": []
}
```

Do not automatically execute destructive workflows unless the test plan explicitly marks them as safe/authorized.

---

## 5. Performance Probe Tool

Create:

`performance_probe`

Purpose:

Perform lightweight performance measurements.

This is NOT a load-testing system.

Initially keep it conservative.

Input:

```json
{
  "endpoint": "GET /tasks",
  "requests": 5,
  "timeout_seconds": 10
}
```

Measure:

- latency
- timeout count
- HTTP errors
- successful requests
- p50
- p95 where sample size permits
- maximum latency

Example:

```json
{
  "test_type": "performance",
  "endpoint": "GET /tasks",
  "requests": 5,
  "successful_requests": 5,
  "error_requests": 0,
  "p50_ms": 182,
  "p95_ms": 310,
  "max_ms": 344
}
```

Do not perform aggressive load testing.

---

## 6. Dependency Check Tool

Create:

`dependency_check`

Purpose:

Check externally observable dependencies identified during Backend Discovery.

Possible dependencies:

- PostgreSQL
- Redis
- external REST APIs
- object storage
- authentication providers
- other services

Do not attempt to directly connect to private infrastructure unless credentials and explicit access already exist.

Prefer checking dependency behavior through the deployed application's API.

For example:

```text
GET /health
        ↓
database connectivity

GET /tasks
        ↓
database-backed operation

POST /external-resource
        ↓
external API dependency
```

Return structured observations.

Example:

```json
{
  "test_type": "dependency",
  "dependency": "database",
  "status": "PASS",
  "evidence": {
    "endpoint": "GET /tasks",
    "http_status": 200,
    "latency_ms": 150
  }
}
```

---

# Phase 2 — Connect Test Planner to Selective Execution

Once the six tools exist, connect them to the output of Phase 3.

The Test Planner should consume:

```text
backend_context
```

and produce:

```text
test_plan
```

The `test_plan` must be structured JSON.

Do not allow the planner to return an unstructured paragraph.

---

## Test Plan Schema

Use a structure similar to:

```json
{
  "objective": "Validate the deployed backend after no obvious issue was found",

  "tests": [
    {
      "id": "test_001",
      "type": "endpoint",
      "target": "GET /tasks",
      "priority": "high",
      "reason": "Primary database-backed endpoint"
    },
    {
      "id": "test_002",
      "type": "contract",
      "target": "POST /tasks",
      "priority": "high",
      "reason": "OpenAPI contract available"
    },
    {
      "id": "test_003",
      "type": "edge_case",
      "target": "POST /tasks",
      "cases": [
        "missing title",
        "invalid user_id"
      ],
      "priority": "medium",
      "reason": "Input validation should be verified"
    }
  ]
}
```

The planner may select only a subset of the six test categories.

For example:

```text
Backend has:
- OpenAPI
- JWT authentication
- CRUD API
- PostgreSQL

Planner selects:
- endpoint
- contract
- edge_case
- synthetic_flow
```

It should not automatically run performance or dependency tests unless the backend context provides a reason.

---

## Test Selection Node

The existing:

`Select Test Type`

router should now operate on `test_plan.tests`.

It should NOT independently reason about what should be tested.

Its responsibility is:

```text
test_plan
    ↓
for each selected test
    ↓
route to corresponding executor
```

Conceptually:

```text
Test Plan
    |
    +---- type = endpoint ------> Endpoint Testing
    |
    +---- type = contract ------> Contract Testing
    |
    +---- type = edge_case -----> Edge Case Testing
    |
    +---- type = synthetic -----> Synthetic Flow
    |
    +---- type = performance ---> Performance Probe
    |
    +---- type = dependency ----> Dependency Check
```

---

# Phase 3 — Aggregate Results and Feed the Existing Graph

After executing the selected tests, do not immediately send each result independently to the Final Report.

Create a dedicated:

`Test Result Aggregator`

node.

Its purpose is to collect all test results into one structured investigation result.

---

## Test Result Schema

Every executor should return a common structure:

```json
{
  "test_id": "test_001",
  "test_type": "endpoint",
  "target": "GET /tasks",
  "status": "PASS",
  "severity": null,
  "evidence": {},
  "failures": [],
  "observations": [],
  "limitations": []
}
```

Possible statuses:

```text
PASS
FAIL
ERROR
SKIPPED
INCONCLUSIVE
```

Do not use only PASS/FAIL.

For example, an authenticated endpoint for which no credentials are available should be:

```text
SKIPPED
```

or:

```text
INCONCLUSIVE
```

not:

```text
PASS
```

---

# Result Aggregation

The aggregator should produce:

```json
{
  "active_investigation": {
    "tests_planned": 6,
    "tests_executed": 5,
    "tests_passed": 3,
    "tests_failed": 1,
    "tests_skipped": 1,

    "findings": [],

    "evidence": [],

    "limitations": [],

    "overall_status": "ISSUES_FOUND"
  }
}
```

The aggregator should preserve the raw results as well.

Do not throw away the individual test evidence.

---

# Result Analyzer

After aggregation, use an LLM Result Analyzer to interpret the evidence.

Input:

```text
Backend Context
+
Test Plan
+
Test Results
```

The analyzer should answer:

```text
1. Did any test actually fail?

2. Is the failure reproducible?

3. Is it an application behavior issue,
   contract violation, performance issue,
   dependency issue, or something else?

4. Is there enough evidence to investigate?

5. Which finding should be investigated first?

6. What additional evidence is required?
```

The analyzer must distinguish:

```text
observed failure
```

from:

```text
possible explanation
```

Do not allow it to invent root causes from a failed test.

---

# Connect Findings to the Existing Investigator

This is the key integration with the graph you already built.

Current path:

```text
Active Health Investigation
        ↓
Test Analyzer
        ↓
Issue Found?
```

Change this to:

```text
Active Health Investigation
        ↓
Backend Discovery
        ↓
Backend Understanding
        ↓
Test Planner
        ↓
Selective Test Execution
        ↓
Result Aggregator
        ↓
Result Analyzer
        ↓
Issue Found?
```

Then:

```text
Issue Found = YES
        ↓
Existing Investigator Node
        ↓
Route Investigator
        ↓
Targeted tools / GitHub retrieval / Render logs
        ↓
Verifier
```

This means the existing Investigator is reused rather than creating a second independent investigation system.

---

# No Issue Path

If all relevant tests pass and there is sufficient coverage:

```text
Result Analyzer
        ↓
NO ISSUE FOUND
        ↓
Final Report
```

The Final Report should receive:

```text
original deployment observations
+
triage result
+
backend snapshot
+
test plan
+
test execution results
+
test coverage
+
limitations
```

The report can then state something like:

```text
Passive deployment analysis found no obvious issue.

Active investigation:
- 14 endpoints discovered
- 9 safe endpoints tested
- 3 API contracts validated
- 2 edge-case groups tested
- 1 synthetic workflow tested
- 5 performance probes completed

No reproducible application failure was observed.

Limitations:
- Authenticated admin workflows could not be tested.
- Destructive operations were not executed.
```

This is much stronger than simply saying:

```text
No errors found.
```

---

# Updated Graph

The active branch should ultimately become:

```text
NO_OBVIOUS_ISSUE
        |
        v
Backend Discovery
        |
        v
Backend Understanding
        |
        v
Test Plan Generator (LLM)
        |
        v
Select Test Type
        |
   ┌────┼────┬────┬────┬────┐
   |    |    |    |    |    |
   v    v    v    v    v    v
Endpoint Contract Edge Synthetic Performance Dependency
   |    |    |    |    |    |
   └────┴────┴────┴────┴────┘
                 |
                 v
        Test Result Aggregator
                 |
                 v
          Result Analyzer
                 |
           ┌─────┴─────┐
           |           |
         ISSUE       NO ISSUE
           |           |
           v           v
     Investigator   Final Report
           |
           v
       Verifier
           |
           v
      Final Report
```

The most important implementation order is therefore:

```text
1. Build the six deterministic test tools.

2. Give every tool a common input/output contract.

3. Create the structured test_plan schema.

4. Connect the Backend Snapshot to the Test Planner.

5. Make the Test Planner select only relevant tests.

6. Route each selected test to its corresponding executor.

7. Aggregate all results.

8. Add the Result Analyzer.

9. Route ISSUE_FOUND back into the existing Investigator.

10. Route NO_ISSUE into the existing Final Report.

11. Include Backend Snapshot + Test Plan + Test Results + Limitations in Final Report.
```

This preserves the architecture you already have: the LLM performs reasoning and planning, while the actual interaction with the deployed application remains deterministic and controlled.
