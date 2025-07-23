-- Atomic promotion script for Redis
-- KEYS[1] = inflight queue key (e.g., "dev_queue:inflight")
-- KEYS[2] = PRP hash key (e.g., "prp:P3-003")
-- ARGV[1] = next queue name (e.g., "validation_queue")
-- ARGV[2] = current stage name (e.g., "dev")

local inflight_key = KEYS[1]
local prp_key = KEYS[2]
local next_queue = ARGV[1]
local stage = ARGV[2]

-- Get PRP data
local prp_data = redis.call("HGETALL", prp_key)
local prp_map = {}
for i = 1, #prp_data, 2 do
    prp_map[prp_data[i]] = prp_data[i + 1]
end

-- Check if stage is already completed
local completed_key = stage .. "_completed_at"
if not prp_map[completed_key] then
    return {err = "Stage not marked as completed"}
end

-- Get evidence requirements for this stage
local schema_key = "cfg:evidence_schema:" .. stage
local required_keys = redis.call("SMEMBERS", schema_key)

-- Validate all required evidence exists
for i, key in ipairs(required_keys) do
    if not prp_map[key] then
        return {err = "Missing required evidence: " .. key}
    end
end

-- Special validations based on stage
if stage == "dev" or stage == "pm" then
    local coverage = tonumber(prp_map["coverage_pct"] or "0")
    if coverage < 80 then
        return {err = "Coverage below 80%: " .. coverage}
    end
end

if stage == "validation" or stage == "validator" then
    if prp_map["validation_passed"] ~= "true" then
        -- Failed validation goes back to dev queue
        local prp_id = prp_map["id"]
        redis.call("LREM", inflight_key, 0, prp_id)
        redis.call("LPUSH", "dev_queue", prp_id)
        redis.call("HINCRBY", prp_key, "validation_attempts", 1)
        return {ok = "sent_back_to_dev"}
    end
end

-- All validations passed - promote to next queue
local prp_id = prp_map["id"]
redis.call("LREM", inflight_key, 0, prp_id)

if next_queue ~= "complete" then
    redis.call("LPUSH", next_queue, prp_id)
else
    -- Final stage - mark as complete
    redis.call("HSET", prp_key, "state", "complete")
    redis.call("HSET", prp_key, "completed_at", redis.call("TIME")[1])
end

return {ok = "promoted", next = next_queue}