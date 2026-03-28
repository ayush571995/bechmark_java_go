FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir locust==2.24.0 grpcio==1.62.1 grpcio-tools==1.62.1

# Generate Python proto stubs from the shared proto file
COPY proto/ /proto/
RUN python -m grpc_tools.protoc \
      -I /proto \
      --python_out=. \
      --grpc_python_out=. \
      /proto/kv.proto

COPY locust/locustfile.py locust/locustfile_java.py locust/locustfile_go.py ./

EXPOSE 8089

CMD ["locust", "-f", "locustfile.py"]
