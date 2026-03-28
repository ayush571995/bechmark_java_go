# Build stage
FROM rust:1.78-alpine AS builder

RUN apk add --no-cache musl-dev protobuf-dev

WORKDIR /build

# Copy proto first (needed by build.rs)
COPY proto/ /proto/

# Copy source
COPY rust-service/Cargo.toml .
COPY rust-service/build.rs .
COPY rust-service/src/ src/

RUN cargo build --release

# ─────────────────────────────────────────────────────────────────────────────
# Runtime stage — minimal Alpine image
FROM alpine:3.19

RUN apk add --no-cache libgcc wget

COPY --from=builder /build/target/release/rust-service /usr/local/bin/rust-service

EXPOSE 50053 8082

ENV RUST_LOG=info

CMD ["rust-service"]
