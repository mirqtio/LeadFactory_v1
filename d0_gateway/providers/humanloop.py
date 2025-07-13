"""
Humanloop provider for centralized prompt management
Phase-0 implementation with all prompts via Humanloop
"""
import os
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..base import BaseAPIClient
from core.logging import get_logger
from core.metrics import metrics

logger = get_logger(__name__, domain="d0")


class HumanloopClient(BaseAPIClient):
    """
    Humanloop API client for prompt management and LLM calls

    This client routes all LLM calls through Humanloop for:
    - Centralized prompt management
    - A/B testing capabilities
    - Usage tracking and analytics
    - Model switching without code changes
    """

    def __init__(self, api_key: Optional[str] = None, project_id: Optional[str] = None):
        """
        Initialize Humanloop client

        Args:
            api_key: Humanloop API key (defaults to env HUMANLOOP_API_KEY)
            project_id: Default project ID (defaults to env HUMANLOOP_PROJECT_ID)
        """
        super().__init__(provider="humanloop", api_key=api_key)
        self.project_id = project_id or os.getenv("HUMANLOOP_PROJECT_ID", "PLACEHOLDER_PROJECT_ID")
        self.prompts_dir = Path(__file__).parent.parent.parent / "prompts"
        self._prompt_cache = {}

    def _get_base_url(self) -> str:
        """Get Humanloop API base URL"""
        return "https://api.humanloop.com/v4"

    def _get_headers(self) -> Dict[str, str]:
        """Get Humanloop API headers"""
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def get_rate_limit(self) -> Dict[str, int]:
        """Get Humanloop rate limit configuration"""
        return {
            "daily_limit": 50000,  # Higher limit as it's a proxy
            "daily_used": 0,
            "burst_limit": 50,
            "window_seconds": 1,
        }

    def calculate_cost(self, operation: str, **kwargs) -> Decimal:
        """
        Calculate cost for Humanloop operations

        Humanloop passes through underlying model costs
        """
        # Extract model from kwargs or default
        model = kwargs.get("model", "gpt-4o-mini")

        if "gpt-4o" in model:
            # GPT-4o-mini pricing
            estimated_input_tokens = kwargs.get("input_tokens", 800)
            estimated_output_tokens = kwargs.get("output_tokens", 300)

            input_cost = (Decimal(estimated_input_tokens) / Decimal("1000000")) * Decimal("0.15")
            output_cost = (Decimal(estimated_output_tokens) / Decimal("1000000")) * Decimal("0.60")

            return input_cost + output_cost
        elif "gpt-4" in model:
            # GPT-4 pricing (higher)
            estimated_input_tokens = kwargs.get("input_tokens", 800)
            estimated_output_tokens = kwargs.get("output_tokens", 300)

            input_cost = (Decimal(estimated_input_tokens) / Decimal("1000000")) * Decimal("30.00")
            output_cost = (Decimal(estimated_output_tokens) / Decimal("1000000")) * Decimal("60.00")

            return input_cost + output_cost
        else:
            # Default/unknown model
            return Decimal("0.001")

    async def load_prompt(self, slug: str) -> Dict[str, Any]:
        """
        Load prompt configuration from markdown file

        Args:
            slug: Prompt slug (filename without .md)

        Returns:
            Dict with prompt content and metadata
        """
        if slug in self._prompt_cache:
            return self._prompt_cache[slug]

        prompt_path = self.prompts_dir / f"{slug}.md"
        if not prompt_path.exists():
            raise ValueError(f"Prompt not found: {slug}")

        with open(prompt_path, "r") as f:
            content = f.read()

        # Parse frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                import yaml
                metadata = yaml.safe_load(parts[1])
                prompt_content = parts[2].strip()
            else:
                metadata = {}
                prompt_content = content
        else:
            metadata = {}
            prompt_content = content

        prompt_config = {
            "slug": slug,
            "content": prompt_content,
            "model": metadata.get("model", "gpt-4o-mini"),
            "temperature": metadata.get("temperature", 0.7),
            "max_tokens": metadata.get("max_tokens", 1000),
            "supports_vision": metadata.get("supports_vision", False),
            "metadata": metadata,
        }

        self._prompt_cache[slug] = prompt_config
        return prompt_config

    async def completion(
        self,
        prompt_slug: str,
        inputs: Dict[str, Any],
        project_id: Optional[str] = None,
        version: Optional[str] = None,
        environment: str = "production",
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a completion using Humanloop

        Args:
            prompt_slug: Prompt identifier
            inputs: Variables to inject into prompt
            project_id: Override default project ID
            version: Specific prompt version (optional)
            environment: Environment tag
            user_id: User identifier for tracking
            metadata: Additional metadata

        Returns:
            Humanloop completion response
        """
        # Load prompt from local file (in production, this would use Humanloop API)
        prompt_config = await self.load_prompt(prompt_slug)

        # Format prompt with inputs
        formatted_prompt = self._format_prompt(prompt_config["content"], inputs)

        # Prepare Humanloop request
        payload = {
            "project": project_id or self.project_id,
            "model": prompt_config["model"],
            "prompt": formatted_prompt,
            "temperature": prompt_config["temperature"],
            "max_tokens": prompt_config["max_tokens"],
            "environment": environment,
        }

        if version:
            payload["version"] = version
        if user_id:
            payload["user_id"] = user_id
        if metadata:
            payload["metadata"] = metadata

        # Track request start time
        start_time = time.time()

        try:
            # In production, this would call Humanloop API
            # For now, we'll simulate by calling OpenAI directly
            response = await self._simulate_completion(payload, prompt_config)

            # Track metrics
            duration = time.time() - start_time
            usage = response.get("usage", {})

            metrics.track_prompt_request(
                prompt_slug=prompt_slug,
                model=prompt_config["model"],
                duration=duration,
                tokens_input=usage.get("prompt_tokens", 0),
                tokens_output=usage.get("completion_tokens", 0),
                cost=float(self.calculate_cost("completion", model=prompt_config["model"], **usage)),
                status="success",
            )

            # Log the request
            logger.info(
                "Humanloop completion successful",
                extra={
                    "prompt_slug": prompt_slug,
                    "model": prompt_config["model"],
                    "duration_ms": int(duration * 1000),
                    "tokens": usage.get("total_tokens", 0),
                }
            )

            return response

        except Exception as e:
            # Track failed request
            duration = time.time() - start_time
            metrics.track_prompt_request(
                prompt_slug=prompt_slug,
                model=prompt_config["model"],
                duration=duration,
                tokens_input=0,
                tokens_output=0,
                cost=0,
                status="failed",
            )

            logger.error(
                "Humanloop completion failed",
                extra={
                    "prompt_slug": prompt_slug,
                    "error": str(e),
                    "duration_ms": int(duration * 1000),
                }
            )
            raise

    async def chat_completion(
        self,
        prompt_slug: str,
        inputs: Dict[str, Any],
        messages: Optional[List[Dict[str, str]]] = None,
        project_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Create a chat completion using Humanloop

        Args:
            prompt_slug: Prompt identifier
            inputs: Variables to inject into prompt
            messages: Optional message history
            project_id: Override default project ID
            **kwargs: Additional parameters

        Returns:
            Humanloop chat completion response
        """
        # Load prompt configuration
        prompt_config = await self.load_prompt(prompt_slug)

        # Format system prompt with inputs
        system_prompt = self._format_prompt(prompt_config["content"], inputs)

        # Build messages
        if messages is None:
            messages = []

        # Add system message if prompt content exists
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        # Prepare payload
        payload = {
            "project": project_id or self.project_id,
            "model": prompt_config["model"],
            "messages": messages,
            "temperature": prompt_config["temperature"],
            "max_tokens": prompt_config["max_tokens"],
            **kwargs,
        }

        # Track request start time
        start_time = time.time()

        try:
            # In production, this would call Humanloop chat endpoint
            response = await self._simulate_chat_completion(payload, prompt_config)

            # Track metrics
            duration = time.time() - start_time
            usage = response.get("usage", {})

            metrics.track_prompt_request(
                prompt_slug=prompt_slug,
                model=prompt_config["model"],
                duration=duration,
                tokens_input=usage.get("prompt_tokens", 0),
                tokens_output=usage.get("completion_tokens", 0),
                cost=float(self.calculate_cost("chat", model=prompt_config["model"], **usage)),
                status="success",
            )

            logger.info(
                "Humanloop chat completion successful",
                extra={
                    "prompt_slug": prompt_slug,
                    "model": prompt_config["model"],
                    "duration_ms": int(duration * 1000),
                    "tokens": usage.get("total_tokens", 0),
                }
            )

            return response

        except Exception as e:
            # Track failed request
            duration = time.time() - start_time
            metrics.track_prompt_request(
                prompt_slug=prompt_slug,
                model=prompt_config["model"],
                duration=duration,
                tokens_input=0,
                tokens_output=0,
                cost=0,
                status="failed",
            )

            logger.error(
                "Humanloop chat completion failed",
                extra={
                    "prompt_slug": prompt_slug,
                    "error": str(e),
                    "duration_ms": int(duration * 1000),
                }
            )
            raise

    async def log_feedback(
        self,
        completion_id: str,
        feedback_type: str,
        value: Union[bool, float, str],
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Log feedback for a completion

        Args:
            completion_id: ID of the completion
            feedback_type: Type of feedback (rating, flag, comment)
            value: Feedback value
            comment: Optional comment

        Returns:
            Feedback response
        """
        payload = {
            "completion_id": completion_id,
            "type": feedback_type,
            "value": value,
        }

        if comment:
            payload["comment"] = comment

        # In production, this would call Humanloop feedback API
        logger.info(f"Feedback logged: {feedback_type}={value} for {completion_id}")
        return {"status": "success", "feedback_id": f"fb_{completion_id}"}

    def _format_prompt(self, template: str, inputs: Dict[str, Any]) -> str:
        """
        Format prompt template with inputs

        Handles both {var} and {{var}} syntax
        """
        formatted = template

        # Handle conditional sections (simplified)
        # {lcp_section} -> filled if lcp_score exists
        for key, value in inputs.items():
            if f"{{{key}_section}}" in formatted:
                # This is a conditional section
                if key in inputs and inputs[key]:
                    formatted = formatted.replace(f"{{{key}_section}}", str(value))
                else:
                    formatted = formatted.replace(f"{{{key}_section}}", "")

        # Handle regular variables
        for key, value in inputs.items():
            # Handle both {var} and {{var}} syntax
            formatted = formatted.replace(f"{{{key}}}", str(value))
            formatted = formatted.replace(f"{{{{{key}}}}}", str(value))

        return formatted

    async def _simulate_completion(
        self, payload: Dict[str, Any], prompt_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Simulate Humanloop completion by calling OpenAI

        In production, this would be replaced by actual Humanloop API call
        """
        # Import here to avoid circular dependency
        from .openai import OpenAIClient

        # Create OpenAI client
        openai_client = OpenAIClient()

        # Call OpenAI
        messages = [{"role": "user", "content": payload["prompt"]}]

        response = await openai_client.chat_completion(
            messages=messages,
            model=payload["model"],
            temperature=payload["temperature"],
            max_tokens=payload["max_tokens"],
        )

        # Wrap in Humanloop-style response
        return {
            "id": f"hl_{response.get('id', 'mock')}",
            "project_id": payload["project"],
            "model": payload["model"],
            "output": response["choices"][0]["message"]["content"],
            "usage": response.get("usage", {}),
            "prompt_slug": prompt_config["slug"],
            "humanloop_version": "simulated",
        }

    async def _simulate_chat_completion(
        self, payload: Dict[str, Any], prompt_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Simulate Humanloop chat completion by calling OpenAI

        In production, this would be replaced by actual Humanloop API call
        """
        # Import here to avoid circular dependency
        from .openai import OpenAIClient

        # Create OpenAI client
        openai_client = OpenAIClient()

        # Handle vision prompts
        if prompt_config.get("supports_vision") and any(
            "image_url" in str(msg.get("content", "")) for msg in payload["messages"]
        ):
            # This is a vision request
            response_format = {"type": "json_object"} if "json" in prompt_config["content"].lower() else None
        else:
            response_format = None

        # Call OpenAI
        response = await openai_client.chat_completion(
            messages=payload["messages"],
            model=payload["model"],
            temperature=payload["temperature"],
            max_tokens=payload["max_tokens"],
            response_format=response_format,
        )

        # Wrap in Humanloop-style response
        return {
            "id": f"hl_{response.get('id', 'mock')}",
            "project_id": payload["project"],
            "model": payload["model"],
            "choices": response["choices"],
            "usage": response.get("usage", {}),
            "prompt_slug": prompt_config["slug"],
            "humanloop_version": "simulated",
        }


# Convenience functions for backward compatibility
async def create_completion(
    prompt_slug: str,
    inputs: Dict[str, Any],
    **kwargs
) -> Dict[str, Any]:
    """
    Create a completion using the default Humanloop client

    Args:
        prompt_slug: Prompt identifier
        inputs: Variables to inject into prompt
        **kwargs: Additional parameters

    Returns:
        Completion response
    """
    client = HumanloopClient()
    return await client.completion(prompt_slug, inputs, **kwargs)


async def create_chat_completion(
    prompt_slug: str,
    inputs: Dict[str, Any],
    messages: Optional[List[Dict[str, str]]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Create a chat completion using the default Humanloop client

    Args:
        prompt_slug: Prompt identifier
        inputs: Variables to inject into prompt
        messages: Optional message history
        **kwargs: Additional parameters

    Returns:
        Chat completion response
    """
    client = HumanloopClient()
    return await client.chat_completion(prompt_slug, inputs, messages, **kwargs)
