PROTO_SRC   := proto/kv.proto
PROTO_DIR   := proto
GO_OUT_DIR  := go-service

PROTOC      := protoc
PROTOC_OPTS := -I $(PROTO_DIR)

.PHONY: generate build infra test test-java test-go down clean

## generate: compile proto → Go stubs (Java handled by Maven in Docker)
generate:
	@echo "Generating Go proto stubs..."
	@mkdir -p $(GO_OUT_DIR)/proto
	$(PROTOC) $(PROTOC_OPTS) \
		--go_out=$(GO_OUT_DIR) \
		--go_opt=module=github.com/benchmark/go-service \
		--go-grpc_out=$(GO_OUT_DIR) \
		--go-grpc_opt=module=github.com/benchmark/go-service \
		$(PROTO_SRC)
	@echo "Done → $(GO_OUT_DIR)/proto/"

## infra: start both Redis instances + both gRPC services + Prometheus + Grafana
infra:
	docker compose up --build -d redis-java redis-go redis-init-java redis-init-go java-service go-service prometheus grafana

## test: run k6 stress tests against BOTH services simultaneously
test:
	docker compose --profile benchmark up k6-java k6-go

## test-java: run k6 stress test against Java gRPC service only
test-java:
	docker compose --profile java up k6-java

## test-go: run k6 stress test against Go gRPC service only
test-go:
	docker compose --profile go up k6-go

## down: stop all containers
down:
	docker compose --profile java --profile go down

## clean: remove containers, volumes, and generated proto files
clean:
	docker compose --profile java --profile go down -v
	rm -f $(GO_OUT_DIR)/proto/kv.pb.go $(GO_OUT_DIR)/proto/kv_grpc.pb.go
