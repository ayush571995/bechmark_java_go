package com.benchmark;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import redis.clients.jedis.Jedis;
import redis.clients.jedis.JedisPool;
import redis.clients.jedis.JedisPoolConfig;

/**
 * Redis-backed key-value store — blocking Jedis, designed for virtual threads.
 *
 * With virtual threads: when a virtual thread blocks on Jedis.get() the JVM
 * unmounts it from the carrier OS thread immediately, freeing the OS thread
 * to run other virtual threads. The OS thread is never idle — blocking is free.
 *
 * Pool size is large to support thousands of concurrent virtual threads each
 * holding a connection simultaneously.
 */
public class RedisStore {

    private static final Logger log = LoggerFactory.getLogger(RedisStore.class);

    private final JedisPool pool;

    public RedisStore(String host, int port) {
        JedisPoolConfig cfg = new JedisPoolConfig();
        cfg.setMaxTotal(1000);
        cfg.setMaxIdle(200);
        cfg.setMinIdle(50);
        cfg.setTestOnBorrow(false);
        this.pool = new JedisPool(cfg, host, port, 2000);
        log.info("RedisStore (Jedis blocking) pool created → {}:{}", host, port);
    }

    public void ping() {
        try (Jedis j = pool.getResource()) {
            log.info("Redis ping: {}", j.ping());
        }
    }

    public String get(String key) {
        try (Jedis j = pool.getResource()) {
            return j.get(key);
        }
    }

    public void close() {
        pool.close();
    }
}
