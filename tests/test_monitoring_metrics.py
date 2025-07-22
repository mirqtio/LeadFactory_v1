#!/usr/bin/env python3
"""
Tests for monitoring, metrics, and dashboard data collection
"""
import json
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pytest
import redis


class MetricsCollector:
    """Collect and validate system metrics for dashboard"""

    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.metrics = defaultdict(int)

    def collect_queue_metrics(self) -> Dict[str, Dict[str, int]]:
        """Collect metrics for all queues"""
        queues = ["dev_queue", "validation_queue", "integration_queue"]
        metrics = {}

        for queue in queues:
            metrics[queue] = {
                "depth": self.redis_client.llen(queue),
                "inflight": self.redis_client.llen(f"{queue}:inflight"),
                "total": self.redis_client.llen(queue) + self.redis_client.llen(f"{queue}:inflight"),
            }

        return metrics

    def collect_agent_metrics(self) -> Dict[str, Dict[str, any]]:
        """Collect metrics for all agents"""
        agents = ["orchestrator", "pm-1", "pm-2", "pm-3", "validator", "integrator"]
        metrics = {}

        for agent in agents:
            agent_key = f"agent:{agent}"
            agent_data = self.redis_client.hgetall(agent_key)

            if agent_data:
                last_activity = agent_data.get(b"last_activity", b"").decode()
                if last_activity:
                    try:
                        last_time = datetime.fromisoformat(last_activity)
                        age_seconds = (datetime.utcnow() - last_time).total_seconds()
                    except:
                        age_seconds = float("inf")
                else:
                    age_seconds = float("inf")

                metrics[agent] = {
                    "status": agent_data.get(b"status", b"unknown").decode(),
                    "current_prp": agent_data.get(b"current_prp", b"").decode(),
                    "last_activity_age": age_seconds,
                    "healthy": age_seconds < 300,  # 5 minute threshold
                }
            else:
                metrics[agent] = {
                    "status": "missing",
                    "current_prp": "",
                    "last_activity_age": float("inf"),
                    "healthy": False,
                }

        return metrics

    def collect_prp_metrics(self) -> Dict[str, any]:
        """Collect PRP-level metrics"""
        metrics = {
            "total_prps": 0,
            "by_state": defaultdict(int),
            "stuck_prps": [],
            "high_retry_prps": [],
            "age_distribution": defaultdict(list),
        }

        # Scan all PRPs
        for key in self.redis_client.keys("prp:*"):
            prp_id = key.decode().split(":")[1]
            prp_data = self.redis_client.hgetall(key)

            if not prp_data:
                continue

            metrics["total_prps"] += 1

            # Decode data
            data = {k.decode(): v.decode() for k, v in prp_data.items()}

            # Count by state
            state = data.get("state", "unknown")
            metrics["by_state"][state] += 1

            # Check if stuck
            if self._is_stuck(data):
                metrics["stuck_prps"].append(prp_id)

            # Check retry count
            retry_count = int(data.get("retry_count", "0"))
            if retry_count >= 3:
                metrics["high_retry_prps"].append(
                    {
                        "prp_id": prp_id,
                        "retry_count": retry_count,
                        "state": state,
                    }
                )

            # Age distribution
            created_at = data.get("created_at", "")
            if created_at:
                age_hours = (datetime.utcnow() - datetime.fromisoformat(created_at)).total_seconds() / 3600
                metrics["age_distribution"][state].append(age_hours)

        return dict(metrics)

    def _is_stuck(self, prp_data: Dict[str, str]) -> bool:
        """Check if PRP is stuck"""
        # Check inflight timeout
        inflight_since = prp_data.get("inflight_since", "")
        if inflight_since:
            inflight_time = datetime.fromisoformat(inflight_since)
            if datetime.utcnow() - inflight_time > timedelta(minutes=30):
                return True

        # Check state age
        state = prp_data.get("state", "")
        state_timestamp_key = f"{state}_at"
        if state_timestamp_key in prp_data:
            state_time = datetime.fromisoformat(prp_data[state_timestamp_key])
            if datetime.utcnow() - state_time > timedelta(hours=1):
                return True

        return False

    def calculate_flow_rates(self) -> Dict[str, float]:
        """Calculate flow rates between queues"""
        # This would need historical data in practice
        # For now, return mock data
        return {
            "dev_to_validation": 0.8,  # PRPs/hour
            "validation_to_integration": 0.7,
            "integration_to_complete": 0.9,
            "rejection_rate": 0.1,
            "failure_rate": 0.05,
        }


class TestMonitoringMetrics:
    """Test monitoring and metrics collection"""

    def setup_method(self):
        """Set up test environment"""
        self.redis_client = redis.from_url("redis://localhost:6379/0")
        self.collector = MetricsCollector(self.redis_client)
        self.cleanup_test_data()

    def teardown_method(self):
        """Clean up after tests"""
        self.cleanup_test_data()

    def cleanup_test_data(self):
        """Remove all test data"""
        for key in self.redis_client.keys("prp:METRIC-*"):
            self.redis_client.delete(key)
        for key in self.redis_client.keys("test_*"):
            self.redis_client.delete(key)
        for key in self.redis_client.keys("agent:test-*"):
            self.redis_client.delete(key)

    def create_test_system_state(self):
        """Create a realistic system state for testing"""
        # Create PRPs in various states
        states = {
            "new": 5,
            "development": 3,
            "validation": 2,
            "integration": 1,
            "complete": 10,
            "failed": 2,
            "rejected": 1,
        }

        prp_counter = 1
        for state, count in states.items():
            for i in range(count):
                prp_id = f"METRIC-{prp_counter:03d}"
                prp_data = {
                    "id": prp_id,
                    "state": state,
                    "created_at": (datetime.utcnow() - timedelta(hours=prp_counter)).isoformat(),
                    "retry_count": str(i % 4),
                }

                # Add state-specific fields
                if state in ["development", "validation", "integration"]:
                    prp_data["inflight_since"] = (datetime.utcnow() - timedelta(minutes=prp_counter * 5)).isoformat()
                    prp_data["owner"] = f"test-agent-{i % 3}"

                self.redis_client.hset(f"prp:{prp_id}", mapping=prp_data)

                # Add to appropriate queue
                if state == "new":
                    self.redis_client.lpush("dev_queue", prp_id)
                elif state == "development":
                    self.redis_client.lpush("dev_queue:inflight", prp_id)
                elif state == "validation":
                    self.redis_client.lpush("validation_queue:inflight", prp_id)

                prp_counter += 1

        # Create agent states
        agents = ["pm-1", "pm-2", "validator", "integrator"]
        for i, agent in enumerate(agents):
            agent_data = {
                "status": "active" if i < 3 else "idle",
                "last_activity": (datetime.utcnow() - timedelta(minutes=i * 2)).isoformat(),
                "current_prp": f"METRIC-{i+1:03d}" if i < 3 else "",
            }
            self.redis_client.hset(f"agent:{agent}", mapping=agent_data)

    def test_queue_metrics_collection(self):
        """Test queue depth and inflight metrics"""
        self.create_test_system_state()

        metrics = self.collector.collect_queue_metrics()

        # Verify structure
        assert "dev_queue" in metrics
        assert "validation_queue" in metrics
        assert "integration_queue" in metrics

        # Verify dev queue has items
        assert metrics["dev_queue"]["depth"] > 0
        assert metrics["dev_queue"]["inflight"] > 0
        assert metrics["dev_queue"]["total"] == metrics["dev_queue"]["depth"] + metrics["dev_queue"]["inflight"]

    def test_agent_health_monitoring(self):
        """Test agent health and status monitoring"""
        self.create_test_system_state()

        metrics = self.collector.collect_agent_metrics()

        # Check known agents
        assert "pm-1" in metrics
        assert metrics["pm-1"]["status"] == "active"
        assert metrics["pm-1"]["healthy"] is True

        # Check missing agent
        assert "orchestrator" in metrics
        assert metrics["orchestrator"]["status"] == "missing"
        assert metrics["orchestrator"]["healthy"] is False

    def test_stuck_prp_detection(self):
        """Test detection of stuck PRPs"""
        # Clear any existing test PRPs
        for key in self.redis_client.keys("prp:METRIC-*"):
            self.redis_client.delete(key)

        # Create a stuck PRP
        stuck_prp_id = "METRIC-STUCK-001"
        self.redis_client.hset(
            f"prp:{stuck_prp_id}",
            mapping={
                "id": stuck_prp_id,
                "state": "development",
                "inflight_since": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
                "retry_count": "0",
                "created_at": datetime.utcnow().isoformat(),
            },
        )

        metrics = self.collector.collect_prp_metrics()

        assert stuck_prp_id in metrics["stuck_prps"], f"Should find stuck PRP, got: {metrics['stuck_prps']}"

    def test_high_retry_detection(self):
        """Test detection of PRPs with high retry counts"""
        # Create high retry PRP
        high_retry_id = "METRIC-RETRY-001"
        self.redis_client.hset(
            f"prp:{high_retry_id}",
            mapping={
                "id": high_retry_id,
                "state": "failed",
                "retry_count": "5",
                "created_at": datetime.utcnow().isoformat(),
            },
        )

        metrics = self.collector.collect_prp_metrics()

        high_retry_prps = [p["prp_id"] for p in metrics["high_retry_prps"]]
        assert high_retry_id in high_retry_prps

    def test_prp_age_distribution(self):
        """Test PRP age distribution by state"""
        self.create_test_system_state()

        metrics = self.collector.collect_prp_metrics()

        # Check age distribution exists
        assert "age_distribution" in metrics
        assert len(metrics["age_distribution"]) > 0

        # Verify older PRPs
        for state, ages in metrics["age_distribution"].items():
            if ages:
                assert all(age >= 0 for age in ages)

    def test_system_invariants_monitoring(self):
        """Test monitoring of system-wide invariants"""
        self.create_test_system_state()

        # Collect all metrics
        queue_metrics = self.collector.collect_queue_metrics()
        prp_metrics = self.collector.collect_prp_metrics()

        # Basic invariants
        assert prp_metrics["total_prps"] > 0, "Should have PRPs in system"
        assert len(prp_metrics["by_state"]) > 0, "Should have state distribution"

        # All PRPs should have a state
        total_by_state = sum(prp_metrics["by_state"].values())
        assert total_by_state == prp_metrics["total_prps"], "All PRPs should have a state"

        # Queue depths should be non-negative
        for queue, metrics in queue_metrics.items():
            assert metrics["depth"] >= 0, f"{queue} depth should be non-negative"
            assert metrics["inflight"] >= 0, f"{queue} inflight should be non-negative"
            assert metrics["total"] == metrics["depth"] + metrics["inflight"]

    def test_dashboard_data_structure(self):
        """Test complete dashboard data structure"""
        self.create_test_system_state()

        # Simulate dashboard data collection
        dashboard_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "queues": self.collector.collect_queue_metrics(),
            "agents": self.collector.collect_agent_metrics(),
            "prps": self.collector.collect_prp_metrics(),
            "flow_rates": self.collector.calculate_flow_rates(),
            "alerts": [],
        }

        # Generate alerts
        if dashboard_data["prps"]["stuck_prps"]:
            dashboard_data["alerts"].append(
                {
                    "level": "warning",
                    "message": f"{len(dashboard_data['prps']['stuck_prps'])} PRPs are stuck",
                    "prps": dashboard_data["prps"]["stuck_prps"],
                }
            )

        # Check unhealthy agents
        unhealthy_agents = [agent for agent, data in dashboard_data["agents"].items() if not data["healthy"]]
        if unhealthy_agents:
            dashboard_data["alerts"].append(
                {
                    "level": "error",
                    "message": f"{len(unhealthy_agents)} agents are unhealthy",
                    "agents": unhealthy_agents,
                }
            )

        # Verify dashboard structure
        assert "timestamp" in dashboard_data
        assert "queues" in dashboard_data
        assert "agents" in dashboard_data
        assert "prps" in dashboard_data
        assert "alerts" in dashboard_data

        # Should have some alerts in our test data
        assert len(dashboard_data["alerts"]) > 0

    def test_sla_tracking(self):
        """Test SLA tracking for PRP processing times"""
        # Define SLAs (in hours)
        slas = {
            "new_to_development": 1,
            "development_to_validation": 4,
            "validation_to_integration": 2,
            "integration_to_complete": 1,
            "total_time": 8,
        }

        # Create PRP with timestamps
        prp_id = "METRIC-SLA-001"
        now = datetime.utcnow()
        self.redis_client.hset(
            f"prp:{prp_id}",
            mapping={
                "id": prp_id,
                "state": "complete",
                "created_at": (now - timedelta(hours=10)).isoformat(),
                "assigned_at": (now - timedelta(hours=9.5)).isoformat(),
                "development_at": (now - timedelta(hours=9)).isoformat(),
                "validation_at": (now - timedelta(hours=5)).isoformat(),
                "integration_at": (now - timedelta(hours=3)).isoformat(),
                "complete_at": (now - timedelta(hours=1)).isoformat(),
            },
        )

        # Calculate SLA compliance
        prp_data = self.redis_client.hgetall(f"prp:{prp_id}")
        data = {k.decode(): v.decode() for k, v in prp_data.items()}

        # Check total time SLA
        total_time = (
            datetime.fromisoformat(data["complete_at"]) - datetime.fromisoformat(data["created_at"])
        ).total_seconds() / 3600

        assert total_time > slas["total_time"]  # This PRP violated SLA

    def test_error_categorization(self):
        """Test categorization of errors and failures"""
        # Create PRPs with different failure reasons
        failures = [
            ("METRIC-FAIL-001", "Agent timeout"),
            ("METRIC-FAIL-002", "Test failure"),
            ("METRIC-FAIL-003", "Network error"),
            ("METRIC-FAIL-004", "Agent timeout"),
        ]

        for prp_id, reason in failures:
            self.redis_client.hset(
                f"prp:{prp_id}",
                mapping={
                    "id": prp_id,
                    "state": "failed",
                    "failure_reason": reason,
                    "retry_count": "1",
                },
            )

        # Collect and categorize
        error_categories = defaultdict(list)
        for key in self.redis_client.keys("prp:METRIC-FAIL-*"):
            prp_data = self.redis_client.hgetall(key)
            if prp_data:
                reason = prp_data.get(b"failure_reason", b"unknown").decode()
                prp_id = key.decode().split(":")[1]
                error_categories[reason].append(prp_id)

        # Verify categorization
        assert len(error_categories["Agent timeout"]) == 2
        assert len(error_categories["Test failure"]) == 1
        assert len(error_categories["Network error"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
