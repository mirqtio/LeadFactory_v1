# PRP Executor Tool

This is a standalone tool for executing PRPs through a multi-agent workflow.
It runs on your dev machine and pushes real code to your VPS via GitHub.

## ⚠️ WARNING
This tool executes real shell commands and makes actual git commits/pushes.
Only run PRPs you trust!

## Setup
```bash
cd tools/prp-executor
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

## Usage
```bash
# Execute a single PRP
python prp_executor.py /path/to/PRP-001.md

# Execute with Q&A support
python prp_executor.py /path/to/PRP-001.md --enable-qa

# Dry run (show what would be executed)
python prp_executor.py /path/to/PRP-001.md --dry-run
```

## Architecture
- PM Agent (Sonnet 4): Implements the PRP
- Validator Agent (Sonnet 4): Reviews code quality
- Integration Agent (Sonnet 4): Deploys to GitHub
- Q&A Orchestrator (Opus 4): Answers complex questions

This tool is NOT part of the main project and should not be deployed.