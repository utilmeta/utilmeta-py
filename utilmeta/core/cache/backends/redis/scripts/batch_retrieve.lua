local result = {}
for i, key in pairs(KEYS) do
    result[i] = redis.call('hmget', key, unpack(ARGV))
end
return result