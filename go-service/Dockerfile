# ── Stage 1: generate proto + build ──────────────────────────────────────────
FROM golang:1.22-alpine AS builder

RUN apk add --no-cache protobuf-dev git

# Install protoc plugins
RUN go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.33.0
RUN go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.3.0

WORKDIR /build

# Copy module manifest and all Go sources
COPY go-service/go.mod ./
COPY go-service/main.go ./
COPY go-service/server/ server/

# Copy and generate proto stubs into proto/ (matches go_package option)
COPY proto/ /proto/
RUN mkdir -p proto && \
    protoc \
      --go_out=. \
      --go_opt=module=github.com/benchmark/go-service \
      --go-grpc_out=. \
      --go-grpc_opt=module=github.com/benchmark/go-service \
      -I /proto \
      /proto/kv.proto

# Now that all imports are known, tidy fetches and pins dependencies
RUN go mod tidy

# Build a static binary
RUN CGO_ENABLED=0 GOOS=linux go build -o go-service .

# ── Stage 2: minimal runtime ──────────────────────────────────────────────────
FROM alpine:3.19
RUN apk add --no-cache ca-certificates
WORKDIR /app
COPY --from=builder /build/go-service .

EXPOSE 50052 8081
CMD ["./go-service"]
