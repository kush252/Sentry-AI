# Sentry AI: Autonomous Observability Agent

Sentry is an intelligent, LangGraph-based AI agent designed to autonomously diagnose, investigate, and discover root causes of application failures, specifically targeting services deployed on Render. It bridges the gap between passive log analysis and active synthetic testing.

## 🚀 Features

- **Autonomous Troubleshooting**: Analyzes deterministic deployment signals, build logs, and runtime logs to find the root cause of failures.
- **Active Investigation Planner**: When passive logs don't reveal obvious issues, the agent actively discovers backend API endpoints and autonomously plans and executes deterministic tests to find hidden bugs.
- **Iterative Tool Execution**: Can dynamically use tools to fetch files from GitHub, compare commit differences, and fetch log history.
- **Strict Verification**: Contains a dedicated verifier node to ensure the proposed root cause matches the collected deterministic evidence.
- **Closed-Loop Remediation**: Once a root cause is verified, the agent formulates a patch, commits and pushes the resolution upstream to the origin repository, and automatically triggers a CI/CD pipeline redeployment to self-heal the production environment.
- **Smart Context Management**: Uses context truncation to fit within LLM token limits while safely archiving raw JSON lines (`investigation_data.jsonl`) for detailed manual review.

## 🛠️ Tech Stack

- **[Python](https://www.python.org/)**: The core programming language.
- **[LangGraph](https://python.langchain.com/docs/langgraph/)**: Used to model the agent's workflow as a cyclical state machine.
- **[LangChain](https://www.langchain.com/)**: For structured LLM outputs, message handling, and prompt construction.
- **LLM Providers**:
  - **[Google GenAI (Gemini)](https://ai.google.dev/)**: Used as the primary reasoning engine (`gemini-2.5-flash`).
  - **[Groq](https://groq.com/)**: Supported for fast, deterministic open-source model inference.
- **[Requests](https://pypi.org/project/requests/)**: To interact with the Render API, GitHub API, and run active investigation tests.
- **[python-dotenv](https://pypi.org/project/python-dotenv/)**: For managing API keys safely.

## 🧠 How the Planner & Workflow Works

The core of Sentry is built on LangGraph using a robust state machine (`SentryState`). The workflow operates in multiple distinct phases:

### 1. Initialization and Triage
- The entry point is `run_sentry.py`, which pulls initial telemetry (signals and evidence) from the Render API for a target service.
- The state graph starts at the **`triage_node`**. The Triage LLM acts as a strict router to determine if there is an obvious domain failure (e.g., `BUILD_DEPLOYMENT`, `RUNTIME_APPLICATION`) based on immediate evidence.

### 2. Active Investigation (When No Obvious Issue is Found)
If Triage determines `NO_OBVIOUS_ISSUE`, the system transitions into an active probing mode:
- **`backend_discovery_node`**: Pings the service to sniff out available API routes and constructs a logical "Backend Snapshot".
- **`active_investigation_planner_node`**: Formulates a targeted test plan based on the discovered API structure, specifically targeting unknown or core workflows.
- **`test_execution_node`**: Deterministically executes the planned HTTP tests against the live service.
- **`result_analyzer_node`**: Analyzes test results. If a test fails, the agent flags an active issue and routes the workflow into the core Investigator loop.

### 3. The Investigator Loop
If an issue is found (either directly via Triage or indirectly via the Active Investigation), the state moves to the **`investigator_node`**:
- The Investigator reviews the current "Evidence History" and hypotheses. 
- If the evidence is insufficient, it requests the use of specific deterministic tools (`get_build_logs`, `get_runtime_logs`, `get_file`, `get_commit_diff`).
- The **`tool_executor_node`** executes these actions.
- This loops back and forth until the Investigator reaches a confident `ROOT_CAUSE_READY` status or hits a safety iteration limit (`MAX_ITERS`).

### 4. Verification and Final Report
- **`verifier_node`**: A strict separate LLM instance that validates if the collected evidence *actually* supports the candidate root cause proposed by the Investigator.
- **`final_report_node`**: Compiles the findings, whether it be a verified root cause, an insufficient evidence warning, or an "All Clear" from active investigations, presenting it cleanly to the user.

### 5. Automated Remediation & CI/CD Re-integration
Upon generation of a verified root cause report, the system executes a closed-loop self-healing sequence:
- **Patch Generation**: Synthesizes a deterministic code fix or configuration adjustment to resolve the identified defect.
- **VCS Integration**: Commits the remediating changes and pushes them to the upstream Git repository via standard version control protocols.
- **Production Redeployment**: Invokes the hosting platform's (e.g., Render) deployment webhook to initiate a new rollout, subsequently monitoring the deployment signals to ensure full service restoration.

## 📦 Installation & Setup

1. **Clone the repository.**
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure Environment Variables:**
   Create a `.env` file in the root directory and add your required API keys (e.g., `RENDER_API_KEY`, `GITHUB_TOKEN`, `GEMINI_API_KEY`).
4. **Run Sentry:**
   ```bash
   python run_sentry.py --url https://your-service.onrender.com
   # OR
   python run_sentry.py --service-id srv-cabc1234defg
   ```
