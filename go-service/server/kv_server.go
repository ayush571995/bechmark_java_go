package server

import (
	"context"
	"errors"
	"log"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/redis/go-redis/v9"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	pb "github.com/benchmark/go-service/proto"
)

var (
	requestsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "grpc_requests_total",
			Help: "Total gRPC requests",
		},
		[]string{"service", "method", "status"},
	)

	requestDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "grpc_request_duration_seconds",
			Help:    "gRPC request duration in seconds",
			Buckets: []float64{0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0},
		},
		[]string{"service", "method"},
	)
)

// KVServer implements the gRPC KeyValueService using Redis as the backend.
type KVServer struct {
	pb.UnimplementedKeyValueServiceServer
	rdb *redis.Client
}

func NewKVServer(rdb *redis.Client) *KVServer {
	return &KVServer{rdb: rdb}
}

func (s *KVServer) Get(ctx context.Context, req *pb.GetRequest) (*pb.GetResponse, error) {
	timer := prometheus.NewTimer(requestDuration.WithLabelValues("go", "Get"))
	defer timer.ObserveDuration()

	val, err := s.rdb.Get(ctx, req.Key).Result()

	switch {
	case errors.Is(err, redis.Nil):
		requestsTotal.WithLabelValues("go", "Get", "not_found").Inc()
		return &pb.GetResponse{Value: "{}"}, nil
	case err != nil:
		log.Printf("redis error key=%s: %v", req.Key, err)
		requestsTotal.WithLabelValues("go", "Get", "error").Inc()
		return nil, status.Errorf(codes.Internal, "redis error: %v", err)
	}

	requestsTotal.WithLabelValues("go", "Get", "ok").Inc()
	return &pb.GetResponse{Value: val}, nil
}
