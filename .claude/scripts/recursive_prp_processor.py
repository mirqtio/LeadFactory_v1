#!/usr/bin/env python3
"""
Recursive PRP Processor for LeadFactory

This script:
1. Parses INITIAL.md to extract tasks
2. Generates PRP files following the naming convention: PRP-{priority}-{title-slug}.md
3. Executes PRPs sequentially, checking dependencies
4. Tracks progress and handles failures
"""

import re
import os
import sys
import json
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional
import time

# Import enhancement data
try:
    from prp_enhancements import BUSINESS_LOGIC, OUTCOME_CRITERIA, CODE_EXAMPLES, ROLLBACK_STRATEGIES
except ImportError:
    # If run from different directory
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from prp_enhancements import BUSINESS_LOGIC, OUTCOME_CRITERIA, CODE_EXAMPLES, ROLLBACK_STRATEGIES


@dataclass
class Task:
    """Represents a task from INITIAL.md"""
    priority: str  # P0-000, P1-010, etc.
    title: str
    dependencies: List[str]
    goal: str
    integration_points: List[str]
    tests_to_pass: List[str]
    acceptance_criteria: List[str]
    wave: str  # A or B
    
    @property
    def slug(self):
        """Generate slug from title"""
        return re.sub(r'[^a-z0-9-]+', '-', self.title.lower()).strip('-')
    
    @property
    def prp_filename(self):
        """Generate PRP filename following convention"""
        return f"PRP-{self.priority}-{self.slug}.md"


class InitialMDParser:
    """Parse INITIAL.md to extract tasks"""
    
    def __init__(self, initial_md_path: str):
        self.path = Path(initial_md_path)
        if not self.path.exists():
            raise FileNotFoundError(f"INITIAL.md not found at {initial_md_path}")
        
        with open(self.path, 'r') as f:
            self.content = f.read()
    
    def parse_tasks(self) -> List[Task]:
        """Extract all tasks from INITIAL.md"""
        tasks = []
        
        # Split into Wave A and Wave B sections
        wave_a_match = re.search(r'## Wave A - Stabilize.*?(?=## Wave B)', self.content, re.DOTALL)
        wave_b_match = re.search(r'## Wave B - Expand.*?(?=## Implementation Notes|$)', self.content, re.DOTALL)
        
        if wave_a_match:
            tasks.extend(self._parse_wave_tasks(wave_a_match.group(0), 'A'))
        
        if wave_b_match:
            tasks.extend(self._parse_wave_tasks(wave_b_match.group(0), 'B'))
        
        return tasks
    
    def _parse_wave_tasks(self, wave_content: str, wave: str) -> List[Task]:
        """Parse tasks from a wave section"""
        tasks = []
        
        # Find all task sections (### P0-000 Title)
        task_pattern = r'### (P\d+-\d+) ([^\n]+)\n(.*?)(?=###|$)'
        
        for match in re.finditer(task_pattern, wave_content, re.DOTALL):
            priority = match.group(1)
            title = match.group(2).strip()
            task_content = match.group(3)
            
            # Extract components
            dependencies = self._extract_field(task_content, "Dependencies")
            goal = self._extract_field(task_content, "Goal")
            integration_points = self._extract_list(task_content, "Integration Points")
            tests_to_pass = self._extract_list(task_content, "Tests to Pass")
            acceptance_criteria = self._extract_list(task_content, "Acceptance Criteria")
            
            task = Task(
                priority=priority,
                title=title,
                dependencies=dependencies.split(', ') if dependencies and dependencies != 'None' else [],
                goal=goal,
                integration_points=integration_points,
                tests_to_pass=tests_to_pass,
                acceptance_criteria=acceptance_criteria,
                wave=wave
            )
            tasks.append(task)
        
        return tasks
    
    def _extract_field(self, content: str, field_name: str) -> str:
        """Extract a single-line field value"""
        pattern = rf'\*\*{field_name}\*\*:\s*([^\n]+)'
        match = re.search(pattern, content)
        return match.group(1).strip() if match else ""
    
    def _extract_list(self, content: str, field_name: str) -> List[str]:
        """Extract a list of items under a field"""
        items = []
        
        # Find the field header
        pattern = rf'\*\*{field_name}\*\*:(.*?)(?=\*\*|\Z)'
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            list_content = match.group(1)
            # Extract list items (- item or 1. item)
            item_pattern = r'(?:^|\n)\s*(?:-|\d+\.)\s+(.+?)(?=\n(?:\s*(?:-|\d+\.)|$))'
            items = []
            for m in re.finditer(item_pattern, list_content, re.MULTILINE):
                item_text = m.group(1).strip()
                # Remove any existing checkbox markers to avoid duplication
                item_text = re.sub(r'^\[\s*\]\s*', '', item_text).strip()
                items.append(item_text)
        
        return items


class PRPGenerator:
    """Generate PRP files from tasks"""
    
    def __init__(self, prp_dir: str = ".claude/PRPs"):
        self.prp_dir = Path(prp_dir)
        self.prp_dir.mkdir(parents=True, exist_ok=True)
        
        # Load additional context files
        self.claude_md_content = self._load_file("CLAUDE.md")
        self.current_state_content = self._load_file("CURRENT_STATE.md")
        self.reference_map = self._load_reference_map()
    
    def _load_file(self, filename: str) -> str:
        """Load content from a file if it exists"""
        path = Path(filename)
        if path.exists():
            with open(path, 'r') as f:
                return f.read()
        return ""
    
    def _load_reference_map(self) -> Dict[str, Dict[str, str]]:
        """Load reference map for examples and references"""
        path = Path("examples/REFERENCE_MAP.md")
        reference_map = {}
        
        if path.exists():
            with open(path, 'r') as f:
                content = f.read()
                
            # Parse reference map entries
            pattern = r'\| \*\*(P\d+-\d+)\*\*.*?\| ([^|]+) \| ([^|]+) \|'
            for match in re.finditer(pattern, content):
                task_id = match.group(1)
                example = match.group(2).strip()
                reference = match.group(3).strip()
                reference_map[task_id] = {
                    'example': example,
                    'reference': reference
                }
        
        return reference_map
    
    def generate_prp(self, task: Task) -> Path:
        """Generate a PRP file for a task"""
        prp_path = self.prp_dir / task.prp_filename
        
        # Build PRP content
        prp_content = self._build_prp_content(task)
        
        with open(prp_path, 'w') as f:
            f.write(prp_content)
        
        return prp_path
    
    def _build_prp_content(self, task: Task) -> str:
        """Build PRP content from task"""
        # Convert lists to markdown
        deps = "\n".join([f"- {dep}" for dep in task.dependencies]) if task.dependencies else "- None"
        
        # Add clarity to dependencies
        if task.dependencies and task.priority != "P0-000":
            deps += f"\n\n**Note**: Depends on {', '.join(task.dependencies)} completing successfully in the same CI run."
        
        integration = "\n".join([f"- {item}" for item in task.integration_points])
        tests = "\n".join([f"- {test}" for test in task.tests_to_pass])
        
        # Get business logic and outcome criteria
        business_logic = BUSINESS_LOGIC.get(task.priority, task.goal)
        outcome_criteria = OUTCOME_CRITERIA.get(task.priority, "")
        
        # Get code example if available
        code_example = CODE_EXAMPLES.get(task.priority, "")
        
        # Get example and reference from reference map
        ref_info = self.reference_map.get(task.priority, {})
        example_path = ref_info.get('example', '')
        reference = ref_info.get('reference', '')
        
        # Get rollback strategy
        rollback = ROLLBACK_STRATEGIES.get(task.priority, "git revert commit")
        
        # Build validation commands
        validation_commands = []
        
        # Add task-specific tests if any
        if task.tests_to_pass:
            validation_commands.append("# Run task-specific tests")
            for test in task.tests_to_pass:
                # Clean up test specifications
                if test.startswith('pytest '):
                    # Already a pytest command
                    validation_commands.append(test)
                elif test.endswith('.py'):
                    # Just a file path
                    validation_commands.append(f"pytest {test} -xvs")
                elif test.startswith('tests/'):
                    # Test path without pytest
                    validation_commands.append(f"pytest {test} -xvs")
                elif 'alembic' in test:
                    # Alembic commands
                    validation_commands.append(test)
                elif 'docker' in test.lower():
                    # Docker commands
                    validation_commands.append(test)
                else:
                    # Other validation commands
                    validation_commands.append(f"# {test}")
        
        # Add standard validation based on wave
        validation_commands.append("\n# Run standard validation")
        if task.wave == 'A':
            validation_commands.append("bash scripts/validate_wave_a.sh")
        else:
            validation_commands.append("bash scripts/validate_wave_b.sh")
        
        if task.priority in ["P0-003", "P0-004", "P0-011", "P0-012"]:
            validation_commands.append("\n# Docker/deployment specific validation")
            validation_commands.append("docker build -f Dockerfile.test -t leadfactory-test .")
        
        validation_cmd_str = '\n'.join(validation_commands)
        
        return f"""# PRP: {task.title}

## Task ID: {task.priority}
## Wave: {task.wave}

## Business Logic (Why This Matters)
{business_logic}

## Overview
{task.goal}

## Dependencies
{deps}

## Outcome-Focused Acceptance Criteria
{outcome_criteria}

### Task-Specific Acceptance Criteria
{"\n".join([f"- [ ] {criterion}" for criterion in task.acceptance_criteria])}

### Additional Requirements
- [ ] Ensure overall test coverage ≥ 80% after implementation
- [ ] Update relevant documentation (README, docs/) if behavior changes
- [ ] No performance regression (merge operations remain O(n))
- [ ] Only modify files within specified integration points (no scope creep)

## Integration Points
{integration}

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

## Tests to Pass
{tests}

{code_example}

## Example File/Pattern
{example_path}

## Reference Documentation
{reference}

## Implementation Guide

### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure all dependencies show "completed"
- Verify CI is green before starting

### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Docker must be running for infrastructure tasks
- Activate virtual environment: `source venv/bin/activate`
- Set `USE_STUBS=true` for local development

### Step 3: Implementation
1. Review the business logic and acceptance criteria
2. Study the example code/file pattern
3. Implement changes following CLAUDE.md standards
4. Ensure no deprecated features (see CURRENT_STATE.md below)

### Step 4: Testing
- Run all tests listed in "Tests to Pass" section
- Verify KEEP suite remains green
- Check coverage hasn't decreased

### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix({task.priority}): {task.title}`

## Validation Commands
```bash
{validation_cmd_str}
```

## Rollback Strategy
**Rollback**: {rollback}

## Feature Flag Requirements
{"No new feature flag required - this fix is unconditional." if task.wave == "A" else "Feature flag required: See integration points for flag name."}

## Success Criteria
- All specified tests passing
- Outcome-focused acceptance criteria verified
- Coverage ≥ 80% maintained
- CI green after push
- No performance regression

## Critical Context

### From CLAUDE.md (Project Instructions)
```markdown
{self.claude_md_content}
```

### From CURRENT_STATE.md (Current State vs PRD)
```markdown
{self.current_state_content}
```

**IMPORTANT**: The CURRENT_STATE.md document above contains critical information about:
- Features that have been REMOVED (like Yelp integration)
- Current implementation decisions that differ from the original PRD
- The DO NOT IMPLEMENT section that must be respected
- Current provider status and what's actually being used

Always follow CURRENT_STATE.md when there's any conflict with older documentation.
"""


class PRPExecutor:
    """Execute PRPs sequentially with dependency checking"""
    
    def __init__(self, progress_file: str = ".claude/prp_progress.json"):
        self.progress_file = Path(progress_file)
        self.progress = self._load_progress()
    
    def _load_progress(self) -> Dict[str, str]:
        """Load execution progress"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_progress(self):
        """Save execution progress"""
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)
    
    def can_execute(self, task: Task) -> bool:
        """Check if task dependencies are satisfied"""
        for dep in task.dependencies:
            if dep not in self.progress or self.progress[dep] != "completed":
                return False
        return True
    
    def execute_prp(self, task: Task, prp_path: Path) -> bool:
        """Execute a single PRP using Claude"""
        if task.priority in self.progress and self.progress[task.priority] == "completed":
            print(f"✓ Task {task.priority} already completed")
            return True
        
        if not self.can_execute(task):
            print(f"⚠️  Task {task.priority} has unsatisfied dependencies")
            return False
        
        print(f"\n{'='*60}")
        print(f"Executing PRP: {task.priority} - {task.title}")
        print(f"{'='*60}\n")
        
        # Mark as in progress
        self.progress[task.priority] = "in_progress"
        self._save_progress()
        
        # Execute using Claude (this would be the actual Claude command)
        # For now, we'll create a placeholder that shows what would be executed
        claude_command = f"claude execute-prp {prp_path}"
        print(f"Would execute: {claude_command}")
        
        # Simulate execution (replace with actual Claude call)
        success = self._simulate_execution(task)
        
        if success:
            self.progress[task.priority] = "completed"
            print(f"✓ Task {task.priority} completed successfully")
        else:
            self.progress[task.priority] = "failed"
            print(f"✗ Task {task.priority} failed")
        
        self._save_progress()
        return success
    
    def _simulate_execution(self, task: Task) -> bool:
        """Simulate PRP execution (replace with actual implementation)"""
        # This is where you'd actually call Claude to execute the PRP
        # For now, just return True to simulate success
        time.sleep(1)  # Simulate work
        return True


def main():
    """Main execution flow"""
    # Parse command line arguments
    if len(sys.argv) < 2:
        print("Usage: python recursive_prp_processor.py [generate|execute|status]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    # Initialize components
    parser = InitialMDParser("INITIAL.md")
    generator = PRPGenerator()
    executor = PRPExecutor()
    
    # Parse tasks
    tasks = parser.parse_tasks()
    print(f"Found {len(tasks)} tasks in INITIAL.md")
    
    if command == "generate":
        # Generate all PRPs
        print("\nGenerating PRPs...")
        for task in tasks:
            prp_path = generator.generate_prp(task)
            print(f"✓ Generated {prp_path}")
        print(f"\nGenerated {len(tasks)} PRP files in .claude/PRPs/")
    
    elif command == "execute":
        # Execute PRPs in order
        print("\nExecuting PRPs...")
        
        # Separate by wave
        wave_a_tasks = [t for t in tasks if t.wave == 'A']
        wave_b_tasks = [t for t in tasks if t.wave == 'B']
        
        # Execute Wave A first
        print("\n=== WAVE A: Stabilize ===")
        for task in wave_a_tasks:
            prp_path = generator.prp_dir / task.prp_filename
            if not prp_path.exists():
                print(f"⚠️  PRP not found: {prp_path}")
                continue
            
            success = executor.execute_prp(task, prp_path)
            if not success and task.priority.startswith("P0"):
                print("\n❌ Critical P0 task failed. Stopping execution.")
                break
        
        # Check if all Wave A completed before starting Wave B
        wave_a_complete = all(
            executor.progress.get(t.priority) == "completed" 
            for t in wave_a_tasks
        )
        
        if wave_a_complete:
            print("\n=== WAVE B: Expand ===")
            for task in wave_b_tasks:
                prp_path = generator.prp_dir / task.prp_filename
                if not prp_path.exists():
                    print(f"⚠️  PRP not found: {prp_path}")
                    continue
                
                executor.execute_prp(task, prp_path)
        else:
            print("\n⚠️  Wave A not complete. Cannot start Wave B.")
    
    elif command == "status":
        # Show execution status
        print("\nPRP Execution Status:")
        print("-" * 40)
        
        for task in tasks:
            status = executor.progress.get(task.priority, "pending")
            status_icon = {
                "completed": "✓",
                "in_progress": "🔄",
                "failed": "✗",
                "pending": "⏳"
            }[status]
            
            print(f"{status_icon} {task.priority} - {task.title}")
        
        # Summary
        completed = sum(1 for t in tasks if executor.progress.get(t.priority) == "completed")
        print(f"\nProgress: {completed}/{len(tasks)} tasks completed")
    
    else:
        print(f"Unknown command: {command}")
        print("Usage: python recursive_prp_processor.py [generate|execute|status]")
        sys.exit(1)


if __name__ == "__main__":
    main()