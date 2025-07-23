#!/usr/bin/env python3
"""
Base Agent Worker - Core functionality for all agent types
"""
import json
import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis
from anthropic import Anthropic

from .config import config


class AgentWorker:
    """Base class for all agent workers"""

    def __init__(self, role: str, agent_id: str, model: str = None):
        self.role = role
        self.agent_id = agent_id
        self.model = model or config.get_model_for_role(role)
        self.queue = f"{role}_queue"

        # Initialize connections
        self.redis_client = redis.from_url(config.redis_url)
        self.anthropic_client = Anthropic(api_key=config.anthropic_api_key)

        # Setup logging
        self.logger = logging.getLogger(f"{role}.{agent_id}")
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

        self.current_prp = None
        self.conversation_history = []

    def run(self):
        """Main worker loop"""
        self.logger.info(f"Starting {self.agent_id} worker")

        while True:
            try:
                # Atomic move from queue to inflight
                prp_id = self.redis_client.blmove(self.queue, f"{self.queue}:inflight", timeout=5.0)

                if prp_id:
                    prp_id = prp_id.decode() if isinstance(prp_id, bytes) else prp_id
                    self.logger.info(f"Processing PRP: {prp_id}")
                    self.process_prp(prp_id)
                else:
                    # No work available, update status
                    self.update_agent_status("idle")

            except Exception as e:
                self.logger.error(f"Error in worker loop: {e}", exc_info=True)
                time.sleep(5)

    def process_prp(self, prp_id: str):
        """Process a single PRP"""
        self.current_prp = prp_id
        self.update_agent_status("active", prp_id)

        try:
            # Load PRP data
            prp_data = self.load_prp_data(prp_id)
            if not prp_data:
                self.logger.error(f"No data found for PRP: {prp_id}")
                self.requeue_prp(prp_id, "No PRP data found")
                return

            # Load conversation history
            self.conversation_history = self.load_conversation_history(prp_id)

            # Build context for this agent
            context = self.build_context(prp_id, prp_data)

            # Process until complete or blocked
            max_iterations = 10
            iteration = 0

            while iteration < max_iterations and not self.is_task_complete(prp_id):
                iteration += 1
                self.logger.info(f"Iteration {iteration} for {prp_id}")

                # Get Claude's response
                response = self.get_claude_response(context)
                if not response:
                    self.logger.error("Failed to get Claude response")
                    break

                # Save to history
                self.save_conversation_turn(prp_id, context, response)

                # Process response
                result = self.process_response(prp_id, response)

                if result.get("needs_qa"):
                    # Handle Q&A
                    answer = self.handle_qa(result["question"], prp_id)
                    if answer:
                        context = self.build_followup_context(response, answer)
                    else:
                        self.logger.warning("No answer received for question")
                        break

                elif result.get("complete"):
                    # Task complete
                    self.handle_completion(prp_id, result.get("evidence", {}))
                    break

                else:
                    # Continue processing
                    context = self.build_continuation_context(prp_id, response)

            if iteration >= max_iterations:
                self.logger.warning(f"Max iterations reached for {prp_id}")
                self.requeue_prp(prp_id, "Max iterations reached")

        except Exception as e:
            self.logger.error(f"Error processing PRP {prp_id}: {e}", exc_info=True)
            self.requeue_prp(prp_id, str(e))
        finally:
            self.current_prp = None
            self.update_agent_status("idle")

    def get_claude_response(self, context: Dict[str, Any]) -> Optional[str]:
        """Get response from Claude API"""
        try:
            # Separate system message from user messages
            messages = context["messages"]
            system_content = None
            user_messages = []

            for msg in messages:
                if msg["role"] == "system":
                    system_content = msg["content"]
                else:
                    user_messages.append(msg)

            # Create API call with proper format
            kwargs = {"model": self.model, "messages": user_messages, "max_tokens": 8000, "temperature": 0.7}

            if system_content:
                kwargs["system"] = system_content

            response = self.anthropic_client.messages.create(**kwargs)
            return response.content[0].text
        except Exception as e:
            self.logger.error(f"Claude API error: {e}")
            return None

    def extract_evidence(self, response: str) -> Dict[str, str]:
        """Extract evidence from JSON blocks in response"""
        evidence = {}

        # Find all JSON blocks
        json_blocks = re.findall(r"```json\n(.*?)\n```", response, re.DOTALL)

        for block in json_blocks:
            # Handle multiple JSON objects in one block (one per line)
            lines = block.strip().split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if isinstance(data, dict) and "key" in data and "value" in data:
                        evidence[data["key"]] = data["value"]
                    elif isinstance(data, dict):
                        # If it's a dict without key/value format, merge it
                        evidence.update(data)
                except json.JSONDecodeError:
                    continue

            # If no evidence found from line-by-line, try parsing the entire block
            if not evidence:
                try:
                    # Try to parse the whole block as a single JSON object
                    data = json.loads(block)
                    if isinstance(data, dict) and "key" in data and "value" in data:
                        evidence[data["key"]] = data["value"]
                    elif isinstance(data, dict):
                        evidence.update(data)
                except json.JSONDecodeError:
                    # Try to extract key-value pairs from pretty-printed JSON
                    try:
                        # Handle pretty-printed JSON with multiple objects
                        # Find all complete JSON objects in the block
                        json_objects = re.findall(r"\{[^{}]*\}", block.replace("\n", " "))
                        for obj_str in json_objects:
                            try:
                                obj = json.loads(obj_str)
                                if "key" in obj and "value" in obj:
                                    evidence[obj["key"]] = obj["value"]
                            except json.JSONDecodeError:
                                continue
                    except Exception:
                        self.logger.warning(f"Failed to parse JSON block: {block[:100]}...")

        return evidence

    def extract_question(self, response: str) -> Optional[str]:
        """Extract question from response"""
        # Look for QUESTION: pattern
        match = re.search(r"QUESTION:\s*(.+?)(?:\n|$)", response)
        if match:
            return match.group(1).strip()
        return None

    def process_response(self, prp_id: str, response: str) -> Dict[str, Any]:
        """Process Claude's response"""
        result = {}

        # Check for questions
        question = self.extract_question(response)
        if question:
            result["needs_qa"] = True
            result["question"] = question
            return result

        # Extract evidence
        evidence = self.extract_evidence(response)
        if evidence:
            # Save evidence to Redis
            for key, value in evidence.items():
                # Convert lists to JSON strings for Redis storage
                if isinstance(value, list):
                    value = json.dumps(value)
                elif not isinstance(value, str):
                    value = str(value)
                self.redis_client.hset(f"prp:{prp_id}", key, value)

            # Check if task is complete based on evidence
            if self.check_completion_criteria(prp_id, evidence):
                result["complete"] = True
                result["evidence"] = evidence

        return result

    def handle_qa(self, question: str, prp_id: str) -> Optional[str]:
        """Handle Q&A with orchestrator"""
        qa_id = f"qa-{self.agent_id}-{int(time.time())}"

        # Submit question
        qa_request = {
            "id": qa_id,
            "agent": self.agent_id,
            "role": self.role,
            "prp_id": prp_id,
            "question": question,
            "timestamp": datetime.utcnow().isoformat(),
        }

        self.redis_client.lpush("qa_queue", json.dumps(qa_request))
        self.logger.info(f"Submitted Q&A request: {qa_id}")

        # Wait for answer
        start_time = time.time()
        timeout = 300  # 5 minutes

        while time.time() - start_time < timeout:
            answer = self.redis_client.get(f"qa_answer:{qa_id}")
            if answer:
                answer_text = answer.decode() if isinstance(answer, bytes) else answer
                self.redis_client.delete(f"qa_answer:{qa_id}")
                self.logger.info(f"Received answer for {qa_id}")
                return answer_text
            time.sleep(2)

        self.logger.warning(f"Q&A timeout for {qa_id}")
        return None

    def handle_completion(self, prp_id: str, evidence: Dict[str, str]):
        """Handle PRP completion"""
        self.logger.info(f"Completing PRP {prp_id} with evidence: {evidence}")

        # Update PRP state
        completion_time = datetime.utcnow().isoformat()
        self.redis_client.hset(
            f"prp:{prp_id}",
            mapping={f"{self.role}_completed_at": completion_time, f"{self.role}_completed_by": self.agent_id},
        )

        # Move to next queue
        next_queue = self.get_next_queue()
        if next_queue:
            self.redis_client.lrem(f"{self.queue}:inflight", 0, prp_id)
            self.redis_client.lpush(next_queue, prp_id)
            self.logger.info(f"Promoted {prp_id} to {next_queue}")
        else:
            # Final stage - mark as complete
            self.redis_client.lrem(f"{self.queue}:inflight", 0, prp_id)
            self.redis_client.hset(f"prp:{prp_id}", "state", "complete")
            self.logger.info(f"PRP {prp_id} fully complete")

    def requeue_prp(self, prp_id: str, reason: str):
        """Requeue PRP for retry"""
        retry_count = int(self.redis_client.hget(f"prp:{prp_id}", "retry_count") or 0)

        if retry_count >= 3:
            # Too many retries, move to failed state
            self.redis_client.lrem(f"{self.queue}:inflight", 0, prp_id)
            self.redis_client.hset(
                f"prp:{prp_id}",
                mapping={"state": "failed", "failed_reason": reason, "failed_at": datetime.utcnow().isoformat()},
            )
            self.logger.error(f"PRP {prp_id} failed after {retry_count} retries: {reason}")
        else:
            # Increment retry count and requeue
            self.redis_client.hincrby(f"prp:{prp_id}", "retry_count", 1)
            self.redis_client.hset(f"prp:{prp_id}", "last_error", reason)
            self.redis_client.lrem(f"{self.queue}:inflight", 0, prp_id)
            self.redis_client.lpush(self.queue, prp_id)
            self.logger.warning(f"Requeued {prp_id} (retry {retry_count + 1}): {reason}")

    # Helper methods

    def load_prp_data(self, prp_id: str) -> Dict[str, str]:
        """Load PRP data from Redis"""
        data = self.redis_client.hgetall(f"prp:{prp_id}")
        return {
            k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v
            for k, v in data.items()
        }

    def load_conversation_history(self, prp_id: str) -> List[Dict[str, str]]:
        """Load conversation history for PRP"""
        history_key = f"prp:{prp_id}:history:{self.role}"
        history = self.redis_client.lrange(history_key, 0, -1)

        return [json.loads(h.decode() if isinstance(h, bytes) else h) for h in history]

    def save_conversation_turn(self, prp_id: str, context: Dict, response: str):
        """Save conversation turn to history"""
        turn = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent": self.agent_id,
            "prompt": context.get("messages", [])[-1].get("content", ""),
            "response": response,
        }

        history_key = f"prp:{prp_id}:history:{self.role}"
        self.redis_client.rpush(history_key, json.dumps(turn))

    def update_agent_status(self, status: str, current_prp: str = ""):
        """Update agent status in Redis"""
        self.redis_client.hset(
            f"agent:{self.agent_id}",
            mapping={
                "status": status,
                "current_prp": current_prp,
                "last_activity": datetime.utcnow().isoformat(),
                "role": self.role,
            },
        )

    # Methods to be overridden by subclasses

    def build_context(self, prp_id: str, prp_data: Dict[str, str]) -> Dict[str, Any]:
        """Build initial context for Claude - Override in subclass"""
        raise NotImplementedError("Subclasses must implement build_context")

    def check_completion_criteria(self, prp_id: str, evidence: Dict[str, str]) -> bool:
        """Check if task is complete - Override in subclass"""
        raise NotImplementedError("Subclasses must implement check_completion_criteria")

    def get_next_queue(self) -> Optional[str]:
        """Get next queue for promotion - Override in subclass"""
        raise NotImplementedError("Subclasses must implement get_next_queue")

    def is_task_complete(self, prp_id: str) -> bool:
        """Check if task is already complete"""
        prp_data = self.load_prp_data(prp_id)
        return prp_data.get(f"{self.role}_completed_at") is not None

    def build_followup_context(self, previous_response: str, answer: str) -> Dict[str, Any]:
        """Build context for follow-up after Q&A"""
        return {
            "messages": self.conversation_history
            + [
                {"role": "assistant", "content": previous_response},
                {"role": "user", "content": f"ANSWER: {answer}\n\nPlease continue with the task."},
            ]
        }

    def build_continuation_context(self, prp_id: str, previous_response: str) -> Dict[str, Any]:
        """Build context for continuation"""
        return {
            "messages": self.conversation_history
            + [
                {"role": "assistant", "content": previous_response},
                {
                    "role": "user",
                    "content": "Please continue with the task. If complete, output the evidence JSON blocks.",
                },
            ]
        }
