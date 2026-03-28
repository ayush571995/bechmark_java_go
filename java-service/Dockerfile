# Build stage – compile + generate proto
FROM maven:3.9-eclipse-temurin-21 AS builder
WORKDIR /build

# Cache dependencies first
COPY java-service/pom.xml .
RUN mvn dependency:go-offline -q

# Proto lives at the repo root /proto
COPY proto/ /proto/

# Application source
COPY java-service/src/ src/

RUN mvn package -DskipTests -q

# ─────────────────────────────────────────────────────────
# Runtime stage
FROM eclipse-temurin:21-jre-jammy
WORKDIR /app
COPY --from=builder /build/target/java-grpc-service-1.0.0.jar app.jar

EXPOSE 50051 8080

# 20 GB container → give JVM 18 GB heap, leave 2 GB for JVM internals/metaspace.
# G1GC is chosen intentionally so GC pauses are visible in Grafana when the
# service is pushed past its breaking point (ZGC hides pauses too well).
ENTRYPOINT ["java", \
  "-Xms8g", \
  "-Xmx8g", \
  "-XX:+UseG1GC", \
  "-XX:MaxGCPauseMillis=200", \
  "-XX:InitiatingHeapOccupancyPercent=45", \
  "-XX:ConcGCThreads=4", \
  "-XX:+UseStringDeduplication", \
  "-XX:+ParallelRefProcEnabled", \
  "-jar", "app.jar"]
