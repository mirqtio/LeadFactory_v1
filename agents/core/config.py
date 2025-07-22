#!/usr/bin/env python3
"""
Configuration management for agent system
"""
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


class Config:
    """Configuration for agent system"""
    
    def __init__(self):
        # Load environment variables from parent directory first
        parent_env = Path(__file__).parent.parent.parent / ".env"
        if parent_env.exists():
            load_dotenv(parent_env)
        
        # Then load local agent .env if exists (can override)
        local_env = Path(__file__).parent.parent / ".env"
        if local_env.exists():
            load_dotenv(local_env, override=True)
        
        # API Configuration
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        
        # Redis Configuration
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        # Model Configuration
        self.pm_model = os.getenv("PM_MODEL", "claude-3-5-sonnet-20241022")
        self.validator_model = os.getenv("VALIDATOR_MODEL", "claude-3-5-sonnet-20241022")
        self.integrator_model = os.getenv("INTEGRATOR_MODEL", "claude-3-5-sonnet-20241022")
        self.qa_model = os.getenv("QA_MODEL", "claude-3-opus-20240229")
        
        # Agent Configuration
        self.pm_agent_count = int(os.getenv("PM_AGENT_COUNT", "3"))
        self.max_iterations_per_prp = int(os.getenv("MAX_ITERATIONS_PER_PRP", "10"))
        self.qa_timeout_seconds = int(os.getenv("QA_TIMEOUT_SECONDS", "300"))
        
        # Retry Configuration
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        self.retry_delay_seconds = int(os.getenv("RETRY_DELAY_SECONDS", "30"))
        
        # Monitoring Configuration
        self.monitor_interval_seconds = int(os.getenv("MONITOR_INTERVAL_SECONDS", "10"))
        self.stuck_prp_threshold_minutes = int(os.getenv("STUCK_PRP_THRESHOLD_MINUTES", "30"))
        self.agent_inactive_threshold_minutes = int(os.getenv("AGENT_INACTIVE_THRESHOLD_MINUTES", "5"))
        
        # Cost Monitoring
        self.enable_cost_tracking = os.getenv("ENABLE_COST_TRACKING", "true").lower() == "true"
        self.daily_cost_limit = float(os.getenv("DAILY_COST_LIMIT", "100.0"))
        
        # Logging
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.log_format = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        
    def get_model_for_role(self, role: str) -> str:
        """Get the appropriate model for a given role"""
        if role == "pm":
            return self.pm_model
        elif role == "validator":
            return self.validator_model
        elif role == "integration":
            return self.integrator_model
        elif role == "qa":
            return self.qa_model
        else:
            return self.pm_model  # Default
    
    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for API usage"""
        # Pricing per million tokens (as of 2025)
        pricing = {
            "claude-3-opus-20240229": {"input": 15.0, "output": 75.0},
            "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
            "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25}
        }
        
        model_pricing = pricing.get(model, pricing["claude-3-5-sonnet-20241022"])
        
        input_cost = (input_tokens / 1_000_000) * model_pricing["input"]
        output_cost = (output_tokens / 1_000_000) * model_pricing["output"]
        
        return input_cost + output_cost
    
    def to_dict(self) -> dict:
        """Convert config to dictionary (excluding sensitive data)"""
        return {
            "redis_url": self.redis_url,
            "pm_model": self.pm_model,
            "validator_model": self.validator_model,
            "integrator_model": self.integrator_model,
            "qa_model": self.qa_model,
            "pm_agent_count": self.pm_agent_count,
            "max_iterations_per_prp": self.max_iterations_per_prp,
            "qa_timeout_seconds": self.qa_timeout_seconds,
            "max_retries": self.max_retries,
            "monitor_interval_seconds": self.monitor_interval_seconds,
            "enable_cost_tracking": self.enable_cost_tracking,
            "daily_cost_limit": self.daily_cost_limit,
            "log_level": self.log_level
        }


# Global config instance
config = Config()