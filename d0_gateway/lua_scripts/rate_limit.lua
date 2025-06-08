-- Redis Lua script for atomic rate limiting operations
-- Implements token bucket algorithm with daily and burst limits

-- Daily rate limit checker
-- KEYS[1]: daily rate limit key
-- ARGV[1]: daily limit
-- ARGV[2]: window in seconds (86400 for daily)
-- Returns: {current_count, limit, allowed_flag}
local function check_daily_limit(key, limit, window)
    local current = redis.call('GET', key)
    if current == false then
        current = 0
    else
        current = tonumber(current)
    end
    
    if current >= tonumber(limit) then
        return {current, tonumber(limit), 0}
    end
    
    local new_value = redis.call('INCR', key)
    if new_value == 1 then
        redis.call('EXPIRE', key, tonumber(window))
    end
    
    return {new_value, tonumber(limit), 1}
end

-- Burst rate limit checker using sliding window
-- KEYS[1]: burst rate limit key  
-- ARGV[1]: window in seconds
-- ARGV[2]: burst limit
-- ARGV[3]: current timestamp
-- Returns: {current_count, limit, allowed_flag}
local function check_burst_limit(key, window, limit, now)
    local window_seconds = tonumber(window)
    local burst_limit = tonumber(limit)
    local timestamp = tonumber(now)
    
    -- Remove expired entries from sliding window
    redis.call('ZREMRANGEBYSCORE', key, 0, timestamp - window_seconds)
    
    -- Count current requests in window
    local current = redis.call('ZCARD', key)
    
    if current >= burst_limit then
        return {current, burst_limit, 0}
    end
    
    -- Add current request to sliding window
    redis.call('ZADD', key, timestamp, timestamp)
    redis.call('EXPIRE', key, window_seconds + 1)
    
    return {current + 1, burst_limit, 1}
end

-- Combined rate limit check
-- KEYS[1]: daily key
-- KEYS[2]: burst key
-- ARGV[1]: daily limit
-- ARGV[2]: daily window (86400)
-- ARGV[3]: burst limit  
-- ARGV[4]: burst window
-- ARGV[5]: current timestamp
-- Returns: {daily_allowed, burst_allowed, daily_current, burst_current}
local function check_combined_limits(daily_key, burst_key, daily_limit, daily_window, burst_limit, burst_window, now)
    -- Check daily limit
    local daily_result = check_daily_limit(daily_key, daily_limit, daily_window)
    local daily_allowed = daily_result[3]
    
    -- Only check burst if daily is allowed
    if daily_allowed == 0 then
        return {0, 0, daily_result[1], 0}
    end
    
    -- Check burst limit
    local burst_result = check_burst_limit(burst_key, burst_window, burst_limit, now)
    local burst_allowed = burst_result[3]
    
    -- If burst is not allowed, decrement the daily counter we just incremented
    if burst_allowed == 0 then
        redis.call('DECR', daily_key)
        return {1, 0, daily_result[1] - 1, burst_result[1]}
    end
    
    return {1, 1, daily_result[1], burst_result[1]}
end

-- Token bucket refill operation
-- KEYS[1]: bucket key
-- ARGV[1]: bucket capacity
-- ARGV[2]: refill rate (tokens per second)
-- ARGV[3]: current timestamp
-- Returns: {current_tokens, capacity, last_refill}
local function refill_bucket(key, capacity, refill_rate, now)
    local bucket_capacity = tonumber(capacity)
    local rate = tonumber(refill_rate)
    local timestamp = tonumber(now)
    
    -- Get current bucket state
    local bucket_data = redis.call('HMGET', key, 'tokens', 'last_refill')
    local current_tokens = tonumber(bucket_data[1]) or bucket_capacity
    local last_refill = tonumber(bucket_data[2]) or timestamp
    
    -- Calculate tokens to add based on time elapsed
    local time_elapsed = timestamp - last_refill
    local tokens_to_add = math.floor(time_elapsed * rate)
    
    -- Update token count (cannot exceed capacity)
    local new_tokens = math.min(current_tokens + tokens_to_add, bucket_capacity)
    
    -- Update bucket state
    redis.call('HMSET', key, 'tokens', new_tokens, 'last_refill', timestamp)
    redis.call('EXPIRE', key, 3600) -- Expire after 1 hour of inactivity
    
    return {new_tokens, bucket_capacity, timestamp}
end

-- Token bucket consumption
-- KEYS[1]: bucket key
-- ARGV[1]: bucket capacity
-- ARGV[2]: refill rate
-- ARGV[3]: tokens to consume
-- ARGV[4]: current timestamp
-- Returns: {allowed, remaining_tokens, capacity}
local function consume_tokens(key, capacity, refill_rate, tokens_needed, now)
    local tokens_to_consume = tonumber(tokens_needed) or 1
    
    -- First refill the bucket
    local refill_result = refill_bucket(key, capacity, refill_rate, now)
    local available_tokens = refill_result[1]
    
    -- Check if we have enough tokens
    if available_tokens < tokens_to_consume then
        return {0, available_tokens, tonumber(capacity)}
    end
    
    -- Consume tokens
    local remaining_tokens = available_tokens - tokens_to_consume
    redis.call('HSET', key, 'tokens', remaining_tokens)
    
    return {1, remaining_tokens, tonumber(capacity)}
end

-- Main entry point - determine which function to call based on command
local command = ARGV[1]

if command == "check_daily" then
    return check_daily_limit(KEYS[1], ARGV[2], ARGV[3])
elseif command == "check_burst" then
    return check_burst_limit(KEYS[1], ARGV[2], ARGV[3], ARGV[4])
elseif command == "check_combined" then
    return check_combined_limits(KEYS[1], KEYS[2], ARGV[2], ARGV[3], ARGV[4], ARGV[5], ARGV[6])
elseif command == "refill_bucket" then
    return refill_bucket(KEYS[1], ARGV[2], ARGV[3], ARGV[4])
elseif command == "consume_tokens" then
    return consume_tokens(KEYS[1], ARGV[2], ARGV[3], ARGV[4], ARGV[5])
else
    error("Unknown command: " .. tostring(command))
end