-- promote.lua: Atomic PRP promotion script
-- Ensures exactly-once promotion with all required evidence keys

local from_queue = KEYS[1]  -- e.g., "dev_queue:inflight"
local to_queue = KEYS[2]    -- e.g., "validation_queue"
local prp_key = KEYS[3]     -- e.g., "prp:P0-001"
local prp_id = ARGV[1]      -- e.g., "P0-001"

-- Required evidence keys based on the stage
local required_keys = {}

if string.find(from_queue, "dev_queue") then
    -- Moving from dev to validation
    required_keys = {
        "development_complete",
        "lint_clean",
        "tests_passed",
        "coverage_pct"
    }
elseif string.find(from_queue, "validation_queue") then
    -- Moving from validation to integration
    required_keys = {
        "validation_complete",
        "all_tests_pass",
        "coverage_acceptable"
    }
elseif string.find(from_queue, "integration_queue") then
    -- Moving from integration to done
    required_keys = {
        "deploy_ok",
        "integration_complete"
    }
end

-- Check if PRP exists
if redis.call("EXISTS", prp_key) == 0 then
    return "PRP_NOT_FOUND"
end

-- Check if PRP is in the inflight queue
local in_queue = false
local queue_items = redis.call("LRANGE", from_queue, 0, -1)
for i, item in ipairs(queue_items) do
    if item == prp_id then
        in_queue = true
        break
    end
end

if not in_queue then
    return "NOT_IN_QUEUE"
end

-- Verify all required evidence keys exist
for _, key in ipairs(required_keys) do
    local value = redis.call("HGET", prp_key, key)
    if not value or value == "" or value == "false" then
        return "PROMOTE_FAILED"
    end
end

-- Atomic promotion: remove from inflight and push to next queue
redis.call("LREM", from_queue, 0, prp_id)
redis.call("LPUSH", to_queue, prp_id)

-- Update PRP status
local new_status = "unknown"
if string.find(to_queue, "validation_queue") then
    new_status = "validation"
elseif string.find(to_queue, "integration_queue") then
    new_status = "integration"
elseif string.find(to_queue, "done") then
    new_status = "complete"
end

redis.call("HSET", prp_key, "status", new_status)
redis.call("HSET", prp_key, "promoted_at", tostring(redis.call("TIME")[1]))

return "PROMOTED"