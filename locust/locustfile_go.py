"""
Stress test – Go gRPC service (Redis backend).

Identical load shape to locustfile_java.py for a fair apples-to-apples comparison.

  Step 1 :   50 users  → warmup
  Step 2 :  100 users  → ~1 000 RPS
  Step 3 :  200 users  → ~2 000 RPS
  Step 4 :  300 users  → ~3 000 RPS
  Step 5 :  400 users  → ~4 000 RPS
  Step 6 :  600 users  → pushing past
  Step 7 :  800 users  → heavy
  Step 8 : 1000 users  → ceiling

Hit / miss ratio
────────────────
  80 % → keys that exist   (key_00000 … key_09999)  → real ~50-byte JSON
  20 % → keys that never exist (miss_00000 … miss_01999) → {} from server
"""

import random
import time

import grpc
from locust import LoadTestShape, User, constant_pacing, events, task

import kv_pb2
import kv_pb2_grpc

# ── Key pools ─────────────────────────────────────────────────────────────────

HIT_KEYS  = [f"key_{i:05d}"  for i in range(10_000)]
MISS_KEYS = [f"miss_{i:05d}" for i in range(2_000)]


# ── Helper ────────────────────────────────────────────────────────────────────

def _fire(name: str, start: float, exc=None, resp_len: int = 0):
    events.request.fire(
        request_type="gRPC",
        name=name,
        response_time=(time.perf_counter() - start) * 1000,
        response_length=resp_len,
        exception=exc,
    )


# ── User ──────────────────────────────────────────────────────────────────────

class GoGrpcUser(User):
    """Back-to-back gRPC GETs; key chosen 80 % hit / 20 % miss."""

    wait_time = constant_pacing(0)

    def on_start(self):
        self.channel = grpc.insecure_channel(
            "go-service:50052",
            options=[
                ("grpc.max_send_message_length",    1 * 1024 * 1024),
                ("grpc.max_receive_message_length", 1 * 1024 * 1024),
            ],
        )
        self.stub = kv_pb2_grpc.KeyValueServiceStub(self.channel)

    def on_stop(self):
        self.channel.close()

    @task
    def get_key(self):
        key = (
            random.choice(HIT_KEYS)
            if random.random() < 0.8
            else random.choice(MISS_KEYS)
        )
        start = time.perf_counter()
        exc = None
        resp_len = 0
        try:
            resp = self.stub.Get(kv_pb2.GetRequest(key=key))
            resp_len = len(resp.value)
        except grpc.RpcError as e:
            exc = e
        _fire("Go/Get", start, exc, resp_len)


# ── Step-up load shape (identical to Java test) ───────────────────────────────

class BreakingPointShape(LoadTestShape):
    """
    Ramps users in steps to find the QPS ceiling.
    Each row: (target_users, spawn_rate, duration_seconds)
    """

    steps = [
        (50,   50,  60),
        (100,  50,  90),
        (200, 100,  90),
        (300, 100,  90),
        (400, 100,  90),
        (600, 200,  90),
        (800, 200,  90),
        (1000, 200, 90),
    ]

    def tick(self):
        run_time = self.get_run_time()
        elapsed = 0
        for users, spawn_rate, duration in self.steps:
            elapsed += duration
            if run_time < elapsed:
                return (users, spawn_rate)
        return None
