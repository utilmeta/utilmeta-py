local result = redis.call('lrange', KEYS[1], 0, -1)
redis.call('delete', KEYS[1])
return result