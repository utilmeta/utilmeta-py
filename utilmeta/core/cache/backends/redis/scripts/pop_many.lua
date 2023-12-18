local result = redis.call('mget', unpack(KEYS))
redis.call('delete', unpack(KEYS))
return result
