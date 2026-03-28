# kv-benchmark

gRPC key-value GET benchmark — **Java vs Go** — backed by Redis, observed with Prometheus + Grafana, load-tested with Grafana k6.

Built to answer one question: *at high QPS with a simple key-value GET, which runtime is more efficient — Java (G1GC, Lettuce async) or Go (default GC, goroutines)?*

---

## Architecture

```
                    ┌─────────────┐         ┌─────────────┐
  k6-java ──────► │ java-service │──────► │  redis-java  │
  (gRPC)          │  :50051      │         │  :6379       │
                  │  Lettuce     │         └─────────────┘
                  └─────────────┘
                        │ :8080/metrics
                        ▼
                  ┌─────────────┐         ┌─────────────┐
  k6-go   ──────► │  go-service  │──────► │  redis-go    │
  (gRPC)          │  :50052      │         │  :6380       │
                  │  go-redis    │         └─────────────┘
                  └─────────────┘
                        │ :8081/metrics
                        ▼
                  ┌─────────────┐     ┌─────────┐
                  │  Prometheus  │────►│ Grafana  │
                  │  :9090       │     │  :3000   │
                  └─────────────┘     └─────────┘
```

Each service has its **own dedicated Redis** instance — no shared backend, isolated benchmarks.

---

## Services

| Service | Language | Redis client | gRPC executor | GC |
|---------|----------|-------------|---------------|----|
| `java-service` | Java 21 | Lettuce (async, Netty) | default (16 threads) | G1GC, -Xms8g -Xmx8g |
| `go-service` | Go 1.22 | go-redis/v9 (pool=200) | goroutine per RPC | default (GOGC=100) |

Both implement the same proto:
```protobuf
service KeyValueService {
  rpc Get(GetRequest) returns (GetResponse);
}
```

---

## Quick Start

```bash
# 1. Start all infra (builds images, seeds Redis, starts Prometheus + Grafana)
make infra

# 2. Run both load tests simultaneously
make test

# View metrics
open http://localhost:3000   # Grafana (admin/admin)
open http://localhost:9090   # Prometheus
```

Individual test runs:
```bash
make test-java   # Java only
make test-go     # Go only
```

Teardown:
```bash
make down        # stop containers
make clean       # stop + remove volumes + generated proto files
```

---

## Load Shape (k6)

Both tests use an identical step-up shape — 80% cache hit / 20% miss:

| Stage | VUs | Duration |
|-------|----:|----------|
| Warmup | 50 | 60s |
| Step 2 | 200 | 90s |
| Step 3 | 500 | 90s |
| Step 4 | 1 000 | 90s |
| Step 5 | 2 000 | 90s |
| Step 6 | 3 000 | 90s |
| Step 7 | 5 000 | 90s |
| Step 8 | 8 000 | 90s |
| Step 9 | 10 000 | 90s |
| Ramp-down | 0 | 30s |

---

## Benchmark Results Summary

### k6 — Java (Lettuce async) vs Go

> Full report: [`BENCHMARK_LETTUCE_VS_GO.md`](BENCHMARK_LETTUCE_VS_GO.md)

| Metric | Java (Lettuce) | Go |
|--------|---------------:|---:|
| Peak RPS | 27 758 | **29 834** |
| CPU avg | 3.02c / 8 | **2.97c / 8** |
| Heap avg / peak | 2.24 GB / 4.65 GB | **200 MB / 745 MB** |
| p50 latency avg | 10.21 ms | **9.14 ms** |
| p99 at ~5 000 VUs | ~49 ms | ~46 ms |
| Errors | 0% | 0% |

### Three-way comparison (Locust baseline → k6 final)

| Metric | Java + Jedis | Java + Lettuce | Go |
|--------|------------:|---------------:|---:|
| Peak RPS | 26 160 | 27 758 | **29 834** |
| CPU avg | 3.77c | 3.02c | **2.97c** |
| p99 at 2 500 VUs | **1 000 ms** | 47 ms | 44 ms |
| Heap avg | 1.99 GB | 2.24 GB | **200 MB** |

Switching Java from **Jedis (blocking)** to **Lettuce (async)** was the biggest single improvement — dropping p99 from 1 000 ms to 47 ms and reducing CPU by 20%.

---

## Project Structure

```
kv-benchmark/
├── proto/
│   └── kv.proto                  # shared gRPC proto definition
│
├── java-service/
│   ├── Dockerfile
│   ├── pom.xml                   # Lettuce, gRPC, Prometheus, G1GC flags
│   └── src/main/java/com/benchmark/
│       ├── Main.java             # gRPC server startup
│       ├── KVServiceImpl.java    # async handler (CompletableFuture)
│       ├── RedisStore.java       # Lettuce async client
│       └── VeniceStore.java      # drop-in Venice SDK swap (reference)
│
├── go-service/
│   ├── Dockerfile
│   ├── main.go                   # gRPC + Redis + Prometheus startup
│   ├── go.mod
│   └── server/
│       └── kv_server.go          # gRPC handler (goroutine per RPC)
│
├── k6/
│   ├── java.js                   # k6 load test → java-service
│   └── go.js                     # k6 load test → go-service
│
├── redis-init/
│   └── seed.py                   # seeds 10 000 keys into Redis on startup
│
├── prometheus/
│   └── prometheus.yml            # scrape config for both services
│
├── grafana/
│   ├── provisioning/             # auto-provision datasource + dashboard
│   └── dashboards/
│       └── kv-benchmark.json     # 13-panel dashboard
│
├── docker-compose.yml            # full stack definition
├── Makefile                      # infra / test / down / clean targets
│
├── BENCHMARK_JAVA_locust.md      # Java baseline (Jedis, Locust)
├── BENCHMARK_GO_locust.md        # Go baseline (Locust)
├── BENCHMARK_K6_COMPARISON.md   # first k6 run (Jedis vs Go)
└── BENCHMARK_LETTUCE_VS_GO.md   # final k6 run (Lettuce vs Go)
```

---

## Key Design Decisions

**Why two Redis instances?**
Shared Redis would make one service's load affect the other's latency. Separate instances ensure the benchmark measures the gRPC service, not Redis contention.

**Why Lettuce over Jedis for Java?**
Jedis is synchronous — each call blocks an OS thread. With gRPC's default 16-thread pool, Jedis caps throughput at ~16 × (1/latency). Lettuce uses Netty non-blocking I/O — one thread handles thousands of concurrent Redis commands via pipelining, eliminating the thread ceiling.

**Why not virtual threads for Java?**
Virtual threads (`Executors.newVirtualThreadPerTaskExecutor()`) also fix the thread ceiling, but they still pay the cost of blocking Jedis. Lettuce + Netty is fundamentally more efficient because neither the Redis I/O nor the thread is ever blocked.

**Why go-redis with pool=200?**
Go's goroutines block on `rdb.Get()` but that's fine — the Go scheduler parks blocked goroutines and runs others on OS threads. The pool=200 cap means at most 200 Redis connections are open simultaneously. Increasing this to 1 000 would reduce pool-wait latency at >5 000 VUs.

---

## Venice Swap-In (Java)

`VeniceStore.java` is a drop-in replacement for `RedisStore.java`. To use Venice:

1. Add the Venice Java SDK to `pom.xml`
2. Replace `new RedisStore(...)` with `new VeniceStore(...)` in `Main.java`
3. The gRPC layer and metrics are unchanged

---

## Requirements

- Docker + Docker Compose
- `make`
- `protoc` + `protoc-gen-go` + `protoc-gen-go-grpc` (only needed for `make generate`)
