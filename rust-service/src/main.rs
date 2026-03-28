use axum::{routing::get, Router};
use deadpool_redis::{Config, Runtime};
use prometheus::{CounterVec, Encoder, HistogramOpts, HistogramVec, Opts, TextEncoder};
use std::net::SocketAddr;
use std::sync::Arc;
use tokio::net::TcpListener;
use tonic::{transport::Server, Request, Response, Status};

pub mod proto {
    tonic::include_proto!("kvbenchmark");
}

use proto::key_value_service_server::{KeyValueService, KeyValueServiceServer};
use proto::{GetRequest, GetResponse};

#[derive(Clone)]
struct KVServer {
    pool:             Arc<deadpool_redis::Pool>,
    requests_total:   CounterVec,
    request_duration: HistogramVec,
}

#[tonic::async_trait]
impl KeyValueService for KVServer {
    async fn get(&self, req: Request<GetRequest>) -> Result<Response<GetResponse>, Status> {
        let timer = self.request_duration
            .with_label_values(&["rust", "Get"])
            .start_timer();

        let key = req.into_inner().key;

        let mut conn = self.pool.get().await
            .map_err(|e| Status::internal(e.to_string()))?;

        let result: Option<String> = redis::cmd("GET")
            .arg(&key)
            .query_async(&mut conn)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;

        timer.observe_duration();

        match result {
            Some(value) => {
                self.requests_total.with_label_values(&["rust", "Get", "ok"]).inc();
                Ok(Response::new(GetResponse { value }))
            }
            None => {
                self.requests_total.with_label_values(&["rust", "Get", "not_found"]).inc();
                Ok(Response::new(GetResponse { value: "{}".to_string() }))
            }
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt::init();

    let redis_host   = std::env::var("REDIS_HOST").unwrap_or_else(|_| "redis".into());
    let redis_port   = std::env::var("REDIS_PORT").unwrap_or_else(|_| "6379".into());
    let grpc_port    = std::env::var("GRPC_PORT").unwrap_or_else(|_| "50053".into());
    let metrics_port = std::env::var("METRICS_PORT").unwrap_or_else(|_| "8082".into());

    // ── Redis connection pool ────────────────────────────────────────────────
    let mut cfg = Config::from_url(format!("redis://{}:{}", redis_host, redis_port));
    cfg.pool = Some(deadpool_redis::PoolConfig::new(200));
    let pool = Arc::new(cfg.create_pool(Some(Runtime::Tokio1))?);
    // verify connection
    let _ = pool.get().await.expect("Cannot connect to Redis");
    tracing::info!("Redis connected at {}:{}", redis_host, redis_port);

    // ── Prometheus metrics ───────────────────────────────────────────────────
    let requests_total = CounterVec::new(
        Opts::new("grpc_requests_total", "Total gRPC requests"),
        &["service", "method", "status"],
    )?;
    let request_duration = HistogramVec::new(
        HistogramOpts::new("grpc_request_duration_seconds", "gRPC request duration in seconds")
            .buckets(vec![0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]),
        &["service", "method"],
    )?;
    prometheus::register(Box::new(requests_total.clone()))?;
    prometheus::register(Box::new(request_duration.clone()))?;

    // ── Metrics HTTP server ──────────────────────────────────────────────────
    let metrics_addr: SocketAddr = format!("0.0.0.0:{}", metrics_port).parse()?;
    let app = Router::new().route("/metrics", get(|| async {
        let encoder = TextEncoder::new();
        let mut buf  = Vec::new();
        encoder.encode(&prometheus::gather(), &mut buf).unwrap();
        String::from_utf8(buf).unwrap()
    }));

    tokio::spawn(async move {
        let listener = TcpListener::bind(metrics_addr).await.unwrap();
        tracing::info!("Metrics listening on {}/metrics", metrics_addr);
        axum::serve(listener, app).await.unwrap();
    });

    // ── gRPC server ──────────────────────────────────────────────────────────
    let server = KVServer { pool, requests_total, request_duration };
    let grpc_addr: SocketAddr = format!("0.0.0.0:{}", grpc_port).parse()?;
    tracing::info!("Rust gRPC server starting on {}", grpc_addr);

    Server::builder()
        .add_service(KeyValueServiceServer::new(server))
        .serve(grpc_addr)
        .await?;

    Ok(())
}
