/**
 * k6 gRPC stress test — Java service (baseline: default executor, G1GC)
 *
 * Ramps VUs aggressively until errors appear in Grafana.
 * 80 % hit keys / 20 % miss keys.
 *
 * Run via docker compose:
 *   make test          (both Java + Go simultaneously)
 *   make test-java     (Java only)
 */

import grpc    from 'k6/net/grpc';
import { check } from 'k6';

const client = new grpc.Client();
client.load(['/proto'], 'kv.proto');

export const options = {
  stages: [
    { duration: '60s',  target: 50    },  // warmup
    { duration: '90s',  target: 200   },  // ~2 000 RPS
    { duration: '90s',  target: 500   },  // ~5 000 RPS
    { duration: '90s',  target: 1000  },  // ~10 000 RPS — Java default-thread wall
    { duration: '90s',  target: 2000  },  // push past
    { duration: '90s',  target: 3000  },  // heavy pressure
    { duration: '90s',  target: 5000  },  // errors expected for Java here
    { duration: '90s',  target: 8000  },
    { duration: '90s',  target: 10000 },  // ceiling
    { duration: '30s',  target: 0     },  // ramp down
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
    client.connect('java-service:50051', { plaintext: true });
    connected = true;
  }

  const res = client.invoke('kvbenchmark.KeyValueService/Get', { key: randomKey() });

  check(res, {
    'status is OK': (r) => r && r.status === grpc.StatusOK,
  });
}
