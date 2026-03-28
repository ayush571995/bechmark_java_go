package com.benchmark;

/*
 * ─────────────────────────────────────────────────────────────────────────────
 * Venice SDK swap-in (not compiled by default – add the dependency below to
 * pom.xml to enable, then replace RedisStore with VeniceStore in KVServiceImpl).
 *
 *   <dependency>
 *     <groupId>com.linkedin.venice</groupId>
 *     <artifactId>venice-thin-client</artifactId>
 *     <version>0.4.17</version>
 *   </dependency>
 *
 * Venice Router URL env-var: VENICE_ROUTER_URL  (default: http://venice-router:7777)
 * Venice Store name env-var: VENICE_STORE_NAME  (default: benchmark-store)
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * import com.linkedin.venice.client.store.AvroGenericStoreClient;
 * import com.linkedin.venice.client.store.ClientConfig;
 * import com.linkedin.venice.client.store.ClientFactory;
 *
 * public class VeniceStore {
 *
 *     private final AvroGenericStoreClient<String, Object> client;
 *
 *     public VeniceStore(String routerUrl, String storeName) {
 *         ClientConfig<Object> cfg = ClientConfig
 *                 .defaultGenericClientConfig(storeName)
 *                 .setVeniceURL(routerUrl);
 *         this.client = ClientFactory.getAndStartGenericAvroClient(cfg);
 *     }
 *
 *     public String get(String key) throws Exception {
 *         Object v = client.get(key).get();
 *         return (v != null) ? v.toString() : null;
 *     }
 *
 *     public void close() { client.close(); }
 * }
 */
public class VeniceStore {
    // Placeholder – see comment above to activate.
}
