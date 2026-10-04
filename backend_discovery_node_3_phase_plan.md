Below is the plan I would give to an LLM/code-generation agent. I have split it into exactly three phases, with the end goal being a `Backend Discovery Node` that produces a compact, persistent backend context for the later Active Investigation/Test Planner.

# Backend Discovery Node — 3-Phase Implementation Plan

## Objective

Build a deterministic-first `Backend Discovery Node` for the Sentry LangGraph system.

The node is entered when Triage determines:

```text
NO_OBVIOUS_ISSUE
```

Its purpose is **not to diagnose an error and not to generate tests yet**.

Its purpose is to understand the deployed backend through its live Render URL, construct a compact `Backend Snapshot`, and store enough structured context for a later LLM to intelligently plan active investigation tests.

The system should follow this principle:

```text
Render URL
    ↓
Live Backend Discovery
    ↓
Structured Backend Snapshot
    ↓
LLM Backend Understanding
    ↓
Persistent Context
    ↓
Active Investigation Test Planner
```

Do NOT begin by reading the entire GitHub repository.

GitHub should be a secondary, targeted source of evidence only when live discovery cannot answer something or when a later investigation needs implementation-level context.

---

# Phase 1 — Live Backend Discovery

## Goal

Understand what the deployed service exposes without requiring the LLM to inspect the repository.

The discovery layer should be primarily deterministic.

### 1. Input

The node should receive the existing Sentry state containing, where available:

```text
service_id
service_name
service_url
deployment_id
deployment_status
repository_url
branch
commit
existing observations
```

The primary input for backend discovery should be:

```text
service_url
```

The Render API should provide additional service/deployment metadata.

---

## 2. Service Information Discovery

Create a deterministic tool such as:

```text
render_service_info
```

Collect:

```text
service name
service ID
service URL
deployment status
deployment ID
current commit
branch
repository
deployment timestamp
service type
environment information that is safe to expose
```

Also perform a basic availability check against the deployed URL.

Record:

```text
reachable
HTTP status
latency
redirects
TLS status
response headers
```

Do not treat a successful homepage response as proof that the backend is healthy.

This is only initial service discovery.

---

## 3. API Specification Discovery

The first major discovery mechanism should be OpenAPI/Swagger.

Try a small deterministic set of common locations:

```text
/openapi.json
/swagger.json
/api/openapi.json
/v1/openapi.json
/docs
/redoc
```

Do not ask the LLM to browse or interpret the documentation.

The tool should directly retrieve machine-readable API specifications where available.

Record:

```text
specification found
specification URL
OpenAPI version
API title
API version
number of paths
number of operations
schemas
security schemes
```

If OpenAPI is found:

```text
OpenAPI → parse → normalize
```

If OpenAPI is not found:

```text
OpenAPI unavailable
        ↓
fallback discovery
```

---

## 4. Normalize the API Specification

Do not send the raw OpenAPI document to the LLM.

Convert it into a compact representation containing:

```text
endpoint
HTTP method
path parameters
query parameters
request body schema
response schema
expected status codes
authentication requirement
tags/resource
```

Example:

```json
{
  "method": "POST",
  "path": "/tasks",
  "resource": "tasks",
  "authentication": "required",
  "request_schema": {
    "title": "string",
    "description": "string",
    "user_id": "integer"
  },
  "responses": {
    "201": "Task",
    "400": "ValidationError",
    "401": "Unauthorized"
  }
}
```

This normalized representation becomes part of the backend context.

---

## 5. Endpoint Classification

Classify every discovered endpoint as:

```text
PUBLIC
AUTH_REQUIRED
UNKNOWN
```

Use deterministic evidence:

```text
OpenAPI security definitions
401 responses
403 responses
WWW-Authenticate
known authentication endpoints
```

Do not assume that every undocumented endpoint is public.

---

## 6. Authentication Discovery

Identify authentication mechanisms from the deployed API.

Detect, where possible:

```text
Bearer/JWT
API key
Basic authentication
Cookie/session authentication
OAuth-related endpoints
unknown
```

Identify likely authentication endpoints:

```text
/login
/auth/login
/register
/auth/register
/token
/auth/token
```

Construct the authentication relationship:

```text
authentication endpoint
        ↓
credential/token
        ↓
authorization mechanism
        ↓
protected endpoints
```

Do not attempt to obtain or invent credentials.

If authentication cannot be exercised, record it as an explicit limitation.

---

## 7. Basic Endpoint Probing

After discovering endpoints, perform safe, low-impact probes.

The purpose is to compare:

```text
Declared behavior
        vs
Observed behavior
```

For safe endpoints, collect:

```text
HTTP status
latency
headers
content type
response structure
response schema
error structure
```

For example:

```json
{
  "endpoint": "GET /users",
  "observed": {
    "status": 200,
    "latency_ms": 142,
    "content_type": "application/json",
    "response_shape": "array"
  }
}
```

Do not perform destructive operations during discovery.

Do not automatically execute:

```text
DELETE
destructive POST
payment operations
account deletion
```

unless an explicit safe-test policy later authorizes them.

---

# Phase 2 — Backend Understanding and Context Construction

## Goal

Convert raw discovery results into a compact representation of how the deployed backend works.

This is where the LLM should be used.

The LLM should **reason over structured evidence**, not read the entire repository.

---

## 1. Build the Backend Snapshot

Create a canonical object:

```text
BackendSnapshot
```

It should contain at least:

```json
{
  "service": {},
  "runtime": {},
  "api": {},
  "resources": [],
  "endpoints": [],
  "authentication": {},
  "relationships": [],
  "dependencies": [],
  "observations": [],
  "unknowns": [],
  "limitations": [],
  "confidence": {}
}
```

---

## 2. Runtime Understanding

From Render metadata, response headers, deployment information, and safe observable signals, infer:

```text
framework
server
runtime
API style
versioning
```

Examples:

```text
FastAPI + Uvicorn
Flask
Django
Express
Spring
unknown
```

Do not claim a framework with certainty unless evidence supports it.

Use:

```text
observed
inferred
unknown
```

as appropriate.

---

## 3. Resource Mapping

Group endpoints into logical resources.

For example:

```text
/users
/users/{id}

/tasks
/tasks/{id}

/projects
/projects/{id}
```

becomes:

```text
users
    GET collection
    POST collection
    GET individual
    DELETE individual

tasks
    GET collection
    POST collection
    GET individual
    PUT individual
    DELETE individual
```

This gives the LLM a conceptual map rather than a flat list of URLs.

---

## 4. Identify Relationships

Use available API schemas and endpoint structures to infer relationships.

For example:

```text
User
  |
  └── Tasks
```

or:

```text
Project
  |
  ├── Users
  └── Tasks
```

Only record relationships when supported by evidence.

Mark uncertain relationships as:

```text
inferred
```

rather than factual.

---

## 5. Identify Application Workflows

The LLM should reason about possible workflows from the discovered API.

For example:

```text
login
  ↓
create user/resource
  ↓
retrieve resource
  ↓
update resource
  ↓
delete resource
```

or:

```text
authentication
  ↓
create task
  ↓
retrieve task
  ↓
update task
  ↓
delete task
```

These are **candidate workflows**, not tests yet.

The purpose is to give the future Test Planner enough context to decide what should actually be tested.

---

## 6. Compare Declared vs Observed Behavior

The LLM should receive:

```text
OpenAPI information
+
Endpoint observations
+
authentication observations
+
service metadata
```

and identify discrepancies such as:

```text
OpenAPI says 200
actual response = 500
```

or:

```text
endpoint documented
but unreachable
```

or:

```text
endpoint requires authentication
but authentication mechanism could not be established
```

These should become observations in the Backend Snapshot.

Do not immediately classify them as root causes.

---

## 7. Explicit Unknowns

This is extremely important.

The Backend Snapshot must explicitly state what the system does NOT know.

For example:

```json
{
  "unknowns": [
    "Authenticated workflows could not be executed",
    "Database implementation is unknown",
    "No OpenAPI specification was available",
    "DELETE endpoints were not probed because they are potentially destructive"
  ]
}
```

This prevents the later Test Planner from confusing:

```text
not observed
```

with:

```text
does not exist
```

---

## 8. Confidence Model

Every major part of the backend understanding should have a confidence level.

For example:

```json
{
  "confidence": {
    "endpoint_inventory": "HIGH",
    "authentication": "HIGH",
    "resource_relationships": "MEDIUM",
    "runtime": "MEDIUM",
    "workflow_understanding": "MEDIUM",
    "dependency_understanding": "LOW"
  }
}
```

The confidence should be based on evidence, not on the LLM's subjective confidence alone.

---

## 9. GitHub Must Remain Out of the Main Discovery Path

Do NOT do:

```text
Render URL
    ↓
clone repository
    ↓
read all files
    ↓
LLM summarizes repository
```

Instead:

```text
Render URL
    ↓
Live discovery
    ↓
Backend Snapshot
```

GitHub is only introduced later when:

```text
live evidence is insufficient
```

or:

```text
a concrete investigation question requires source code
```

For example:

```text
POST /tasks returns 500
        ↓
Investigator needs implementation
        ↓
Targeted GitHub retrieval
        ↓
Find POST /tasks implementation
        ↓
Find directly referenced service/model
```

Never retrieve the entire repository simply because GitHub is available.

---

# Phase 3 — Context Handoff to Active Investigation

## Goal

Leave the graph with a structured, persistent context that the next LLM can directly use to create an active testing strategy.

The Discovery Node should NOT itself decide all tests.

It should prepare the information required for the **Active Investigation Planner**.

---

## 1. Store Backend Context in LangGraph State

Add a dedicated state object:

```text
backend_context
```

containing:

```text
BackendSnapshot
```

The state should survive the transition:

```text
Backend Discovery
        ↓
Active Investigation Planner
```

The next node should not need to repeat discovery.

---

## 2. Recommended Context Structure

Use something approximately like:

```json
{
  "backend_context": {
    "service": {
      "name": "",
      "url": "",
      "deployment_id": "",
      "commit": ""
    },

    "runtime": {
      "framework": "",
      "server": "",
      "confidence": ""
    },

    "api": {
      "spec_found": true,
      "spec_url": "",
      "version": "",
      "total_endpoints": 0
    },

    "resources": [],

    "endpoints": [],

    "authentication": {
      "type": "",
      "login_endpoint": "",
      "protected_endpoints": [],
      "confidence": ""
    },

    "relationships": [],

    "candidate_workflows": [],

    "observations": [],

    "unknowns": [],

    "limitations": [],

    "confidence": {}
  }
}
```

Keep this compact.

The goal is to give the next LLM a **backend map**, not a transcript of every HTTP request.

---

## 3. Provide Evidence Alongside Conclusions

Do not store only:

```text
"authentication": "JWT"
```

Store the evidence:

```json
{
  "authentication": {
    "type": "JWT",
    "evidence": [
      "OpenAPI security scheme: bearerAuth",
      "GET /tasks declares bearerAuth"
    ],
    "confidence": "HIGH"
  }
}
```

Likewise:

```json
{
  "endpoint": "GET /tasks",
  "declared": {
    "authentication": "required",
    "response": "Task[]"
  },
  "observed": {
    "status": 401,
    "latency_ms": 120
  }
}
```

This allows the next LLM to reason from evidence rather than blindly trusting a previous LLM's summary.

---

## 4. Final Output of Discovery Node

The node should finish with:

```text
Backend Discovery Complete
        ↓
Backend Snapshot
        ↓
Backend Context stored in LangGraph State
        ↓
Ready for Active Investigation Planning
```

The output should answer:

```text
What service is this?
What framework/runtime does it appear to use?
What endpoints exist?
What resources exist?
What HTTP operations exist?
Which endpoints require authentication?
How does authentication appear to work?
What schemas are involved?
What relationships/workflows appear to exist?
What has actually been observed?
What discrepancies exist?
What remains unknown?
How confident are we?
```

It should NOT answer:

```text
What is the root cause?
```

and should NOT automatically answer:

```text
Which 20 tests should we run?
```

Those belong to the next stage.

---

# Final 3-Phase Architecture

```text
PHASE 1
LIVE DISCOVERY
────────────────────────────

Render Service
      ↓
Service Metadata
      ↓
OpenAPI Discovery
      ↓
Endpoint Discovery
      ↓
Authentication Discovery
      ↓
Safe Endpoint Probing
      ↓
Observed API Behavior


PHASE 2
BACKEND UNDERSTANDING
────────────────────────────

Discovery Results
      ↓
Normalize Evidence
      ↓
LLM Backend Understanding
      ↓
Resource Map
      ↓
Endpoint Map
      ↓
Authentication Model
      ↓
Relationships
      ↓
Candidate Workflows
      ↓
Observed vs Declared
      ↓
Unknowns + Limitations
      ↓
Confidence


PHASE 3
CONTEXT HANDOFF
────────────────────────────

Backend Snapshot
      ↓
Store in LangGraph State
      ↓
Compact Backend Context
      ↓
Active Investigation Planner
      ↓
LLM generates targeted test plan
      ↓
Deterministic Test Executor
```

The key architectural principle for implementation is:

> **Discovery tools collect facts. The Discovery LLM constructs the backend model. LangGraph preserves that model. The Test Planner uses the model to decide what to test. GitHub is queried only when a specific question cannot be answered from the deployed system.**

That keeps your system black-box-first, avoids stuffing large repositories into the LLM context, and gives the Active Investigation stage a structured representation of the application to reason over.
