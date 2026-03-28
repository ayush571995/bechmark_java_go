"""
Locust gRPC stress test – Java (Redis) vs Go (MySQL).

Run via the Locust web UI at http://localhost:8089
Set host to http://java-service:50051  (ignored by gRPC users below, but required by Locust).

Each user class independently opens a long-lived gRPC channel.
Metrics are reported back to the Locust event system and appear in the UI.
"""

import random
import time

import grpc
import locust.stats
from locust import User, constant_pacing, events, task

import kv_pb2
import kv_pb2_grpc

# Pre-build the key pool once
KEYS = [f"key_{i:05d}" for i in range(10_000)]

# ─── helper ──────────────────────────────────────────────────────────────────

def _fire(name: str, start: float, exc: Exception | None, resp_len: int = 0):
    events.request.fire(
        request_type="gRPC",
        name=name,
        response_time=(time.perf_counter() - start) * 1000,
        response_length=resp_len,
        exception=exc,
    )


# ─── Java user ───────────────────────────────────────────────────────────────

class JavaGrpcUser(User):
    """Hits the Java gRPC service backed by Redis."""

    wait_time = constant_pacing(0)          # back-to-back requests

    def on_start(self):
        self.channel = grpc.insecure_channel("java-service:50051")
        self.stub = kv_pb2_grpc.KeyValueServiceStub(self.channel)

    def on_stop(self):
        self.channel.close()

    @task
    def get_key(self):
        key = random.choice(KEYS)
        start = time.perf_counter()
        exc = None
        resp_len = 0
        try:
            resp = self.stub.Get(kv_pb2.GetRequest(key=key))
            resp_len = len(resp.value)
        except grpc.RpcError as e:
            exc = e
        _fire("Java/Get", start, exc, resp_len)


# ─── Go user ─────────────────────────────────────────────────────────────────

class GoGrpcUser(User):
    """Hits the Go gRPC service backed by MySQL."""

    wait_time = constant_pacing(0)

    def on_start(self):
        self.channel = grpc.insecure_channel("go-service:50052")
        self.stub = kv_pb2_grpc.KeyValueServiceStub(self.channel)

    def on_stop(self):
        self.channel.close()

    @task
    def get_key(self):
        key = random.choice(KEYS)
        start = time.perf_counter()
        exc = None
        resp_len = 0
        try:
            resp = self.stub.Get(kv_pb2.GetRequest(key=key))
            resp_len = len(resp.value)
        except grpc.RpcError as e:
            exc = e
        _fire("Go/Get", start, exc, resp_len)
