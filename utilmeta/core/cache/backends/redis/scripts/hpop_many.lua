local result = redis.call('hmget', KEYS[1], unpack(ARGV))
redis.call('hdel', KEYS[1], unpack(ARGV))
return result
