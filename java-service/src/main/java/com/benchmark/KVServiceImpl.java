package com.benchmark;

import com.benchmark.proto.GetRequest;
import com.benchmark.proto.GetResponse;
import com.benchmark.proto.KeyValueServiceGrpc;
import io.grpc.Status;
import io.grpc.stub.StreamObserver;
import io.prometheus.client.Counter;
import io.prometheus.client.Histogram;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class KVServiceImpl extends KeyValueServiceGrpc.KeyValueServiceImplBase {

    private static final Logger log = LoggerFactory.getLogger(KVServiceImpl.class);

    private static final Counter REQUESTS = Counter.build()
            .name("grpc_requests_total")
            .help("Total gRPC requests")
            .labelNames("service", "method", "status")
            .register();

    private static final Histogram LATENCY = Histogram.build()
            .name("grpc_request_duration_seconds")
            .help("gRPC request duration in seconds")
            .labelNames("service", "method")
            .buckets(0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
            .register();

    private final RedisStore store;

    public KVServiceImpl(RedisStore store) {
        this.store = store;
    }

    @Override
    public void get(GetRequest request, StreamObserver<GetResponse> out) {
        Histogram.Timer timer = LATENCY.labels("java", "Get").startTimer();
        try {
            // Blocking call — fine with virtual threads.
            // The JVM unmounts this virtual thread from the carrier OS thread
            // during the Jedis network wait, keeping the OS thread fully busy.
            String raw = store.get(request.getKey());
            String value = (raw != null) ? raw : "{}";

            REQUESTS.labels("java", "Get", raw != null ? "ok" : "not_found").inc();
            out.onNext(GetResponse.newBuilder().setValue(value).build());
            out.onCompleted();

        } catch (Exception e) {
            log.error("key={} error={}", request.getKey(), e.getMessage());
            REQUESTS.labels("java", "Get", "error").inc();
            out.onError(Status.INTERNAL
                    .withDescription(e.getMessage())
                    .asRuntimeException());
        } finally {
            timer.observeDuration();
        }
    }
}
