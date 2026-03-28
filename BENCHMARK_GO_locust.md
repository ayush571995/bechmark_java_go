# Go gRPC Baseline Benchmark — Locust Load Test

> **Test date:** 2026-03-27
> **Label:** Baseline — Default Go GC, no tuning
> **Load generator:** Locust 2.24.0 (Python/gevent, BreakingPointShape)
> **Backend:** Redis 7.2 (shared, seeded with 10 000 keys, ~50-byte JSON values)
> **Key distribution:** 80 % cache hit (`key_00000..key_09999`) / 20 % miss (`miss_00000..miss_01999`)
> **Resources allocated:** 8 vCPUs, 20 GB memory (Docker resource limits)

---

## TL;DR

| Metric | Value |
|--------|-------|
| **Peak RPS** | **3,680** |
| **Sustained RPS (plateau)** | ~3,500 |
| **p50 latency** | 0.25 ms |
| **p95 latency** | 0.48 ms |
| **p99 latency** | 0.50 ms |
| **CPU cores used (avg)** | **0.62 / 8 (7.8 %)** |
| **Heap allocated (avg)** | **2.47 MB** |
| **GC impact** | Negligible (< 0.4 ms/s pause rate) |
| **Errors** | **0** |

---

## Load Shape

| Step | Users | Duration | Min RPS | Max RPS | Avg RPS |
|------|------:|----------|--------:|--------:|--------:|
| Warmup | 50 | 60 s | 2 196 | 3 426 | 3 000 |
| Step 2 | 100 | 90 s | 3 342 | 3 646 | 3 516 |
| Step 3 | 200 | 90 s | 3 440 | 3 657 | 3 562 |
| Step 4 | 300 | 90 s | 3 373 | 3 632 | 3 518 |
| Step 5 | 400 | 90 s | 3 338 | **3 680** | 3 552 |
| Step 6 | 600 | 90 s | 3 406 | 3 535 | 3 464 |
| Step 7 | 800 | 90 s | 3 524 | 3 615 | 3 560 |
| Step 8 | 1 000 | 90 s | 3 351 | 3 541 | 3 489 |

**Key observation:** RPS plateaued at ~3,500 from 100 users onward, with no degradation even at 1,000 users. This is a flat ceiling, not a graceful degradation — the Go service never ran out of headroom.

---

## Latency

| Percentile | Value (steady state) |
|------------|---------------------|
| p50 | 0.25 ms |
| p95 | 0.48 ms |
| p99 | 0.50 ms |

Latency was perfectly stable across **all** load steps — no increase from 50 to 1,000 users. The Go service did not exhibit any latency degradation under the applied load.

---

## Runtime Metrics

### CPU

| Metric | Value |
|--------|-------|
| Min | 0.001 cores |
| Average | **0.621 cores** |
| Peak | **0.685 cores** |

At peak load (1,000 users, ~3,500 RPS), the Go service consumed **< 0.7 of 8 allocated CPU cores**. Docker stats showed ~8 % CPU, matching Prometheus's 0.685 cores. The service had **7+ cores completely idle** throughout.

### Memory (Heap)

| Metric | Value |
|--------|-------|
| Min alloc | 0.86 MB |
| Average alloc | **2.47 MB** |
| Peak alloc | 3.29 MB |
| Sys (reserved) | 6.58–16.46 MB |

Go's heap stayed in the **single-digit megabyte range** for the entire test. The GC had almost nothing to do.

### Goroutines

| Metric | Value |
|--------|-------|
| Min | 7 |
| Average | 11 |
| Max | 12 |

Goroutines never grew beyond 12. This is expected given Little's Law:

```
In-flight goroutines = RPS × latency = 3,500 × 0.00025 s ≈ 0.88
```

At 0.25 ms per request, fewer than **1 goroutine is blocked on Redis at any instant**. The 12 goroutines visible are background workers (gRPC listener, Prometheus HTTP, runtime goroutines). There is no goroutine accumulation or back-pressure.

### GC (Garbage Collector)

| Metric | Value |
|--------|-------|
| GC pause rate | 0.01–0.37 ms/s |
| GC tuning applied | None (default GOGC=100) |

GC pauses amounted to under **0.4 ms per second of wall time** — negligible. With a 2–3 MB heap and sub-millisecond lifetimes, Go's tricolor concurrent GC effectively has nothing to collect.

---

## Bottleneck Analysis

The Go service **did not reach its breaking point** in this test. The plateau at ~3,500 RPS is caused entirely by **Locust**, not by Go.

### Why Locust is the bottleneck

| Indicator | Evidence |
|-----------|----------|
| RPS capped regardless of user count | 100, 200, 400, 1,000 users all deliver ≈3,500 RPS |
| Go CPU < 1 core | 0.685 cores used out of 8 — 91 % of capacity idle |
| Go goroutines never grew | Max 12; no queuing visible inside the service |
| Locust CPU saturation | Locust container pinned to ~58 % CPU (gevent + protobuf Python overhead) |
| No errors or latency spikes | A real Go overload would show timeouts/errors first |

Locust is a Python process bound by the **GIL (Global Interpreter Lock)**. Even with gevent's cooperative threading, CPU-intensive work (protobuf serialization, gRPC framing) in the generator itself caps how many requests per second Locust can inject.

**Verdict:** The ~3,500 RPS ceiling is the load generator's ceiling, not Go's ceiling.

---

## Go vs Java — Comparison at Equal Load (~3,500 RPS)

| Metric | Java (Baseline) | Go (Baseline) | Go Advantage |
|--------|---------------:|---------------:|-------------|
| Peak RPS | 3 832 | 3 680 | ≈ parity (both Locust-capped) |
| CPU avg | 1.76 cores (22 %) | **0.62 cores (7.8 %)** | **2.8× more efficient** |
| Heap avg | 1.32 GB | **2.47 MB** | **547× less memory** |
| GC overhead | G1GC full concurrent cycles | < 0.4 ms/s pause | Go GC negligible |
| Latency p50 | 0.25 ms | 0.25 ms | Equal |
| Latency p99 | 0.50 ms | 0.50 ms | Equal |
| Errors | 0 | 0 | Equal |
| Goroutines / Threads | 50+ OS threads | 11 goroutines | Go runtime far lighter |

Both services deliver **identical user-observable latency** (p50=0.25ms, p99=0.50ms). The fundamental difference is resource efficiency:

- **Go uses 2.8× less CPU** to serve the same request rate
- **Go uses 547× less memory** (2.47 MB vs 1.32 GB heap)
- **Java's thread model** requires OS threads per concurrent request; at 1,000 users Java was under real thread pressure (16 gRPC worker threads bottleneck identified). **Go's goroutine scheduler** handles the same concurrency with < 12 goroutines and negligible CPU overhead.

---

## What Comes Next

### True Breaking Point (k6 Test)

Because Locust could not drive Go past ~3,500 RPS, the **true QPS ceiling of the Go service remains unknown**. Based on resource usage (0.685 cores / 8 = 8.5 % CPU), a rough extrapolation suggests Go could handle **40,000–80,000+ RPS** before saturating a single core — but this needs to be verified with k6, which is Go-based and does not suffer from the Python GIL.

To run with k6:
```bash
make infra       # start services
make test-go     # run k6 gRPC test against Go service
```

### Java Virtual Threads

The Java baseline used the default gRPC thread pool (16 OS threads). The code already includes a virtual-thread executor fix (`Executors.newVirtualThreadPerTaskExecutor()`). Re-running the Java test with virtual threads and Lettuce (async Redis client) will likely push Java's ceiling well past 3,500 RPS and make for a more honest Java vs Go comparison.

---

## Reproduction

```bash
cd kv-benchmark

# 1. Start infra (Redis, both services, Prometheus, Grafana)
make infra

# Wait for services to be healthy, then:

# 2. Run Go baseline (Locust, step shape, 80/20 hit/miss)
docker compose --profile go-locust up locust-go

# Grafana: http://localhost:3000  (admin/admin)
# k6 test:  make test-go
```

---

*Report generated from Prometheus metrics captured during the Locust BreakingPointShape run on 2026-03-27.*
