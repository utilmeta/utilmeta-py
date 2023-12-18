local result = {}
for i, key in pairs(KEYS) do
    local count = redis.call('zcard', key)
    if (redis.call('zcount', key, -1, -1) > 0)
    then
        count = count - 1
    end
    result[i] = count
end
return result