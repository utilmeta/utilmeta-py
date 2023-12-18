local result = {}
for i, key in pairs(KEYS) do
    local values = redis.call('zrange', key, ARGV[2*i-1], ARGV[2*i])
    if (redis.call('zcount', key, -1, -1) > 0)
    then
        table.remove(values, 1)
    end
    result[i] = values
end
return result
