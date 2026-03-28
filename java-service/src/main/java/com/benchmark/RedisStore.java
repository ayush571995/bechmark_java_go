package com.benchmark;

import io.lettuce.core.RedisClient;
import io.lettuce.core.RedisURI;
import io.lettuce.core.api.StatefulRedisConnection;
import io.lettuce.core.api.async.RedisAsyncCommands;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.concurrent.CompletableFuture;

/**
 * Redis-backed key-value store — async via Lettuce.
 *
 * Lettuce uses a single Netty connection that pipelines commands concurrently.
 * Unlike Jedis (one connection per thread), a single Lettuce connection can
 * handle thousands of in-flight commands without blocking any OS thread.
 */
public class RedisStore {

    private static final Logger log = LoggerFactory.getLogger(RedisStore.class);

    private final RedisClient client;
    private final StatefulRedisConnection<String, String> connection;
    private final RedisAsyncCommands<String, String> async;

    public RedisStore(String host, int port) {
        RedisURI uri = RedisURI.builder()
                .withHost(host)
                .withPort(port)
                .withTimeout(java.time.Duration.ofSeconds(2))
                .build();
        this.client = RedisClient.create(uri);
        this.connection = client.connect();
        this.async = connection.async();
        log.info("RedisStore (Lettuce async) connected → {}:{}", host, port);
    }

    public void ping() {
        String pong = connection.sync().ping();
        log.info("Redis ping: {}", pong);
    }

    /**
     * Fetch a value by key — fully async, never blocks a thread.
     * The returned CompletableFuture completes on Lettuce's Netty event-loop thread.
     */
    public CompletableFuture<String> getAsync(String key) {
        return async.get(key).toCompletableFuture();
    }

    public void close() {
        connection.close();
        client.shutdown();
    }
}
