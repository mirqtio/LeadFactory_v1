-- Redis Lua script for atomic PRP queue promotion with evidence validation
-- Implements atomic queue promotion operations for PRP state transitions

-- Evidence schema validation function
-- Validates evidence structure based on transition type
local function validate_evidence(evidence_json, transition_type)
    if not evidence_json or evidence_json == "" then
        error("Evidence required for PRP promotion")
    end
    
    -- Parse evidence JSON
    local evidence = cjson.decode(evidence_json)
    
    -- Common required fields for all transitions
    if not evidence.timestamp then
        error("Evidence must include timestamp")
    end
    
    if not evidence.agent_id then
        error("Evidence must include agent_id")  
    end
    
    if not evidence.transition_type or evidence.transition_type ~= transition_type then
        error("Evidence transition_type must match: " .. transition_type)
    end
    
    -- Transition-specific validation
    if transition_type == "pending_to_development" then
        if not evidence.requirements_analysis then
            error("Development requires requirements_analysis in evidence")
        end
        if not evidence.acceptance_criteria then
            error("Development requires acceptance_criteria in evidence")
        end
    elseif transition_type == "development_to_integration" then
        if not evidence.implementation_complete then
            error("Integration requires implementation_complete=true in evidence")
        end
        if not evidence.local_validation then
            error("Integration requires local_validation result in evidence")
        end
        if not evidence.branch_name then
            error("Integration requires branch_name in evidence")
        end
    elseif transition_type == "integration_to_validate" then
        if not evidence.smoke_ci_passed then
            error("Validation requires smoke_ci_passed=true in evidence") 
        end
        if not evidence.merge_commit then
            error("Validation requires merge_commit hash in evidence")
        end
    elseif transition_type == "validate_to_complete" then
        if not evidence.quality_gates_passed then
            error("Completion requires quality_gates_passed=true in evidence")
        end
        if not evidence.validator_approval then
            error("Completion requires validator_approval in evidence")
        end
    else
        error("Unknown transition type: " .. transition_type)
    end
    
    return true
end

-- Atomic queue promotion function  
-- KEYS[1]: source queue key
-- KEYS[2]: destination queue key
-- KEYS[3]: PRP metadata key (hash)
-- ARGV[1]: PRP ID
-- ARGV[2]: evidence JSON
-- ARGV[3]: transition type
-- ARGV[4]: current timestamp
-- Returns: {success, new_state, evidence_key}
local function promote_prp(source_queue, dest_queue, metadata_key, prp_id, evidence_json, transition_type, timestamp)
    -- Validate evidence first (will error if invalid)
    validate_evidence(evidence_json, transition_type)
    
    -- Check if PRP exists in source queue
    local prp_in_source = redis.call('LREM', source_queue, 1, prp_id)
    if prp_in_source == 0 then
        error("PRP " .. prp_id .. " not found in source queue: " .. source_queue)
    end
    
    -- Atomic promotion: add to destination queue
    redis.call('LPUSH', dest_queue, prp_id)
    
    -- Update PRP metadata atomically
    local new_state = string.match(dest_queue, "queue:(%w+)$") or "unknown"
    redis.call('HSET', metadata_key, 
        'status', new_state,
        'last_transition', timestamp,
        'last_transition_type', transition_type
    )
    
    -- Store evidence with unique key
    local evidence_key = 'evidence:' .. prp_id .. ':' .. timestamp
    redis.call('HSET', evidence_key, 
        'prp_id', prp_id,
        'transition_type', transition_type,
        'evidence_data', evidence_json,
        'created_at', timestamp
    )
    
    -- Set evidence expiry (30 days for audit trail)
    redis.call('EXPIRE', evidence_key, 2592000)
    
    return {1, new_state, evidence_key}
end

-- Batch promotion function for multiple PRPs
-- KEYS[1]: source queue key
-- KEYS[2]: destination queue key  
-- ARGV[1]: transition type
-- ARGV[2]: current timestamp
-- ARGV[3]: batch evidence JSON (array)
-- ARGV[4+]: PRP IDs to promote
-- Returns: {promoted_count, failed_prps}
local function batch_promote(source_queue, dest_queue, transition_type, timestamp, batch_evidence_json, ...)
    local prp_ids = {...}
    local batch_evidence = cjson.decode(batch_evidence_json)
    
    local promoted = 0
    local failed = {}
    
    for i, prp_id in ipairs(prp_ids) do
        -- Get evidence for this PRP
        local evidence = batch_evidence[i] or batch_evidence[1] -- Fallback to first evidence
        local evidence_json = cjson.encode(evidence)
        
        -- Attempt promotion
        local success, err = pcall(function()
            local metadata_key = 'prp:' .. prp_id .. ':metadata'
            return promote_prp(source_queue, dest_queue, metadata_key, prp_id, evidence_json, transition_type, timestamp)
        end)
        
        if success then
            promoted = promoted + 1
        else
            table.insert(failed, {prp_id, tostring(err)})
        end
    end
    
    return {promoted, failed}
end

-- Queue status check function
-- KEYS[1]: PRP metadata key
-- Returns: {status, last_transition, queue_position}
local function get_prp_status(metadata_key, prp_id)
    local metadata = redis.call('HMGET', metadata_key, 'status', 'last_transition', 'last_transition_type')
    local status = metadata[1] or 'unknown'
    local last_transition = metadata[2] or 'never'
    local transition_type = metadata[3] or 'none'
    
    -- Find queue position
    local queue_key = 'queue:' .. status
    local position = redis.call('LPOS', queue_key, prp_id)
    if position == false then
        position = -1 -- Not in expected queue
    end
    
    return {status, last_transition, transition_type, position}
end

-- Evidence retrieval function
-- KEYS[1]: evidence key pattern
-- ARGV[1]: PRP ID
-- ARGV[2]: limit (optional, default 10)
-- Returns: evidence entries (newest first)
local function get_evidence_history(prp_id, limit)
    limit = tonumber(limit) or 10
    
    -- Find evidence keys for this PRP
    local pattern = 'evidence:' .. prp_id .. ':*'
    local evidence_keys = redis.call('KEYS', pattern)
    
    -- Sort by timestamp (newest first)
    table.sort(evidence_keys, function(a, b)
        local ts_a = string.match(a, ':(%d+)$')
        local ts_b = string.match(b, ':(%d+)$')
        return tonumber(ts_a) > tonumber(ts_b)
    end)
    
    -- Retrieve evidence (limited)
    local evidence_list = {}
    for i = 1, math.min(limit, #evidence_keys) do
        local evidence = redis.call('HMGET', evidence_keys[i], 'transition_type', 'evidence_data', 'created_at')
        table.insert(evidence_list, {
            key = evidence_keys[i],
            transition_type = evidence[1],
            evidence_data = evidence[2], 
            created_at = evidence[3]
        })
    end
    
    return evidence_list
end

-- Main entry point - determine which function to call
local command = ARGV[1]

if command == "promote" then
    -- Single PRP promotion
    return promote_prp(KEYS[1], KEYS[2], KEYS[3], ARGV[2], ARGV[3], ARGV[4], ARGV[5])
elseif command == "batch_promote" then
    -- Batch PRP promotion
    return batch_promote(KEYS[1], KEYS[2], ARGV[2], ARGV[3], ARGV[4], unpack(ARGV, 5))
elseif command == "status" then
    -- Get PRP status
    return get_prp_status(KEYS[1], ARGV[2])
elseif command == "evidence" then
    -- Get evidence history
    return get_evidence_history(ARGV[2], ARGV[3])
else
    error("Unknown command: " .. tostring(command))
end