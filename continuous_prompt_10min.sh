#!/bin/bash
while true; do
    ./schedule_with_note.sh 10 "🚨 ORCHESTRATOR ACTIVE CHECK 🚨
1. Check all 3 agents working on P0-016
2. Assess completion readiness - are test failures fixed?
3. Launch PM hierarchy if P0-016 done
4. Execute specific actions - NO PASSIVITY

RESPOND TO THIS PROMPT NOW!" orchestrator:0
    sleep 600  # Wait 10 minutes
done
