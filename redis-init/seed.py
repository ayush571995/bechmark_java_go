"""Seed 10 000 key-value pairs into Redis on startup."""

import os
import redis
import sys

host = os.environ.get("REDIS_HOST", "redis")
r = redis.Redis(host=host, port=6379, decode_responses=True)
print(f"Seeding 10 000 keys into Redis at {host}:6379…")

pipe = r.pipeline(transaction=False)
for i in range(10_000):
    key = f"key_{i:05d}"
    val = f'{{"id":{i},"name":"item_{i:05d}","val":{i * 2}}}'
    pipe.set(key, val)
    if i % 500 == 499:
        pipe.execute()

pipe.execute()
total = r.dbsize()
print(f"Done. Total keys in Redis: {total}")
sys.exit(0 if total >= 10_000 else 1)
