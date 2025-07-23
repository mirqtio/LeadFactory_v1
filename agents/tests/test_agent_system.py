#!/usr/bin/env python3
"""
Comprehensive test suite for the agent system
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Mock the anthropic module before importing our modules
sys.modules["anthropic"] = MagicMock()

from agents.core.base_worker import AgentWorker
from agents.core.qa_orchestrator import QAOrchestrator
from agents.roles.integration_agent import IntegrationAgent
from agents.roles.pm_agent import PMAgent
from agents.roles.validator_agent import ValidatorAgent
from agents.tests.mock_claude_api import MockClaudeClient, MockRedisClient


class TestAgentWorker:
    """Test the base AgentWorker class"""

    def test_agent_initialization(self):
        """Test agent initialization"""
        with patch("agents.core.base_worker.redis.from_url", return_value=MockRedisClient()):
            with patch("agents.core.base_worker.Anthropic", return_value=MockClaudeClient()):
                agent = PMAgent("test-pm-1")

                assert agent.agent_id == "test-pm-1"
                assert agent.role == "pm"
                assert agent.queue == "pm_queue"
                assert agent.current_prp is None

    def test_evidence_extraction(self):
        """Test evidence extraction from response"""
        agent = PMAgent("test-pm-1")

        response = """
        Here's my implementation:
        
        ```json
        {"key": "tests_passed", "value": "true"}
        {"key": "coverage_pct", "value": "85"}
        ```
        
        And another block:
        ```json
        {"key": "lint_passed", "value": "true"}
        ```
        """

        evidence = agent.extract_evidence(response)

        assert evidence["tests_passed"] == "true"
        assert evidence["coverage_pct"] == "85"
        assert evidence["lint_passed"] == "true"

    def test_question_extraction(self):
        """Test question extraction from response"""
        agent = PMAgent("test-pm-1")

        response = """
        I'm working on the implementation.
        
        QUESTION: Should I use the singleton pattern or dependency injection?
        
        I need clarification on this.
        """

        question = agent.extract_question(response)
        assert question == "Should I use the singleton pattern or dependency injection?"

    def test_prp_processing_flow(self):
        """Test complete PRP processing flow"""
        mock_redis = MockRedisClient()
        mock_claude = MockClaudeClient(behavior="normal")

        with patch("redis.from_url", return_value=mock_redis):
            with patch("anthropic.Anthropic", return_value=mock_claude):
                agent = PMAgent("test-pm-1")

                # Setup PRP data
                prp_id = "P0-001"
                mock_redis.hset(
                    f"prp:{prp_id}",
                    {"id": prp_id, "title": "Test Feature", "content": "Implement a test feature", "priority": "high"},
                )

                # Process PRP
                agent.process_prp(prp_id)

                # Check evidence was saved
                assert mock_redis.hget(f"prp:{prp_id}", "tests_passed") == b"true"
                assert mock_redis.hget(f"prp:{prp_id}", "coverage_pct") == b"85"
                assert mock_redis.hget(f"prp:{prp_id}", "implementation_complete") == b"true"

    def test_qa_flow(self):
        """Test Q&A flow"""
        mock_redis = MockRedisClient()
        mock_claude = MockClaudeClient(behavior="qa_needed")

        with patch("redis.from_url", return_value=mock_redis):
            with patch("anthropic.Anthropic", return_value=mock_claude):
                agent = PMAgent("test-pm-1")

                # Setup PRP
                prp_id = "P0-002"
                mock_redis.hset(f"prp:{prp_id}", {"id": prp_id, "title": "Test with Q&A"})

                # Mock Q&A answer
                def mock_qa_handler(*args, **kwargs):
                    # Simulate Q&A delay
                    time.sleep(0.1)
                    # Set answer
                    qa_requests = mock_redis.lrange("qa_queue", 0, -1)
                    if qa_requests:
                        qa_data = json.loads(qa_requests[0])
                        qa_id = qa_data["id"]
                        mock_redis.set(f"qa_answer:{qa_id}", "Use dependency injection")

                # Patch handle_qa to simulate answer
                with patch.object(agent, "handle_qa", side_effect=mock_qa_handler):
                    response = mock_claude.create_message("", [], 8000)
                    result = agent.process_response(prp_id, response.content[0].text)

                    assert result["needs_qa"] == True
                    assert "singleton pattern" in result["question"]


class TestPMAgent:
    """Test PM Agent specific functionality"""

    def test_build_context(self):
        """Test PM context building"""
        mock_redis = MockRedisClient()

        with patch("redis.from_url", return_value=mock_redis):
            with patch("anthropic.Anthropic", return_value=MockClaudeClient()):
                agent = PMAgent("test-pm-1")

                prp_data = {
                    "id": "P0-003",
                    "title": "Add logging feature",
                    "content": "Add comprehensive logging to the system",
                    "priority": "medium",
                }

                context = agent.build_context("P0-003", prp_data)

                assert len(context["messages"]) == 2
                assert "senior software developer" in context["messages"][0]["content"]
                assert "P0-003" in context["messages"][1]["content"]
                assert "Add logging feature" in context["messages"][1]["content"]

    def test_completion_criteria(self):
        """Test PM completion criteria"""
        agent = PMAgent("test-pm-1")

        # Incomplete evidence
        evidence = {"tests_passed": "true", "coverage_pct": "85"}
        assert agent.check_completion_criteria("P0-001", evidence) == False

        # Complete evidence
        evidence["implementation_complete"] = "true"
        evidence["lint_passed"] = "true"
        assert agent.check_completion_criteria("P0-001", evidence) == True

        # Low coverage
        evidence["coverage_pct"] = "50"
        assert agent.check_completion_criteria("P0-001", evidence) == False


class TestValidatorAgent:
    """Test Validator Agent specific functionality"""

    def test_validation_passed(self):
        """Test successful validation"""
        mock_redis = MockRedisClient()
        mock_claude = MockClaudeClient(behavior="normal")

        with patch("redis.from_url", return_value=mock_redis):
            with patch("anthropic.Anthropic", return_value=mock_claude):
                agent = ValidatorAgent("test-validator-1")

                # Setup PRP with PM evidence
                prp_id = "P0-004"
                mock_redis.hset(
                    f"prp:{prp_id}",
                    {
                        "id": prp_id,
                        "title": "Feature to validate",
                        "tests_passed": "true",
                        "coverage_pct": "85",
                        "lint_passed": "true",
                        "modified_files": json.dumps(["feature.py", "test_feature.py"]),
                    },
                )

                # Process validation
                agent.process_prp(prp_id)

                # Check validation passed
                assert mock_redis.hget(f"prp:{prp_id}", "validation_passed") == b"true"
                assert mock_redis.hget(f"prp:{prp_id}", "quality_score") == b"92"

    def test_validation_failed(self):
        """Test failed validation"""
        mock_redis = MockRedisClient()

        with patch("redis.from_url", return_value=mock_redis):
            with patch("anthropic.Anthropic", return_value=MockClaudeClient()):
                agent = ValidatorAgent("test-validator-1")

                # Test failed validation criteria
                evidence = {
                    "validation_passed": "false",
                    "validation_issues": "Missing error handling",
                    "required_changes": "Add try-except blocks",
                }

                assert agent.check_completion_criteria("P0-005", evidence) == True

                # Check next queue for failed validation
                mock_redis.hset("prp:P0-005", {"validation_passed": "false"})
                agent.current_prp = "P0-005"
                assert agent.get_next_queue() == "dev_queue"


class TestIntegrationAgent:
    """Test Integration Agent specific functionality"""

    def test_successful_deployment(self):
        """Test successful deployment flow"""
        mock_redis = MockRedisClient()
        mock_claude = MockClaudeClient(behavior="normal")

        with patch("redis.from_url", return_value=mock_redis):
            with patch("anthropic.Anthropic", return_value=mock_claude):
                agent = IntegrationAgent("test-integrator-1")

                # Setup PRP
                prp_id = "P0-006"
                mock_redis.hset(
                    f"prp:{prp_id}",
                    {"id": prp_id, "title": "Deploy feature", "modified_files": json.dumps(["feature.py"])},
                )

                # Process deployment
                agent.process_prp(prp_id)

                # Check deployment success
                assert mock_redis.hget(f"prp:{prp_id}", "ci_passed") == b"true"
                assert mock_redis.hget(f"prp:{prp_id}", "deployed") == b"true"
                assert mock_redis.hget(f"prp:{prp_id}", "pr_number") == b"123"

    def test_deployment_failure(self):
        """Test deployment failure handling"""
        agent = IntegrationAgent("test-integrator-1")

        # Test failure criteria
        evidence = {"ci_passed": "false", "ci_failure_reason": "Tests failed in CI"}

        assert agent.check_completion_criteria("P0-007", evidence) == True
        assert agent.get_next_queue() is None  # Integration is final stage


class TestQAOrchestrator:
    """Test Q&A Orchestrator functionality"""

    def test_qa_processing(self):
        """Test Q&A request processing"""
        mock_redis = MockRedisClient()
        mock_claude = MockClaudeClient(behavior="normal")

        with patch("redis.from_url", return_value=mock_redis):
            with patch("anthropic.Anthropic", return_value=mock_claude):
                orchestrator = QAOrchestrator()

                # Create Q&A request
                qa_request = {
                    "id": "qa-test-001",
                    "agent": "test-pm-1",
                    "role": "pm",
                    "prp_id": "P0-008",
                    "question": "Should I use singleton pattern?",
                    "timestamp": datetime.utcnow().isoformat(),
                }

                # Process request
                orchestrator.process_qa_request(qa_request)

                # Check answer was stored
                answer = mock_redis.get("qa_answer:qa-test-001")
                assert answer is not None
                assert b"dependency injection" in answer

    def test_context_building(self):
        """Test Q&A context building"""
        mock_redis = MockRedisClient()

        with patch("redis.from_url", return_value=mock_redis):
            with patch("anthropic.Anthropic", return_value=MockClaudeClient()):
                orchestrator = QAOrchestrator()

                # Setup PRP data
                mock_redis.hset("prp:P0-009", {"id": "P0-009", "title": "Test PRP", "content": "Test content"})

                # Build context
                context = orchestrator.build_qa_context("Test question", "pm", "P0-009")

                assert "codebase" in context
                assert "current_prp" in context
                assert "related_prps" in context
                assert context["question_metadata"]["agent_role"] == "pm"


class TestOrchestrator:
    """Test main orchestrator functionality"""

    def test_orchestrator_initialization(self):
        """Test orchestrator initialization"""
        from orchestrator import MainOrchestrator

        with patch("agents.core.base_worker.redis.from_url", return_value=MockRedisClient()):
            with patch("agents.core.base_worker.Anthropic", return_value=MockClaudeClient()):
                orchestrator = MainOrchestrator(pm_count=2)

                assert len(orchestrator.pm_agents) == 2
                assert orchestrator.validator is not None
                assert orchestrator.integrator is not None
                assert orchestrator.qa_orchestrator is not None

    def test_queue_monitoring(self):
        """Test queue monitoring"""
        from orchestrator import MainOrchestrator

        mock_redis = MockRedisClient()
        # Add items to queues
        mock_redis.lpush("dev_queue", "P0-010", "P0-011")
        mock_redis.lpush("validation_queue", "P0-012")

        with patch("redis.from_url", return_value=mock_redis):
            with patch("anthropic.Anthropic", return_value=MockClaudeClient()):
                orchestrator = MainOrchestrator()

                # Test monitoring
                with patch.object(orchestrator.logger, "info") as mock_log:
                    orchestrator.monitor_queues()

                    # Check log output
                    log_call = mock_log.call_args[0][0]
                    assert "dev_queue: 2 pending" in log_call
                    assert "validation_queue: 1 pending" in log_call

    def test_metrics_update(self):
        """Test metrics collection"""
        from orchestrator import MainOrchestrator

        mock_redis = MockRedisClient()

        # Setup test data
        mock_redis.hset("prp:P0-013", {"state": "complete"})
        mock_redis.hset("prp:P0-014", {"state": "failed"})
        mock_redis.hset("prp:P0-015", {"state": "development"})

        with patch("redis.from_url", return_value=mock_redis):
            with patch("anthropic.Anthropic", return_value=MockClaudeClient()):
                orchestrator = MainOrchestrator()

                # Update metrics
                orchestrator.update_metrics()

                # Check metrics were stored
                metrics_json = mock_redis.get("metrics:latest")
                assert metrics_json is not None

                metrics = json.loads(metrics_json)
                assert metrics["prps"]["total"] == 3
                assert metrics["prps"]["complete"] == 1
                assert metrics["prps"]["failed"] == 1


class TestEndToEnd:
    """End-to-end integration tests"""

    def test_full_prp_lifecycle(self):
        """Test complete PRP lifecycle from dev to deployment"""
        mock_redis = MockRedisClient()
        mock_claude = MockClaudeClient(behavior="normal")

        with patch("redis.from_url", return_value=mock_redis):
            with patch("anthropic.Anthropic", return_value=mock_claude):
                # Create agents
                pm = PMAgent("test-pm-1")
                validator = ValidatorAgent("test-validator-1")
                integrator = IntegrationAgent("test-integrator-1")

                # Setup PRP
                prp_id = "P0-100"
                mock_redis.hset(
                    f"prp:{prp_id}",
                    {
                        "id": prp_id,
                        "title": "End-to-end test feature",
                        "content": "Implement feature with full lifecycle",
                        "priority": "high",
                    },
                )

                # Stage 1: PM Development
                mock_redis.lpush("dev_queue", prp_id)
                prp_bytes = mock_redis.blmove("dev_queue", "dev_queue:inflight", 1.0)
                assert prp_bytes.decode() == prp_id

                pm.process_prp(prp_id)

                # Verify PM completion
                assert mock_redis.hget(f"prp:{prp_id}", "implementation_complete") == b"true"
                assert mock_redis.llen("validation_queue") == 1

                # Stage 2: Validation
                prp_bytes = mock_redis.blmove("validation_queue", "validation_queue:inflight", 1.0)
                validator.process_prp(prp_id)

                # Verify validation
                assert mock_redis.hget(f"prp:{prp_id}", "validation_passed") == b"true"
                assert mock_redis.llen("integration_queue") == 1

                # Stage 3: Integration
                prp_bytes = mock_redis.blmove("integration_queue", "integration_queue:inflight", 1.0)
                integrator.process_prp(prp_id)

                # Verify deployment
                assert mock_redis.hget(f"prp:{prp_id}", "deployed") == b"true"
                assert mock_redis.hget(f"prp:{prp_id}", "state") == b"complete"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
