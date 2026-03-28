package com.benchmark;

import io.grpc.Server;
import io.grpc.ServerBuilder;
import io.prometheus.client.exporter.HTTPServer;
import io.prometheus.client.hotspot.DefaultExports;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.concurrent.Executors;

public class Main {

    private static final Logger log = LoggerFactory.getLogger(Main.class);

    public static void main(String[] args) throws Exception {
        // JVM metrics (heap, GC, threads, etc.)
        DefaultExports.initialize();

        String redisHost  = env("REDIS_HOST",    "redis");
        int    redisPort  = Integer.parseInt(env("REDIS_PORT",    "6379"));
        int    grpcPort   = Integer.parseInt(env("GRPC_PORT",     "50051"));
        int    metricsPort = Integer.parseInt(env("METRICS_PORT", "8080"));

        RedisStore store = new RedisStore(redisHost, redisPort);
        store.ping();

        // Prometheus HTTP endpoint
        HTTPServer metricsServer = new HTTPServer(metricsPort);
        log.info("Prometheus metrics listening on :{}/metrics", metricsPort);

        // Virtual thread executor (Java 21):
        // Each incoming gRPC request gets its own virtual thread.
        // When Jedis.get() blocks on the network, the JVM unmounts the virtual
        // thread from the carrier OS thread — the OS thread runs other virtual
        // threads instead of sitting idle. No thread-count ceiling.
        Server server = ServerBuilder.forPort(grpcPort)
                .executor(Executors.newVirtualThreadPerTaskExecutor())
                .addService(new KVServiceImpl(store))
                .build()
                .start();

        log.info("Java gRPC server started on :{} (virtual-thread executor)", grpcPort);

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            log.info("Shutting down...");
            server.shutdown();
            store.close();
            metricsServer.close();
        }));

        server.awaitTermination();
    }

    private static String env(String key, String defaultVal) {
        String v = System.getenv(key);
        return (v != null && !v.isBlank()) ? v : defaultVal;
    }
}
