/**
 * k6 gRPC stress test — Rust service (Tokio async, deadpool-redis)
 *
 * Identical load shape to go.js for a fair comparison.
 * 80 % hit keys / 20 % miss keys.
 *
 * Run via docker compose:
 *   make test-rust      (Rust only)
 *   make test-go-rust   (Go + Rust simultaneously)
 */

import grpc    from 'k6/net/grpc';
import { check } from 'k6';

const client = new grpc.Client();
client.load(['/proto'], 'kv.proto');

export const options = {
  stages: [
    { duration: '60s',  target: 50    },  // warmup
    { duration: '90s',  target: 200   },
    { duration: '90s',  target: 500   },
    { duration: '90s',  target: 1000  },
    { duration: '90s',  target: 2000  },
    { duration: '90s',  target: 3000  },
    { duration: '90s',  target: 5000  },
    { duration: '90s',  target: 8000  },
    { duration: '90s',  target: 10000 },
    { duration: '30s',  target: 0     },
  ],
};

function randomKey() {
  if (Math.random() < 0.8) {
    return 'key_' + String(Math.floor(Math.random() * 10000)).padStart(5, '0');
  }
  return 'miss_' + String(Math.floor(Math.random() * 2000)).padStart(5, '0');
}

let connected = false;

export default function () {
  if (!connected) {
    client.connect('rust-service:50053', { plaintext: true });
    connected = true;
  }

  const res = client.invoke('kvbenchmark.KeyValueService/Get', { key: randomKey() });

  check(res, {
    'status is OK': (r) => r && r.status === grpc.StatusOK,
  });
}
