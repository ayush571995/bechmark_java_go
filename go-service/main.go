package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"time"

	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"
	"google.golang.org/grpc"

	pb "github.com/benchmark/go-service/proto"
	"github.com/benchmark/go-service/server"
)

func main() {
	rdb := mustConnectRedis()

	// Prometheus metrics endpoint
	go func() {
		http.Handle("/metrics", promhttp.Handler())
		addr := ":" + env("METRICS_PORT", "8081")
		log.Printf("Prometheus metrics on %s/metrics", addr)
		log.Fatal(http.ListenAndServe(addr, nil))
	}()

	grpcAddr := ":" + env("GRPC_PORT", "50052")
	lis, err := net.Listen("tcp", grpcAddr)
	if err != nil {
		log.Fatalf("listen %s: %v", grpcAddr, err)
	}

	s := grpc.NewServer()
	pb.RegisterKeyValueServiceServer(s, server.NewKVServer(rdb))

	log.Printf("Go gRPC server started on %s", grpcAddr)
	if err := s.Serve(lis); err != nil {
		log.Fatalf("serve: %v", err)
	}
}

func mustConnectRedis() *redis.Client {
	addr := fmt.Sprintf("%s:%s", env("REDIS_HOST", "redis"), env("REDIS_PORT", "6379"))
	rdb := redis.NewClient(&redis.Options{
		Addr:         addr,
		PoolSize:     200,
		MinIdleConns: 20,
		DialTimeout:  3 * time.Second,
		ReadTimeout:  2 * time.Second,
	})

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	for i := 0; i < 15; i++ {
		if err := rdb.Ping(ctx).Err(); err == nil {
			log.Printf("Redis connected at %s", addr)
			return rdb
		}
		log.Printf("Waiting for Redis (%d/15)…", i+1)
		time.Sleep(time.Second)
	}
	log.Fatalf("Could not connect to Redis at %s", addr)
	return nil
}

func env(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}
