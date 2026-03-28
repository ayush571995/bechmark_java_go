"""
Stress test – Java gRPC service (G1GC, 8 cores, 20 GB).

Load shape
──────────
Automatically steps up users every 90 seconds to find the QPS breaking point.
Each step is visible as a distinct band in Grafana.

  Step 1 :   50 users  → warmup
  Step 2 :  100 users  → ~1 000 RPS
  Step 3 :  200 users  → ~2 000 RPS
  Step 4 :  300 users  → ~3 000 RPS
  Step 5 :  400 users  → ~4 000 RPS  ← likely breaking point
  Step 6 :  600 users  → pushing past
  Step 7 :  800 users  → extreme pressure
  Step 8 : 1000 users  → ceiling

Hit / miss ratio
────────────────
  80 % → keys that exist   (key_00000 … key_09999)  → real ~50-byte JSON response
  20 % → keys that NEVER exist (miss_00000 … miss_01999) → {} from server

Open http://localhost:8089 to watch live.
Grafana http://localhost:3000 shows GC pauses, heap, latency, RPS.
"""

import random
import time

import grpc
from locust import LoadTestShape, User, constant_pacing, events, task

import kv_pb2
import kv_pb2_grpc

# ── Key pools ─────────────────────────────────────────────────────────────────

HIT_KEYS  = [f"key_{i:05d}"  for i in range(10_000)]   # exist in Redis
MISS_KEYS = [f"miss_{i:05d}" for i in range(2_000)]    # never seeded → cache miss


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fire(name: str, start: float, exc=None, resp_len: int = 0):
    events.request.fire(
        request_type="gRPC",
        name=name,
        response_time=(time.perf_counter() - start) * 1000,
        response_length=resp_len,
        exception=exc,
    )


# ── User ──────────────────────────────────────────────────────────────────────

class JavaGrpcUser(User):
    """Back-to-back gRPC GETs; key chosen 80 % hit / 20 % miss."""

    wait_time = constant_pacing(0)   # fire as fast as the server allows

    def on_start(self):
        self.channel = grpc.insecure_channel(
            "java-service:50051",
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
        # 80 % hit, 20 % miss
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
        _fire("Java/Get", start, exc, resp_len)


# ── Step-up load shape ────────────────────────────────────────────────────────

class BreakingPointShape(LoadTestShape):
    """
    Automatically ramps users in steps to find the QPS ceiling.
    Each row: (target_users, spawn_rate, duration_seconds)
    """

    steps = [
        (50,   50,  60),    # warmup
        (100,  50,  90),    # ~1 000 RPS
        (200, 100,  90),    # ~2 000 RPS
        (300, 100,  90),    # ~3 000 RPS
        (400, 100,  90),    # ~4 000 RPS  ← watch for GC + latency spike
        (600, 200,  90),    # push past
        (800, 200,  90),    # heavy
        (1000, 200, 90),    # ceiling
    ]

    def tick(self):
        run_time = self.get_run_time()
        elapsed = 0
        for users, spawn_rate, duration in self.steps:
            elapsed += duration
            if run_time < elapsed:
                return (users, spawn_rate)
        return None   # all steps done → stop test
