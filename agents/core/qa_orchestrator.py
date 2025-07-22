#!/usr/bin/env python3
"""
Q&A Orchestrator - Handles complex questions with full codebase context using Opus 4
"""
import json
import logging
import os
import glob
import time
from datetime import datetime
from typing import Dict, List, Optional

import redis
from anthropic import Anthropic


class QAOrchestrator:
    """Q&A Orchestrator with full codebase access"""
    
    def __init__(self):
        self.model = "claude-3-opus-20240229"  # Using Opus 4 for complex questions
        self.redis_client = redis.from_url("redis://localhost:6379/0")
        self.anthropic_client = Anthropic()
        
        # Setup logging
        self.logger = logging.getLogger("qa_orchestrator")
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        
        # Cache for codebase context
        self.codebase_cache = None
        self.cache_timestamp = None
        self.cache_ttl = 3600  # 1 hour
        
    def run(self):
        """Main Q&A processing loop"""
        self.logger.info("Starting Q&A Orchestrator with Opus 4")
        
        while True:
            try:
                # Check for Q&A requests
                request = self.redis_client.brpop("qa_queue", timeout=5)
                
                if request:
                    _, request_data = request
                    request_json = json.loads(request_data.decode() if isinstance(request_data, bytes) else request_data)
                    self.process_qa_request(request_json)
                    
            except Exception as e:
                self.logger.error(f"Error in Q&A loop: {e}", exc_info=True)
                time.sleep(5)
    
    def process_qa_request(self, request: Dict):
        """Process a single Q&A request"""
        qa_id = request.get("id")
        question = request.get("question")
        agent_role = request.get("role")
        prp_id = request.get("prp_id")
        
        self.logger.info(f"Processing Q&A {qa_id} from {agent_role} about {prp_id}")
        
        try:
            # Build comprehensive context
            context = self.build_qa_context(question, agent_role, prp_id)
            
            # Get answer from Opus 4
            answer = self.get_opus_answer(context, question)
            
            # Store answer for agent to retrieve
            self.redis_client.setex(
                f"qa_answer:{qa_id}",
                300,  # 5 minute TTL
                answer
            )
            
            # Log the Q&A for analysis
            self.log_qa_interaction(qa_id, question, answer, agent_role, prp_id)
            
            self.logger.info(f"Answered Q&A {qa_id}")
            
        except Exception as e:
            self.logger.error(f"Error processing Q&A {qa_id}: {e}", exc_info=True)
            # Store error response
            error_answer = f"I apologize, but I encountered an error processing your question: {str(e)}. Please try rephrasing or ask for help with a specific file or concept."
            self.redis_client.setex(f"qa_answer:{qa_id}", 300, error_answer)
    
    def build_qa_context(self, question: str, agent_role: str, prp_id: str) -> Dict:
        """Build comprehensive context for the question"""
        # Get codebase context (cached)
        codebase_context = self.get_codebase_context()
        
        # Get PRP-specific context
        prp_context = self.get_prp_context(prp_id)
        
        # Get related PRPs
        related_prps = self.find_related_prps(question, prp_id)
        
        # Get agent-specific context
        agent_context = self.get_agent_context(agent_role, prp_id)
        
        return {
            "codebase": codebase_context,
            "current_prp": prp_context,
            "related_prps": related_prps,
            "agent_context": agent_context,
            "question_metadata": {
                "agent_role": agent_role,
                "prp_id": prp_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    
    def get_codebase_context(self) -> Dict[str, str]:
        """Get cached codebase context"""
        # Check if cache is still valid
        if (self.codebase_cache and 
            self.cache_timestamp and 
            time.time() - self.cache_timestamp < self.cache_ttl):
            return self.codebase_cache
        
        self.logger.info("Building codebase context cache")
        
        context = {
            "structure": self.get_project_structure(),
            "key_files": {},
            "documentation": {},
            "configuration": {}
        }
        
        # Load key documentation files
        doc_files = [
            "README.md",
            "CLAUDE.md",
            ".claude/prompts/prp_completion_validator.md",
            ".claude/orchestrator_learnings.md"
        ]
        
        for doc_file in doc_files:
            if os.path.exists(doc_file):
                try:
                    with open(doc_file, 'r') as f:
                        context["documentation"][doc_file] = f.read()
                except Exception as e:
                    self.logger.warning(f"Could not read {doc_file}: {e}")
        
        # Load key configuration files
        config_files = [
            "Makefile",
            "requirements.txt",
            "docker-compose.yml",
            ".github/workflows/ci.yml"
        ]
        
        for config_file in config_files:
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r') as f:
                        context["configuration"][config_file] = f.read()
                except Exception as e:
                    self.logger.warning(f"Could not read {config_file}: {e}")
        
        # Load key Python files (limited to avoid token explosion)
        key_patterns = [
            "agents/core/*.py",
            "agents/roles/*.py",
            "bin/orchestrator*.py",
            "bin/enterprise_shim*.py"
        ]
        
        for pattern in key_patterns:
            for file_path in glob.glob(pattern)[:5]:  # Limit files per pattern
                try:
                    with open(file_path, 'r') as f:
                        context["key_files"][file_path] = f.read()[:3000]  # Truncate large files
                except Exception as e:
                    self.logger.warning(f"Could not read {file_path}: {e}")
        
        # Cache the context
        self.codebase_cache = context
        self.cache_timestamp = time.time()
        
        return context
    
    def get_project_structure(self) -> str:
        """Get a tree-like project structure"""
        # Simple implementation - in production use 'tree' command or similar
        structure = []
        
        for root, dirs, files in os.walk(".", topdown=True):
            # Skip hidden and cache directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules']]
            
            level = root.replace(".", "").count(os.sep)
            indent = " " * 2 * level
            structure.append(f"{indent}{os.path.basename(root)}/")
            
            subindent = " " * 2 * (level + 1)
            for file in files[:10]:  # Limit files shown
                if not file.startswith('.'):
                    structure.append(f"{subindent}{file}")
            
            if len(structure) > 100:  # Limit total lines
                structure.append("... (truncated)")
                break
        
        return "\n".join(structure)
    
    def get_prp_context(self, prp_id: str) -> Dict:
        """Get context about the current PRP"""
        prp_data = self.redis_client.hgetall(f"prp:{prp_id}")
        
        if not prp_data:
            return {"error": f"No data found for PRP {prp_id}"}
        
        # Decode Redis data
        prp_dict = {
            k.decode() if isinstance(k, bytes) else k: 
            v.decode() if isinstance(v, bytes) else v
            for k, v in prp_data.items()
        }
        
        # Get conversation history
        history = {
            "pm": self.get_role_history(prp_id, "pm"),
            "validator": self.get_role_history(prp_id, "validator"),
            "integration": self.get_role_history(prp_id, "integration")
        }
        
        return {
            "data": prp_dict,
            "history": history
        }
    
    def get_role_history(self, prp_id: str, role: str) -> List[Dict]:
        """Get conversation history for a specific role"""
        history_key = f"prp:{prp_id}:history:{role}"
        raw_history = self.redis_client.lrange(history_key, -5, -1)  # Last 5 entries
        
        history = []
        for entry in raw_history:
            try:
                data = json.loads(entry.decode() if isinstance(entry, bytes) else entry)
                history.append({
                    "timestamp": data.get("timestamp"),
                    "summary": data.get("response", "")[:500] + "..."
                })
            except:
                pass
        
        return history
    
    def find_related_prps(self, question: str, current_prp: str) -> List[Dict]:
        """Find PRPs related to the question"""
        related = []
        
        # Get all PRP keys
        prp_keys = self.redis_client.keys("prp:*")
        
        # Simple keyword matching - in production use embeddings
        keywords = question.lower().split()
        
        for key in prp_keys[:50]:  # Limit to avoid overload
            if key.decode().endswith(":history:pm"):  # Skip history keys
                continue
                
            prp_id = key.decode().replace("prp:", "")
            if prp_id == current_prp:
                continue
            
            prp_data = self.redis_client.hgetall(key)
            if prp_data:
                title = prp_data.get(b"title", b"").decode().lower()
                content = prp_data.get(b"content", b"").decode().lower()
                
                # Check for keyword matches
                if any(keyword in title or keyword in content for keyword in keywords):
                    related.append({
                        "id": prp_id,
                        "title": prp_data.get(b"title", b"No title").decode(),
                        "state": prp_data.get(b"state", b"unknown").decode()
                    })
            
            if len(related) >= 5:  # Limit related PRPs
                break
        
        return related
    
    def get_agent_context(self, agent_role: str, prp_id: str) -> Dict:
        """Get context specific to the asking agent"""
        if agent_role == "pm":
            return {
                "role_description": "Project Manager / Developer implementing features",
                "typical_questions": "Architecture decisions, API design, testing strategies",
                "relevant_docs": ["CLAUDE.md", "Makefile", "requirements.txt"]
            }
        elif agent_role == "validator":
            return {
                "role_description": "QA Engineer reviewing code quality and correctness",
                "typical_questions": "Best practices, security concerns, test coverage",
                "relevant_docs": [".claude/prompts/prp_completion_validator.md", "tests/"]
            }
        elif agent_role == "integration":
            return {
                "role_description": "DevOps Engineer handling CI/CD and deployment",
                "typical_questions": "CI failures, deployment issues, git workflows",
                "relevant_docs": [".github/workflows/", "Makefile", "docker-compose.yml"]
            }
        else:
            return {"role_description": f"Unknown role: {agent_role}"}
    
    def get_opus_answer(self, context: Dict, question: str) -> str:
        """Get answer from Opus 4 with full context"""
        # Build system prompt
        system_prompt = """You are the senior architect and technical lead with comprehensive knowledge of the LeadFactory multi-agent system.

You have access to:
1. The complete codebase structure and key files
2. All project documentation and configuration
3. Current and related PRP information
4. Conversation history from all agents

Your role is to provide accurate, detailed answers to help agents complete their tasks successfully.

When answering:
1. Be specific and provide code examples when relevant
2. Reference actual files and line numbers when possible
3. Consider the asking agent's role and current task
4. Provide actionable guidance
5. Clarify any ambiguities in the question

If the question relates to:
- Architecture: Explain design decisions and patterns
- Implementation: Provide specific code examples and file locations
- Testing: Suggest test strategies and point to existing examples
- CI/CD: Help debug issues and explain workflows
- Best practices: Reference project standards in CLAUDE.md"""

        # Build user prompt with context
        user_prompt = f"""An agent needs help with their current task.

AGENT CONTEXT:
Role: {context['question_metadata']['agent_role']}
Current PRP: {context['question_metadata']['prp_id']}
{json.dumps(context['agent_context'], indent=2)}

CURRENT PRP:
{json.dumps(context['current_prp']['data'], indent=2)}

PROJECT STRUCTURE:
{context['codebase']['structure'][:1000]}...

KEY DOCUMENTATION:
{self._summarize_docs(context['codebase']['documentation'])}

RELATED PRPs:
{json.dumps(context['related_prps'], indent=2)}

QUESTION:
{question}

Please provide a comprehensive answer that helps the agent proceed with their task."""

        try:
            response = self.anthropic_client.messages.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=8000,
                temperature=0.3  # Lower temperature for factual answers
            )
            
            return response.content[0].text
            
        except Exception as e:
            self.logger.error(f"Opus API error: {e}")
            return f"I apologize, but I encountered an error accessing Opus 4: {str(e)}. As a fallback, please check the documentation in CLAUDE.md or try asking a more specific question."
    
    def _summarize_docs(self, docs: Dict[str, str]) -> str:
        """Summarize documentation for context"""
        summary = []
        for file_path, content in docs.items():
            # Extract key sections
            lines = content.split('\n')
            key_lines = [line for line in lines if line.strip() and 
                        (line.startswith('#') or line.startswith('**') or 'IMPORTANT' in line)]
            summary.append(f"\n{file_path}:\n" + "\n".join(key_lines[:20]))
        
        return "\n".join(summary)[:3000]  # Limit size
    
    def log_qa_interaction(self, qa_id: str, question: str, answer: str, agent_role: str, prp_id: str):
        """Log Q&A interaction for analysis"""
        interaction = {
            "id": qa_id,
            "timestamp": datetime.utcnow().isoformat(),
            "agent_role": agent_role,
            "prp_id": prp_id,
            "question": question,
            "answer_preview": answer[:200] + "...",
            "answer_length": len(answer)
        }
        
        # Store in Redis list for analysis
        self.redis_client.lpush("qa_history", json.dumps(interaction))
        self.redis_client.ltrim("qa_history", 0, 999)  # Keep last 1000 Q&As


if __name__ == "__main__":
    orchestrator = QAOrchestrator()
    orchestrator.run()