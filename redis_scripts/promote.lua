-- Redis Lua script for atomic PRP queue promotion with evidence validation
-- Implements atomic check-and-set operations for reliable queue promotion
-- Performance target: ≤50µs per call @ 1K RPS

-- Evidence validation helper
-- KEYS[1]: evidence hash key (prp:{id})
-- ARGV[1]: required fields JSON array
-- ARGV[2]: validation mode (strict|permissive)
-- Returns: {valid, missing_fields}
local function validate_evidence(evidence_key, required_fields_json, validation_mode)
    local required_fields = cjson.decode(required_fields_json)
    local missing_fields = {}
    
    -- Get all evidence fields
    local evidence_data = redis.call('HGETALL', evidence_key)
    local evidence = {}
    
    -- Convert array to hash table for lookup
    for i = 1, #evidence_data, 2 do
        local key = evidence_data[i]
        local value = evidence_data[i + 1]
        evidence[key] = value
    end
    
    -- Check required fields
    for i = 1, #required_fields do
        local field = required_fields[i]
        local value = evidence[field]
        
        if not value or value == "" then
            table.insert(missing_fields, field)
        elseif value == "false" or value == "0" then
            -- Boolean false or zero considered invalid
            if validation_mode == "strict" then
                table.insert(missing_fields, field)
            end
        end
    end
    
    local is_valid = #missing_fields == 0
    return {is_valid and 1 or 0, cjson.encode(missing_fields)}
end

-- Queue promotion with atomic BRPOPLPUSH pattern
-- KEYS[1]: source queue key
-- KEYS[2]: destination queue key
-- KEYS[3]: evidence hash key
-- ARGV[1]: required fields JSON array
-- ARGV[2]: validation mode
-- ARGV[3]: prp_id for logging
-- Returns: {success, error_message, evidence_status}
local function promote_prp(source_queue, dest_queue, evidence_key, required_fields, validation_mode, prp_id)
    -- First validate evidence before attempting promotion
    local validation_result = validate_evidence(evidence_key, required_fields, validation_mode)
    local evidence_valid = validation_result[1]
    local missing_fields = validation_result[2]
    
    if evidence_valid == 0 then
        return {0, "evidence_validation_failed", missing_fields}
    end
    
    -- Check if PRP exists in source queue
    local queue_length = redis.call('LLEN', source_queue)
    if queue_length == 0 then
        return {0, "source_queue_empty", "{}"}
    end
    
    -- Find and remove PRP from source queue (atomic search and remove)
    local queue_items = redis.call('LRANGE', source_queue, 0, -1)
    local prp_found = false
    local prp_data = nil
    
    for i = 1, #queue_items do
        local item = queue_items[i]
        local item_data = cjson.decode(item)
        
        if item_data.id == prp_id then
            prp_found = true
            prp_data = item
            -- Remove this specific item (atomic)
            redis.call('LREM', source_queue, 1, item)
            break
        end
    end
    
    if not prp_found then
        return {0, "prp_not_found_in_source", "{}"}
    end
    
    -- Add to destination queue (atomic)
    local new_length = redis.call('LPUSH', dest_queue, prp_data)
    
    -- Update promotion timestamp in evidence
    local timestamp = redis.call('TIME')
    local promotion_time = timestamp[1] .. "." .. string.format("%06d", timestamp[2])
    redis.call('HSET', evidence_key, 'promoted_at', promotion_time)
    redis.call('HSET', evidence_key, 'promoted_to', dest_queue)
    
    -- Success - return new destination queue length
    return {1, "promotion_successful", tostring(new_length)}
end

-- Bulk promotion for multiple PRPs (batch operation)
-- KEYS[1]: source queue key
-- KEYS[2]: destination queue key  
-- ARGV[1]: prp_ids JSON array
-- ARGV[2]: required fields JSON array
-- ARGV[3]: validation mode
-- Returns: {total_processed, successful_count, failed_ids_json}
local function bulk_promote_prps(source_queue, dest_queue, prp_ids_json, required_fields, validation_mode)
    local prp_ids = cjson.decode(prp_ids_json)
    local successful_count = 0
    local failed_ids = {}
    
    for i = 1, #prp_ids do
        local prp_id = prp_ids[i]
        local evidence_key = "prp:" .. prp_id
        
        local result = promote_prp(source_queue, dest_queue, evidence_key, required_fields, validation_mode, prp_id)
        
        if result[1] == 1 then
            successful_count = successful_count + 1
        else
            table.insert(failed_ids, {id = prp_id, error = result[2]})
        end
    end
    
    return {#prp_ids, successful_count, cjson.encode(failed_ids)}
end

-- Queue state check - verify PRP location
-- KEYS[1]: queue key to check
-- ARGV[1]: prp_id
-- Returns: {found, position}
local function check_prp_in_queue(queue_key, prp_id)
    local queue_items = redis.call('LRANGE', queue_key, 0, -1)
    
    for i = 1, #queue_items do
        local item = queue_items[i]
        local item_data = cjson.decode(item)
        
        if item_data.id == prp_id then
            return {1, i - 1} -- Return 0-based position
        end
    end
    
    return {0, -1}
end

-- Evidence integrity check
-- KEYS[1]: evidence hash key
-- ARGV[1]: expected checksum (optional)
-- Returns: {valid, current_checksum}
local function verify_evidence_integrity(evidence_key, expected_checksum)
    local evidence_data = redis.call('HGETALL', evidence_key)
    
    if #evidence_data == 0 then
        return {0, "evidence_not_found"}
    end
    
    -- Calculate simple checksum of evidence data
    local checksum_data = table.concat(evidence_data, "|")
    local checksum = redis.sha1hex(checksum_data)
    
    if expected_checksum and expected_checksum ~= "" then
        local valid = (checksum == expected_checksum) and 1 or 0
        return {valid, checksum}
    end
    
    return {1, checksum}
end

-- Unified promotion interface for integration tests
-- KEYS[1]: source queue
-- KEYS[2]: destination queue  
-- KEYS[3]: PRP metadata key
-- ARGV[1]: command ("promote")
-- ARGV[2]: PRP ID
-- ARGV[3]: evidence JSON
-- ARGV[4]: transition type
-- ARGV[5]: timestamp
-- Returns: {success, new_state, evidence_key}
local function promote(source_queue, dest_queue, metadata_key, prp_id, evidence_json, transition_type, timestamp)
    -- Parse evidence data
    local evidence_data = cjson.decode(evidence_json)
    
    -- Validate evidence has required fields for this transition
    local required_fields = {
        "timestamp", "agent_id", "transition_type", 
        "requirements_analysis", "acceptance_criteria"
    }
    
    for i = 1, #required_fields do
        local field = required_fields[i]
        if not evidence_data[field] or evidence_data[field] == "" then
            error("Evidence validation failed: missing required field '" .. field .. "'")
        end
    end
    
    -- Validate transition type matches
    if evidence_data.transition_type ~= transition_type then
        error("Evidence transition_type must match promotion transition_type")
    end
    
    -- Atomic promotion: remove from source, add to destination
    local removed_count = redis.call('LREM', source_queue, 1, prp_id)
    if removed_count == 0 then
        error("PRP " .. prp_id .. " not found in queue " .. source_queue)
    end
    redis.call('LPUSH', dest_queue, prp_id)
    
    -- Determine new state from destination queue
    local new_state = string.match(dest_queue, "queue:(.+)$") or "unknown"
    
    -- Store metadata
    redis.call('HSET', metadata_key, 
        'current_state', new_state,
        'transition_type', transition_type,
        'last_transition', timestamp
    )
    
    -- Store evidence for history
    local evidence_key = "evidence:" .. prp_id .. ":" .. timestamp
    redis.call('HSET', evidence_key,
        'transition_type', transition_type,
        'evidence_data', evidence_json,
        'timestamp', timestamp
    )
    
    return {1, new_state, evidence_key}
end

-- Main entry point - determine which function to call based on command
local command = ARGV[1]

if command == "validate_evidence" then
    return validate_evidence(KEYS[1], ARGV[2], ARGV[3])
elseif command == "promote_prp" then
    return promote_prp(KEYS[1], KEYS[2], KEYS[3], ARGV[2], ARGV[3], ARGV[4])
elseif command == "promote" then
    return promote(KEYS[1], KEYS[2], KEYS[3], ARGV[2], ARGV[3], ARGV[4], ARGV[5])
elseif command == "bulk_promote" then
    return bulk_promote_prps(KEYS[1], KEYS[2], ARGV[2], ARGV[3], ARGV[4])
elseif command == "check_prp_in_queue" then
    return check_prp_in_queue(KEYS[1], ARGV[2])
elseif command == "verify_evidence_integrity" then
    return verify_evidence_integrity(KEYS[1], ARGV[2])
else
    error("Unknown command: " .. tostring(command))
end