local result = {}
local i = 1
for j, key in pairs(KEYS) do
    if (redis.call('exists', key) == 0)
    then
        result[i] = key
        i = i + 1
    else
        if (ARGV[1] > '0')
        then
            redis.call('expire', key, ARGV[1])
        end
    end
end
return result