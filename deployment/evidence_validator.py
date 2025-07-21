"""
Evidence validation module for PRP-1060 acceptance testing pipeline.

Integrates with Redis and PRP-1059 Lua promotion script for atomic
evidence collection and validation.
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

import redis
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class EvidenceConfig(BaseModel):
    """Configuration for evidence validation."""

    redis_url: str = Field(..., description="Redis connection URL")
    prp_id: str = Field(..., description="PRP identifier")

    # Evidence keys
    acceptance_passed_key: str = Field(default="acceptance_passed", description="Acceptance test evidence key")
    deploy_ok_key: str = Field(default="deploy_ok", description="Deployment success evidence key")

    # Lua script integration
    lua_script_path: str = Field(default="redis/promote.lua", description="Path to promotion Lua script")

    # Validation settings
    timeout_seconds: int = Field(default=300, description="Evidence validation timeout")
    retry_attempts: int = Field(default=3, description="Number of retry attempts")


class EvidenceEntry(BaseModel):
    """Individual evidence entry."""

    key: str = Field(..., description="Evidence key")
    value: str = Field(..., description="Evidence value")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional evidence metadata")


class ValidationResult(BaseModel):
    """Result of evidence validation."""

    success: bool = Field(..., description="Whether validation succeeded")
    evidence_collected: List[EvidenceEntry] = Field(default_factory=list)
    validation_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = Field(None, description="Error message if validation failed")
    lua_promotion_result: Optional[Dict[str, Any]] = Field(None, description="Result from Lua promotion script")


class EvidenceValidator:
    """Validates and manages evidence for PRP promotion."""

    def __init__(self, config: EvidenceConfig):
        self.config = config
        self.redis_client = self._create_redis_client()
        self.lua_script_sha: Optional[str] = None

    def _create_redis_client(self) -> redis.Redis:
        """Create Redis client with connection pooling."""
        try:
            client = redis.from_url(
                self.config.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=10,
                socket_timeout=10,
                retry_on_timeout=True,
                health_check_interval=30,
            )

            # Test connection
            client.ping()
            logger.info("Redis connection established successfully")
            return client

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def collect_evidence(self, evidence_type: str, value: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Collect and store evidence in Redis."""
        try:
            entry = EvidenceEntry(key=evidence_type, value=value, metadata=metadata or {})

            # Store in PRP-specific hash
            prp_key = f"prp:{self.config.prp_id}"

            # Store main evidence
            self.redis_client.hset(prp_key, entry.key, entry.value)

            # Store metadata if present
            if entry.metadata:
                metadata_key = f"{prp_key}:{entry.key}_metadata"
                self.redis_client.set(metadata_key, json.dumps(entry.metadata, default=str), ex=86400)  # 24 hour expiry

            # Store timestamp
            timestamp_key = f"{prp_key}:{entry.key}_timestamp"
            self.redis_client.set(timestamp_key, entry.timestamp.isoformat(), ex=86400)

            logger.info(f"Evidence collected: {evidence_type} = {value}")
            return True

        except Exception as e:
            logger.error(f"Failed to collect evidence {evidence_type}: {e}")
            return False

    async def validate_acceptance_evidence(self, test_results: Dict[str, Any]) -> bool:
        """Validate and store acceptance test evidence."""
        logger.info("Validating acceptance test evidence")

        # Determine if tests passed
        test_passed = (
            test_results.get("status") == "passed"
            and test_results.get("exit_code") == 0
            and test_results.get("tests_failed", 0) == 0
        )

        # Collect evidence
        success = await self.collect_evidence(
            self.config.acceptance_passed_key,
            "true" if test_passed else "false",
            {
                "test_results": test_results,
                "validation_criteria": {
                    "status_passed": test_results.get("status") == "passed",
                    "exit_code_zero": test_results.get("exit_code") == 0,
                    "no_failed_tests": test_results.get("tests_failed", 0) == 0,
                },
            },
        )

        if success and test_passed:
            logger.info("✅ Acceptance evidence validated and stored")
        else:
            logger.error("❌ Acceptance evidence validation failed")

        return success and test_passed

    async def validate_deployment_evidence(self, deploy_results: Dict[str, Any]) -> bool:
        """Validate and store deployment evidence."""
        logger.info("Validating deployment evidence")

        # Determine if deployment succeeded
        deploy_success = deploy_results.get("status") == "success" and all(
            check.get("healthy", False) for check in deploy_results.get("health_check_results", [])
        )

        # Collect evidence
        success = await self.collect_evidence(
            self.config.deploy_ok_key,
            "true" if deploy_success else "false",
            {
                "deploy_results": deploy_results,
                "validation_criteria": {
                    "status_success": deploy_results.get("status") == "success",
                    "health_checks_passed": all(
                        check.get("healthy", False) for check in deploy_results.get("health_check_results", [])
                    ),
                },
            },
        )

        if success and deploy_success:
            logger.info("✅ Deployment evidence validated and stored")
        else:
            logger.error("❌ Deployment evidence validation failed")

        return success and deploy_success

    async def check_evidence_completeness(self) -> Dict[str, Any]:
        """Check if all required evidence is present."""
        logger.info("Checking evidence completeness")

        prp_key = f"prp:{self.config.prp_id}"
        evidence_status = {}

        required_evidence = [self.config.acceptance_passed_key, self.config.deploy_ok_key]

        try:
            for evidence_key in required_evidence:
                value = self.redis_client.hget(prp_key, evidence_key)
                evidence_status[evidence_key] = {
                    "present": value is not None,
                    "value": value,
                    "valid": value == "true" if value else False,
                }

            # Check overall completeness
            all_present = all(status["present"] for status in evidence_status.values())
            all_valid = all(status["valid"] for status in evidence_status.values())

            result = {
                "complete": all_present,
                "valid": all_valid,
                "ready_for_promotion": all_present and all_valid,
                "evidence": evidence_status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            logger.info(f"Evidence completeness: {result}")
            return result

        except Exception as e:
            logger.error(f"Failed to check evidence completeness: {e}")
            return {
                "complete": False,
                "valid": False,
                "ready_for_promotion": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def trigger_prp_promotion(self) -> Dict[str, Any]:
        """Trigger PRP promotion using Lua script."""
        logger.info(f"Triggering PRP promotion for {self.config.prp_id}")

        try:
            # Check evidence completeness first
            evidence_check = await self.check_evidence_completeness()

            if not evidence_check.get("ready_for_promotion", False):
                return {
                    "success": False,
                    "error": "Evidence not ready for promotion",
                    "evidence_status": evidence_check,
                }

            # Load and execute Lua promotion script
            lua_result = await self._execute_lua_promotion()

            if lua_result.get("success", False):
                logger.info("✅ PRP promotion triggered successfully")
            else:
                logger.error(f"❌ PRP promotion failed: {lua_result.get('error')}")

            return lua_result

        except Exception as e:
            logger.error(f"PRP promotion failed: {e}")
            return {"success": False, "error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}

    async def _execute_lua_promotion(self) -> Dict[str, Any]:
        """Execute Lua promotion script."""
        try:
            # Load Lua script if not already loaded
            if not self.lua_script_sha:
                lua_script = self._load_lua_script()
                self.lua_script_sha = self.redis_client.script_load(lua_script)
                logger.info("Lua promotion script loaded")

            # Execute script with PRP ID
            result = self.redis_client.evalsha(
                self.lua_script_sha,
                1,  # Number of keys
                f"prp:{self.config.prp_id}",  # PRP key
                self.config.prp_id,  # PRP ID argument
            )

            return {"success": True, "lua_result": result, "timestamp": datetime.now(timezone.utc).isoformat()}

        except Exception as e:
            logger.error(f"Lua script execution failed: {e}")
            return {"success": False, "error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}

    def _load_lua_script(self) -> str:
        """Load Lua promotion script from file."""
        try:
            with open(self.config.lua_script_path, "r") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"Lua script not found at {self.config.lua_script_path}, using default")
            return self._get_default_lua_script()
        except Exception as e:
            logger.error(f"Failed to load Lua script: {e}")
            raise

    def _get_default_lua_script(self) -> str:
        """Default Lua promotion script if file not found."""
        return """
        -- Default PRP promotion script
        local prp_key = KEYS[1]
        local prp_id = ARGV[1]
        
        -- Check required evidence
        local acceptance_passed = redis.call('HGET', prp_key, 'acceptance_passed')
        local deploy_ok = redis.call('HGET', prp_key, 'deploy_ok')
        
        -- Validate evidence
        if acceptance_passed ~= 'true' then
            return {success = false, error = 'acceptance_passed not true'}
        end
        
        if deploy_ok ~= 'true' then
            return {success = false, error = 'deploy_ok not true'}
        end
        
        -- Mark as promoted
        redis.call('HSET', prp_key, 'promoted', 'true')
        redis.call('HSET', prp_key, 'promotion_timestamp', tostring(redis.call('TIME')[1]))
        
        return {success = true, prp_id = prp_id}
        """

    async def get_evidence_summary(self) -> Dict[str, Any]:
        """Get complete evidence summary for reporting."""
        logger.info("Generating evidence summary")

        try:
            prp_key = f"prp:{self.config.prp_id}"

            # Get all evidence from hash
            evidence_hash = self.redis_client.hgetall(prp_key)

            # Get metadata for each evidence entry
            evidence_details = {}
            for key, value in evidence_hash.items():
                metadata_key = f"{prp_key}:{key}_metadata"
                timestamp_key = f"{prp_key}:{key}_timestamp"

                metadata = self.redis_client.get(metadata_key)
                timestamp = self.redis_client.get(timestamp_key)

                evidence_details[key] = {
                    "value": value,
                    "timestamp": timestamp,
                    "metadata": json.loads(metadata) if metadata else None,
                }

            # Check promotion status
            promotion_status = await self.check_evidence_completeness()

            summary = {
                "prp_id": self.config.prp_id,
                "evidence_details": evidence_details,
                "promotion_status": promotion_status,
                "summary_timestamp": datetime.now(timezone.utc).isoformat(),
            }

            logger.info("Evidence summary generated successfully")
            return summary

        except Exception as e:
            logger.error(f"Failed to generate evidence summary: {e}")
            return {
                "prp_id": self.config.prp_id,
                "error": str(e),
                "summary_timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def clear_evidence(self) -> bool:
        """Clear all evidence for PRP (used for rollback)."""
        logger.warning(f"Clearing evidence for PRP {self.config.prp_id}")

        try:
            prp_key = f"prp:{self.config.prp_id}"

            # Get all keys related to this PRP
            all_keys = self.redis_client.keys(f"{prp_key}*")

            if all_keys:
                # Delete all related keys
                self.redis_client.delete(*all_keys)
                logger.info(f"Cleared {len(all_keys)} evidence keys")

            return True

        except Exception as e:
            logger.error(f"Failed to clear evidence: {e}")
            return False
