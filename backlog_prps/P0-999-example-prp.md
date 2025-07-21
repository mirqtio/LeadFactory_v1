---
id: P0-999
title: Example PRP for Stack Testing
description: Sample PRP to demonstrate the automated ingest system
priority_stage: dev
status: new
priority: high
dependencies: []
---

# P0-999: Example PRP for Stack Testing

## Overview
This is a sample PRP that demonstrates the automated backlog ingest system for the LeadFactory multi-agent stack.

## Requirements
1. Parse PRP metadata from front matter
2. Queue PRP in appropriate Redis queue based on priority_stage
3. Store complete PRP data in Redis hash
4. Notify orchestrator of successful ingest

## Acceptance Criteria
- [ ] PRP metadata extracted correctly
- [ ] PRP queued in dev_queue
- [ ] Redis hash created with all fields
- [ ] Orchestrator receives ingest notification

## Technical Notes
- Uses YAML front matter for metadata
- Supports multiple priority stages: dev, validation, integration
- Integrates with existing Redis queue infrastructure
- Compatible with multi-agent orchestration system

## Implementation Details
The ingest script will:
1. Scan backlog_prps/ directory for .md files
2. Parse YAML front matter for metadata
3. Create Redis hash: prp:P0-999
4. Add to appropriate queue based on priority_stage
5. Send broadcast notification to orchestrator

This PRP will be automatically removed after successful testing.