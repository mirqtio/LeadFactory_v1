# Multi-Agent Orchestration System - BDD Test Plan

## Overview

This test plan validates the complete functionality of the multi-agent orchestration system using Behavior-Driven Development (BDD) principles. The automated test suite can diagnose issues and apply fixes recursively until all tests pass.

## Test Architecture

### Components Under Test
1. **Orchestrator Loop** - External Python monitoring process
2. **Enterprise Shims** - Redis-to-tmux message bridges (5 instances)
3. **Claude Agents** - Orchestrator, Dev-1, Dev-2, Validator, Integrator
4. **Redis Queues** - dev_queue, validation_queue, integration_queue, orchestrator_queue
5. **Message Routing** - JSON messages vs PRP IDs
6. **Evidence-Based Promotion** - Lua scripts for atomic state transitions

### Test Execution Flow
1. Start with clean system state
2. Run each scenario
3. If failure detected:
   - Diagnose root cause
   - Apply targeted fix
   - Retry scenario (max 3 attempts)
4. Continue until all scenarios pass
5. Generate summary report

## Test Scenarios

### 1. System Startup
**Given** the system is not running  
**When** I start the system with `./start_stack.sh`  
**Then** all components should be running within 30 seconds

**Validates**:
- Tmux session creation
- All 5 Claude agents start with correct context
- Enterprise shims connect to Redis queues
- Orchestrator loop begins monitoring
- Redis connectivity

**Common Issues & Fixes**:
- Tmux session conflicts → Kill existing session
- Shims not starting → Check Python path and permissions
- Redis connection failed → Verify Redis is running

### 2. Orchestrator Receives Notifications
**Given** the system is running  
**When** the orchestrator loop sends a progress report  
**Then** the orchestrator agent should receive and display it

**Validates**:
- JSON message handling in enterprise shim
- Message routing to correct agent
- Orchestrator shim processes different message types
- Progress report formatting

**Common Issues & Fixes**:
- JSON parsing errors → Update shim message handling
- Message not delivered → Restart orchestrator shim
- Queue congestion → Clear orchestrator queue

### 3. PRP Assignment to Dev Agent
**Given** a PRP exists in Redis  
**When** the PRP is queued to dev_queue  
**Then** a dev agent should receive the assignment

**Validates**:
- PRP data storage in Redis hash
- Queue operations (LPUSH/BLMOVE)
- Dev shim message formatting
- Agent receives minimal context (no overflow)
- Both dev agents can receive PRPs

**Common Issues & Fixes**:
- PRP not in queue → Re-queue the PRP
- Dev shims not running → Restart pm shims
- Message delivery failed → Clear inflight queue

### 4. Evidence-Based Promotion
**Given** a PRP is in development  
**When** the dev agent sets required evidence  
**Then** the promote.lua script should move it to validation_queue

**Validates**:
- Evidence storage in Redis hash
- Lua script execution
- Atomic queue transitions
- Evidence validation logic
- Queue state consistency

**Common Issues & Fixes**:
- Lua script errors → Reload script
- Missing evidence → Set all required fields
- Queue state mismatch → Clear and rebuild queues

### 5. Timeout Recovery
**Given** a PRP is in an inflight queue  
**When** 30 minutes pass without activity  
**Then** the orchestrator loop should re-queue it

**Validates**:
- Inflight queue monitoring
- Timestamp tracking
- Timeout detection (30 min threshold)
- Re-queueing mechanism
- Orchestrator notification

**Common Issues & Fixes**:
- Orchestrator loop not running → Restart loop
- Timestamp format issues → Update last_activity field
- Queue operations failed → Check Redis connectivity

### 6. Shim Health Monitoring
**Given** the system is running  
**When** a shim process dies  
**Then** the orchestrator should be notified

**Validates**:
- Process monitoring
- Health check frequency
- Notification generation
- Orchestrator receives warning
- System resilience

**Common Issues & Fixes**:
- Monitoring not active → Restart orchestrator loop
- Notification not sent → Check queue connectivity
- Shim won't restart → Check process permissions

## Diagnostic Framework

### Failure Detection
Each test scenario returns a `TestResult` with:
- **status**: PENDING, RUNNING, PASSED, FAILED, FIXED
- **error**: Specific error message if failed
- **fix_applied**: Name of fix if applied
- **duration**: Test execution time

### Root Cause Analysis
The diagnostic system maps error patterns to specific fixes:

```python
diagnostics = {
    "System Startup": {
        "tmux" → "fix_tmux_session",
        "orchestrator_loop" → "fix_orchestrator_loop",
        "enterprise_shims" → "fix_enterprise_shims",
        "redis" → "fix_redis_connection"
    },
    "Orchestrator Receives Notifications": {
        "JSON handling" → "fix_json_message_handling",
        "shim crashed" → "fix_orchestrator_shim"
    },
    # ... etc
}
```

### Automated Fixes
The test suite includes 13 automated fix functions:
1. `fix_tmux_session` - Kill and restart tmux
2. `fix_orchestrator_loop` - Restart monitoring loop
3. `fix_enterprise_shims` - Restart all 5 shims
4. `fix_redis_connection` - Verify Redis connectivity
5. `fix_json_message_handling` - Update shim code
6. `fix_orchestrator_shim` - Restart orchestrator shim
7. `fix_prp_queueing` - Re-queue test PRP
8. `fix_dev_shims` - Restart dev shims
9. `fix_dev_message_delivery` - Clear blocked queues
10. `fix_lua_script` - Reload Lua scripts
11. `fix_evidence_validation` - Set required evidence
12. `fix_orchestrator_loop_timeout` - Fix timeout handling
13. `fix_shim_restart` - Restart failed shims

## Success Criteria

The test suite is considered successful when:
1. All 6 scenarios pass (possibly after fixes)
2. No manual intervention required
3. System remains stable after tests
4. All components are functioning correctly

## Running the Test Suite

```bash
# Ensure Redis is running
redis-cli ping

# Run the automated test suite
python3 tests/bdd_test_suite.py

# The suite will:
# 1. Start the system if not running
# 2. Execute all test scenarios
# 3. Diagnose and fix failures automatically
# 4. Retry failed tests (max 3 times)
# 5. Generate a summary report
```

## Expected Output

```
[10:45:23] ℹ️ Starting BDD Test Suite for Multi-Agent System
[10:45:23] ℹ️ Testing: System Startup
[10:45:35] ✅ System Startup - PASSED (12.34s)
[10:45:35] ℹ️ Testing: Orchestrator Receives Notifications
[10:45:41] ✅ Orchestrator Receives Notifications - PASSED (6.12s)
[10:45:41] ℹ️ Testing: PRP Assignment to Dev Agent
[10:45:47] ✅ PRP Assignment to Dev - PASSED (5.89s)
[10:45:47] ℹ️ Testing: Evidence-Based Promotion
[10:45:52] ✅ Evidence-Based Promotion - PASSED (4.56s)
[10:45:52] ℹ️ Testing: Timeout Recovery
[10:45:57] ✅ Timeout Recovery - PASSED (5.23s)
[10:45:57] ℹ️ Testing: Shim Health Monitoring
[10:46:03] ✅ Shim Health Monitoring - PASSED (6.78s)

============================================================
TEST SUMMARY
============================================================
Total Scenarios: 6
Passed: 6
Failed: 0
Fixed and Retried: 0
Total Fixes Applied: 0
🎉 ALL TESTS PASSED!
```

## Continuous Validation

After initial validation, the test suite can be run periodically to ensure:
- System remains functional after code changes
- All components integrate correctly
- Performance remains acceptable
- Error recovery mechanisms work

## Future Enhancements

1. **Performance Tests** - Measure queue throughput and latency
2. **Load Tests** - Handle multiple PRPs simultaneously
3. **Chaos Testing** - Random component failures
4. **Integration Tests** - Full PRP lifecycle from creation to deployment
5. **Security Tests** - Validate Redis access controls and agent isolation