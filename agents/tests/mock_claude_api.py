#!/usr/bin/env python3
"""
Mock Claude API for testing
"""
import json
import re
from typing import Dict, List, Optional
from unittest.mock import MagicMock


class MockClaudeResponse:
    """Mock response from Claude API"""

    def __init__(self, text: str):
        self.content = [MagicMock(text=text)]


class MockClaudeClient:
    """Mock Anthropic client for testing"""

    def __init__(self, behavior: str = "normal"):
        self.behavior = behavior
        self.call_count = 0
        self.messages = MagicMock()
        self.messages.create = self.create_message

    def create_message(
        self, model: str, messages: List[Dict], max_tokens: int, temperature: float = 0.7
    ) -> MockClaudeResponse:
        """Mock message creation"""
        self.call_count += 1

        # Extract the last user message
        last_message = messages[-1]["content"] if messages else ""

        # Determine response based on behavior and content
        if self.behavior == "normal":
            return self._normal_response(last_message, messages)
        elif self.behavior == "qa_needed":
            return self._qa_response(last_message)
        elif self.behavior == "error":
            raise Exception("Claude API error")
        elif self.behavior == "slow":
            import time

            time.sleep(2)
            return self._normal_response(last_message, messages)
        else:
            return MockClaudeResponse("Unknown behavior")

    def _normal_response(self, prompt: str, messages: List[Dict]) -> MockClaudeResponse:
        """Generate normal responses based on agent role"""
        # Detect agent role from system message
        system_msg = messages[0]["content"] if messages else ""

        if "senior software developer" in system_msg:
            # PM Agent response
            if "implement PRP" in prompt:
                return MockClaudeResponse(self._pm_implementation_response())
            elif "ANSWER:" in prompt:
                return MockClaudeResponse(self._pm_continuation_response())

        elif "senior QA engineer" in system_msg:
            # Validator response
            if "validate the implementation" in prompt:
                return MockClaudeResponse(self._validator_response())

        elif "senior DevOps engineer" in system_msg:
            # Integration response
            if "handle the integration" in prompt:
                return MockClaudeResponse(self._integration_response())

        elif "senior architect" in system_msg:
            # Q&A Orchestrator response
            return MockClaudeResponse(self._qa_answer_response(prompt))

        # Default response
        return MockClaudeResponse("I'll help you with that task.")

    def _pm_implementation_response(self) -> str:
        """Mock PM implementation response"""
        return """I'll implement this PRP step by step.

First, let me understand the requirements and review the existing code structure.

Looking at the PRP, I need to:
1. Create a new feature module
2. Add comprehensive tests
3. Update documentation

Let me start by creating the main implementation file:

```python
# feature.py
class NewFeature:
    def __init__(self):
        self.config = {}
    
    def process(self, data):
        # Implementation logic here
        return {"status": "success", "data": data}
```

Now let me add tests:

```python
# test_feature.py
import pytest
from feature import NewFeature

def test_new_feature():
    feature = NewFeature()
    result = feature.process({"test": "data"})
    assert result["status"] == "success"
```

Running validation with `make quick-check`...

All tests pass! Coverage is at 85%.

```json
{"key": "tests_passed", "value": "true"}
{"key": "coverage_pct", "value": "85"}
{"key": "lint_passed", "value": "true"}
{"key": "implementation_complete", "value": "true"}
{"key": "files_modified", "value": "feature.py,test_feature.py"}
```
"""

    def _pm_continuation_response(self) -> str:
        """Mock PM response after Q&A"""
        return """Thank you for the clarification! Based on your answer, I'll adjust the implementation.

I've updated the code to follow the suggested pattern:

```python
# Updated implementation following the architectural guidance
class NewFeature:
    def __init__(self, config):
        self.config = config
        self.validator = FeatureValidator()
    
    def process(self, data):
        # Validate input
        if not self.validator.validate(data):
            raise ValueError("Invalid input data")
        
        # Process according to requirements
        result = self._internal_process(data)
        return {"status": "success", "data": result}
```

The tests have been updated and all validations pass.

```json
{"key": "tests_passed", "value": "true"}
{"key": "coverage_pct", "value": "88"}
{"key": "lint_passed", "value": "true"}
{"key": "implementation_complete", "value": "true"}
{"key": "files_modified", "value": "feature.py,test_feature.py,validator.py"}
```
"""

    def _validator_response(self) -> str:
        """Mock validator response"""
        return """I'll thoroughly review the PM's implementation.

Reviewing the code changes:

1. **Code Quality**: The implementation follows project conventions and is well-structured.
2. **Test Coverage**: Tests are comprehensive with 85% coverage, which meets our standards.
3. **Security**: No obvious security vulnerabilities detected.
4. **Performance**: The implementation is efficient with O(n) complexity.

The code properly handles edge cases and includes appropriate error handling.

All validation criteria are met.

```json
{"key": "validation_passed", "value": "true"}
{"key": "quality_score", "value": "92"}
{"key": "security_review", "value": "passed"}
{"key": "performance_review", "value": "passed"}
```
"""

    def _integration_response(self) -> str:
        """Mock integration response"""
        return """I'll handle the deployment of these changes.

First, let me check git status:
- feature.py (modified)
- test_feature.py (new file)
- validator.py (new file)

Creating feature branch and committing:

```bash
git checkout -b feat/p0-001-new-feature
git add feature.py test_feature.py validator.py
git commit -m "feat: Implement new feature for P0-001

- Add NewFeature class with validation
- Include comprehensive test coverage (85%)
- Follow project architectural patterns"
```

Pushing to GitHub:
```bash
git push origin feat/p0-001-new-feature
```

Creating PR and monitoring CI...

CI pipeline passed successfully! All checks are green.

```json
{"key": "ci_passed", "value": "true"}
{"key": "deployed", "value": "true"}
{"key": "deployment_url", "value": "https://github.com/user/repo/pull/123"}
{"key": "commit_sha", "value": "abc123def456"}
{"key": "pr_number", "value": "123"}
```
"""

    def _qa_response(self, prompt: str) -> MockClaudeResponse:
        """Generate response that needs Q&A"""
        if self.call_count == 1:
            return MockClaudeResponse(
                """I'm implementing the PRP requirements.

Looking at the code, I need some clarification about the architecture.

QUESTION: Should I follow the existing singleton pattern in the codebase or implement this as a regular class with dependency injection?

I want to ensure the implementation aligns with the project's architectural decisions."""
            )
        else:
            # After Q&A, continue normally
            return self._normal_response(prompt, [])

    def _qa_answer_response(self, prompt: str) -> str:
        """Mock Q&A orchestrator response"""
        if "singleton pattern" in prompt:
            return """Based on the codebase analysis and architectural patterns, you should use dependency injection rather than the singleton pattern.

Looking at the recent refactoring in the codebase:
- File: `core/patterns.py` shows we're moving away from singletons
- The dependency injection container is configured in `config/services.py`
- Recent PRPs (P0-890, P0-891) have established this pattern

Here's the recommended approach:

```python
# In config/services.py
container.register(NewFeature, scope="singleton")

# In your implementation
class NewFeature:
    def __init__(self, config: Config, logger: Logger):
        self.config = config
        self.logger = logger
```

This maintains consistency with the current architectural direction while providing the same benefits as a singleton through the DI container's scope management."""

        return "I can help with that. Based on the codebase analysis, here's my recommendation..."


class MockRedisClient:
    """Mock Redis client for testing"""

    def __init__(self):
        self.data = {}
        self.lists = {}
        self.sets = {}

    def hgetall(self, key: str) -> Dict[bytes, bytes]:
        """Mock hgetall"""
        return self.data.get(key, {})

    def hget(self, key: str, field: str) -> Optional[bytes]:
        """Mock hget"""
        return self.data.get(key, {}).get(field)

    def hset(self, key: str, mapping: Dict) -> None:
        """Mock hset"""
        if key not in self.data:
            self.data[key] = {}
        self.data[key].update({k: v.encode() if isinstance(v, str) else v for k, v in mapping.items()})

    def hincrby(self, key: str, field: str, amount: int) -> int:
        """Mock hincrby"""
        if key not in self.data:
            self.data[key] = {}
        current = int(self.data[key].get(field, b"0"))
        new_value = current + amount
        self.data[key][field] = str(new_value).encode()
        return new_value

    def lrange(self, key: str, start: int, end: int) -> List[bytes]:
        """Mock lrange"""
        lst = self.lists.get(key, [])
        if end == -1:
            return lst[start:]
        return lst[start : end + 1]

    def lpush(self, key: str, *values) -> int:
        """Mock lpush"""
        if key not in self.lists:
            self.lists[key] = []
        for value in reversed(values):
            self.lists[key].insert(0, value.encode() if isinstance(value, str) else value)
        return len(self.lists[key])

    def rpush(self, key: str, value: str) -> int:
        """Mock rpush"""
        if key not in self.lists:
            self.lists[key] = []
        self.lists[key].append(value.encode() if isinstance(value, str) else value)
        return len(self.lists[key])

    def lrem(self, key: str, count: int, value: str) -> int:
        """Mock lrem"""
        if key not in self.lists:
            return 0
        value_bytes = value.encode() if isinstance(value, str) else value
        removed = 0
        if count == 0:
            # Remove all occurrences
            self.lists[key] = [v for v in self.lists[key] if v != value_bytes]
        return removed

    def llen(self, key: str) -> int:
        """Mock llen"""
        return len(self.lists.get(key, []))

    def blmove(self, source: str, destination: str, timeout: float) -> Optional[bytes]:
        """Mock blmove"""
        if source in self.lists and self.lists[source]:
            value = self.lists[source].pop(0)
            if destination not in self.lists:
                self.lists[destination] = []
            self.lists[destination].append(value)
            return value
        return None

    def brpop(self, key: str, timeout: float) -> Optional[tuple]:
        """Mock brpop"""
        if key in self.lists and self.lists[key]:
            value = self.lists[key].pop()
            return (key.encode(), value)
        return None

    def get(self, key: str) -> Optional[bytes]:
        """Mock get"""
        return self.data.get(key)

    def set(self, key: str, value: str) -> None:
        """Mock set"""
        self.data[key] = value.encode() if isinstance(value, str) else value

    def setex(self, key: str, ttl: int, value: str) -> None:
        """Mock setex"""
        self.set(key, value)

    def delete(self, key: str) -> int:
        """Mock delete"""
        deleted = 0
        if key in self.data:
            del self.data[key]
            deleted += 1
        if key in self.lists:
            del self.lists[key]
            deleted += 1
        return deleted

    def keys(self, pattern: str) -> List[bytes]:
        """Mock keys"""
        import fnmatch

        matching_keys = []
        for key in list(self.data.keys()) + list(self.lists.keys()):
            if fnmatch.fnmatch(key, pattern):
                matching_keys.append(key.encode() if isinstance(key, str) else key)
        return matching_keys

    def from_url(self, url: str):
        """Mock from_url - returns self"""
        return self
