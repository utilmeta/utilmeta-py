local exec = false
local key = KEYS[1]
local amount = tonumber(ARGV[1])
local value = redis.call('get', key)
local miss = value == false --- not nil
if miss then
    value = 0
else
    value = tonumber(value)
    if value == nil then --- cannot convert to number
        return nil
    end
end
if not amount then
    return nil
end
local pos = amount > 0
if (#ARGV == 2) then
    local limit = tonumber(ARGV[2]) - amount
    if pos then
        exec = value <= limit
    else
        exec = value >= limit
    end
else
    exec = true
end
local cmd = 'incrbyfloat'
if amount % 1 == 0 then
    if pos then
        cmd = 'incrby'
    else
        cmd = 'decrby'
        amount = -amount
    end
end
if exec then
    return redis.call(cmd, key, amount)
end
return nil