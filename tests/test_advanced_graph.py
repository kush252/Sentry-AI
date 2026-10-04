import unittest
from unittest.mock import patch
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from src.agent.graph import build_sentry_graph
from src.agent.state import SentryState

class SimpleFakeChatModel(BaseChatModel):
    responses: list
    
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        resp = self.responses.pop(0) if self.responses else "{}"
        # Return a structure that mimics a chat model output
        return type("MockResult", (), {"generations": [[type("MockGen", (), {"message": AIMessage(content=resp)})()]]})()
        
    @property
    def _llm_type(self) -> str:
        return "fake"

    # Minimal implementation for invoke to bypass complex LangChain internals for basic tests
    def invoke(self, input, config=None, **kwargs):
        resp = self.responses.pop(0) if self.responses else "{}"
        return AIMessage(content=resp)


class TestAdvancedGraph(unittest.TestCase):
    def setUp(self):
        self.app = build_sentry_graph()

    def run_graph_with_mocked_llm(self, initial_state: dict, responses: list) -> dict:
        fake_llm = SimpleFakeChatModel(responses=responses)
        with patch("src.agent.nodes.get_llm", return_value=fake_llm):
            return self.app.invoke(initial_state)

    def test_1_build_failure(self):
        print("\n--- Test 1: Build Failure ---")
        state = {"signals": {"build_failure": True}, "observation": {"signal_evidence": {"build_failure": ["pip install failed"]}}}
        # Mock responses: 1. Triage, 2. Investigator, 3. Verifier
        responses = [
            '{"route": "BUILD_DEPLOYMENT", "reason": "pip failed", "supporting_signals": ["build_failure"]}',
            '{"status": "ROOT_CAUSE_READY", "candidate_root_cause": "Missing pip package"}',
            '{"verified": true, "verification_summary": "Package missing confirmed."}'
        ]
        final = self.run_graph_with_mocked_llm(state, responses)
        self.assertEqual(final["next_route"], "BUILD_DEPLOYMENT")
        self.assertTrue("Missing pip package" in final["final_report"])

    def test_2_runtime_traceback(self):
        print("\n--- Test 2: Runtime Traceback ---")
        state = {"signals": {"runtime_exception": True}, "observation": {"signal_evidence": {"runtime_exception": ["ModuleNotFoundError"]}}}
        responses = [
            '{"route": "RUNTIME_APPLICATION", "reason": "module not found"}',
            '{"status": "ROOT_CAUSE_READY", "candidate_root_cause": "Bad import"}',
            '{"verified": true}'
        ]
        final = self.run_graph_with_mocked_llm(state, responses)
        self.assertEqual(final["next_route"], "RUNTIME_APPLICATION")

    def test_3_investigation_loop_and_verifier_fail(self):
        print("\n--- Test 3: Investigation Loop & Verifier Reject ---")
        state = {"signals": {"http_errors": True}, "observation": {}}
        responses = [
            # 1. Triage
            '{"route": "AVAILABILITY_HTTP"}',
            # 2. Investigator (requests tool)
            '{"status": "NEED_MORE_EVIDENCE", "tool_request": {"tool": "get_runtime_logs"}}',
            # 3. Investigator (has evidence, makes root cause)
            '{"status": "ROOT_CAUSE_READY", "candidate_root_cause": "Server timeout"}',
            # 4. Verifier (rejects it!)
            '{"verified": false, "verification_summary": "No evidence of timeout"}',
            # 5. Investigator (requests tool again)
            '{"status": "NEED_MORE_EVIDENCE", "tool_request": {"tool": "get_build_logs"}}',
            # 6. Investigator (makes new root cause)
            '{"status": "ROOT_CAUSE_READY", "candidate_root_cause": "Bad config"}',
            # 7. Verifier (accepts it!)
            '{"verified": true, "verification_summary": "Config is indeed bad"}'
        ]
        final = self.run_graph_with_mocked_llm(state, responses)
        
        # Verify it went through the iterations
        self.assertEqual(final["investigation_iterations"], 2) # Two tools executed
        self.assertEqual(final["verification_result"], True)
        self.assertTrue("Bad config" in final["final_report"])

    def test_4_insufficient_evidence(self):
        print("\n--- Test 4: Insufficient Evidence Iteration Limit ---")
        state = {"signals": {"database_error": True}, "observation": {}}
        responses = [
            # Triage
            '{"route": "DATABASE_EXTERNAL_DEPENDENCY"}'
        ]
        # Investigator asks for tools forever (over 5 times)
        responses.extend(['{"status": "NEED_MORE_EVIDENCE", "tool_request": {"tool": "get_runtime_logs"}}'] * 6)
        
        final = self.run_graph_with_mocked_llm(state, responses)
        # Should force route to INSUFFICIENT_EVIDENCE
        self.assertEqual(final["next_route"], "INSUFFICIENT_EVIDENCE")
        self.assertTrue("Insufficient evidence" in final["final_report"])
        
    def test_5_no_obvious_issue(self):
        print("\n--- Test 5: No Obvious Issue ---")
        state = {"signals": {}, "observation": {}}
        responses = [
            '{"route": "NO_OBVIOUS_ISSUE"}'
        ]
        final = self.run_graph_with_mocked_llm(state, responses)
        self.assertEqual(final["next_route"], "NO_OBVIOUS_ISSUE")
        self.assertTrue("No obvious production issues detected" in final["final_report"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
