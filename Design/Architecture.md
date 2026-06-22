# TypeMAX  System Architecture

---

## 1. Overview

TypeMAX is a prefix-based search typeahead engine designed for low-latency autocomplete. It ingests a large-scale word frequency dataset, serves real-time prefix suggestions, and updates query popularity through an asynchronous batch-write pipeline. The system is built on three infrastructure layers: a FastAPI application server, a Redis caching and queuing tier, and a PostgreSQL persistence layer.

---

## 2. High-Level Architecture

```mermaid
graph TB
    subgraph CLIENT["Client Layer"]
        style CLIENT fill:#1a1a2e,stroke:#e94560,color:#fff
        UI["React Frontend<br/>Debounced Input + Suggestion Dropdown"]
    end

    subgraph SERVER["Application Layer"]
        style SERVER fill:#16213e,stroke:#0f3460,color:#fff
        API["FastAPI Server<br/>server_routing.py"]
        HASH["Consistent Hashing<br/>consistent_hashing.py"]
        MODELS["Pydantic Models<br/>application_models.py"]
        TREND["Trending Calculator<br/>trending_calculator.py"]
    end

    subgraph CACHE["Cache Layer  Redis"]
        style CACHE fill:#0f3460,stroke:#e94560,color:#fff
        DB0["Redis DB 0"]
        DB1["Redis DB 1"]
        DB2["Redis DB 2"]
        DB8["Redis DB 8<br/>Trending Counters"]
        DB9["Redis DB 9<br/>Search Queue"]
    end

    subgraph WORKER["Background Worker"]
        style WORKER fill:#533483,stroke:#e94560,color:#fff
        BATCH["Batch Processor<br/>batch_processor.py"]
    end

    subgraph STORAGE["Persistence Layer"]
        style STORAGE fill:#2b2d42,stroke:#e94560,color:#fff
        PG["PostgreSQL<br/>search_queries table<br/>Connection Pool"]
        LOADER["Data Loader<br/>data_loader.py"]
        DATASET["count_2w.txt<br/>Google Web Corpus"]
    end

    UI -->|"GET /suggest?q=prefix"| API
    UI -->|"POST /search"| API
    API --> HASH
    API --> MODELS
    API --> TREND
    HASH --> DB0
    HASH --> DB1
    HASH --> DB2
    API -->|"Queue writes"| DB9
    TREND --> DB8
    BATCH -->|"Pop from queue"| DB9
    BATCH -->|"Bulk upsert"| PG
    BATCH -->|"Invalidate cache"| DB0
    BATCH -->|"Invalidate cache"| DB1
    BATCH -->|"Invalidate cache"| DB2
    BATCH -->|"Record trending"| DB8
    API -->|"Cache miss fallback"| PG
    LOADER -->|"Bulk insert"| PG
    DATASET -->|"Parse"| LOADER
```

---

## 3. Component Breakdown

### 3.1 File Map

| File | Lines | Role |
|------|-------|------|
| `server_routing.py` | 54 | FastAPI entry point. Exposes all HTTP endpoints. Routes to cache or database. |
| `redis_manager.py` | 42 | Redis connection management. Cache get/set, queue push/pop operations. |
| `database_manager.py` | 74 | PostgreSQL connection pool. Schema init, bulk upsert, prefix query. |
| `consistent_hashing.py` | 6 | MD5-based hash function mapping prefixes to Redis DB indices. |
| `batch_processor.py` | 43 | Background loop. Pops search queue, aggregates, flushes to Postgres. |
| `trending_calculator.py` | 48 | Recency-weighted scoring. Blends all-time count with recent search spikes. |
| `application_models.py` | 16 | Pydantic request/response schemas. |
| `data_loader.py` | 56 | One-time dataset ingestion from Google Web Corpus into PostgreSQL. |

### 3.2 Dependency Graph

```mermaid
graph LR
    style SR fill:#e94560,stroke:#1a1a2e,color:#fff
    style RM fill:#0f3460,stroke:#1a1a2e,color:#fff
    style DM fill:#533483,stroke:#1a1a2e,color:#fff
    style CH fill:#e94560,stroke:#1a1a2e,color:#fff
    style BP fill:#533483,stroke:#1a1a2e,color:#fff
    style TC fill:#0f3460,stroke:#1a1a2e,color:#fff
    style AM fill:#2b2d42,stroke:#e94560,color:#fff
    style DL fill:#2b2d42,stroke:#e94560,color:#fff

    SR["server_routing"] --> CH["consistent_hashing"]
    SR --> RM["redis_manager"]
    SR --> DM["database_manager"]
    SR --> TC["trending_calculator"] 
    SR --> AM["application_models"]
    BP["batch_processor"] --> RM
    BP --> DM
    BP --> TC
    BP --> CH
    TC --> RM
    DL["data_loader"] --> DM
```

---

## 4. Read Path  Suggestion Flow

When a user types a prefix, the system resolves it through cache first, falling back to PostgreSQL on a miss.

```mermaid
sequenceDiagram
    autonumber
    participant C as React Client
    participant S as FastAPI Server
    participant H as Consistent Hashing
    participant R as Redis Cache
    participant T as Trending Calculator
    participant P as PostgreSQL

    rect rgb(26, 26, 46)
        C->>S: GET /suggest?q=ipho
        S->>H: get_assigned_node("ipho")
        H-->>S: node_index = 1
        S->>R: get_cached_suggestions(1, "ipho")
    end

    alt Cache Hit
        rect rgb(15, 52, 96)
            R-->>S: cached suggestions
            S-->>C: JSON array (top 10)
        end
    else Cache Miss
        rect rgb(83, 52, 131)
            R-->>S: None
            S->>P: SELECT query, count WHERE query LIKE 'ipho%' LIMIT 50
            P-->>S: raw results
            S->>T: calculate_trending_suggestions(results)
            T->>R: get recent_search counts
            R-->>T: recency data
            T-->>S: re-ranked results
            S->>R: set_cached_suggestions(1, "ipho", top_10)
            S-->>C: JSON array (top 10)
        end
    end
```

### Read Path Characteristics

| Property | Value |
|----------|-------|
| Cache TTL | 300 seconds (5 minutes) |
| Max results returned | 10 |
| DB fetch limit | 50 (pre-trending re-rank) |
| Hash function | MD5 modulo 3 |
| Index type | B-tree with `text_pattern_ops` |
| Measured p50 latency | 3ms (cached) |
| Measured p95 latency | 28ms |

---

## 5. Write Path  Search Submission Flow

Search submissions are never written synchronously to PostgreSQL. They are queued in Redis and flushed in batches by a background worker.

```mermaid
sequenceDiagram
    autonumber
    participant C as React Client
    participant S as FastAPI Server
    participant Q as Redis Queue (DB 9)
    participant B as Batch Processor
    participant P as PostgreSQL
    participant R as Redis Cache
    participant T as Trending Store (DB 8)

    rect rgb(26, 26, 46)
        C->>S: POST /search { "query": "iphone" }
        S->>Q: RPUSH search_queue "iphone"
        S-->>C: { "message": "Searched" }
    end

    rect rgb(83, 52, 131)
        Note over B: Background loop (every 5 seconds)
        B->>Q: LRANGE + LTRIM (atomic pop up to 50)
        Q-->>B: ["iphone", "iphone", "ipad", ...]
        Note over B: Aggregate duplicates in-memory
        B->>T: record_recent_search for each query
        B->>P: INSERT ON CONFLICT DO UPDATE (bulk)
        Note over B: Compute all prefix substrings
        B->>R: DELETE cached entries for affected prefixes
    end
```

### Write Path Characteristics

| Property | Value |
|----------|-------|
| Queue backend | Redis List (DB 9) |
| Batch size | Up to 50 items per cycle |
| Flush interval | 5 seconds |
| Dedup strategy | In-memory aggregation before DB write |
| Cache invalidation | All prefix substrings of each query |

---

## 6. Consistent Hashing

Prefixes are mapped to one of three logical Redis databases using MD5 hashing. This distributes cache load and demonstrates the distributed cache requirement.

```mermaid
graph LR
    subgraph HASH_RING["Hash Ring (MD5 mod 3)"]
        style HASH_RING fill:#1a1a2e,stroke:#e94560,color:#fff
        INPUT["Input Prefix"] --> MD5["MD5 Hash"]
        MD5 --> MOD["mod 3"]
        MOD -->|"0"| N0["Redis DB 0"]
        MOD -->|"1"| N1["Redis DB 1"]
        MOD -->|"2"| N2["Redis DB 2"]
    end

    style INPUT fill:#e94560,stroke:#1a1a2e,color:#fff
    style MD5 fill:#0f3460,stroke:#1a1a2e,color:#fff
    style MOD fill:#533483,stroke:#1a1a2e,color:#fff
    style N0 fill:#2b2d42,stroke:#e94560,color:#fff
    style N1 fill:#2b2d42,stroke:#e94560,color:#fff
    style N2 fill:#2b2d42,stroke:#e94560,color:#fff
```

**Properties:**

- Deterministic: the same prefix always maps to the same node.
- Uniform: MD5 provides near-uniform distribution across the three nodes.
- The `/cache/debug` endpoint exposes which node owns a given prefix and whether the lookup was a cache hit or miss.

---

## 7. Trending Score Calculation

Trending rankings blend historical popularity with recency to prevent stale data from permanently dominating results.

```mermaid
graph TD
    subgraph SCORING["Trending Score Pipeline"]
        style SCORING fill:#1a1a2e,stroke:#e94560,color:#fff
        DB_COUNT["All-Time Count<br/>(from PostgreSQL)"]
        RECENT["Recent Search Count<br/>(from Redis DB 8, 2hr window)"]
        WEIGHT["Recency Weight<br/>(multiplier = 50)"]

        RECENT --> MULTIPLY["recent_count x recency_weight"]
        WEIGHT --> MULTIPLY
        DB_COUNT --> ADD["all_time_count + weighted_recent"]
        MULTIPLY --> ADD
        ADD --> SORT["Sort descending by final score"]
        SORT --> TOP10["Return top 10"]
    end

    style DB_COUNT fill:#0f3460,stroke:#1a1a2e,color:#fff
    style RECENT fill:#533483,stroke:#1a1a2e,color:#fff
    style WEIGHT fill:#e94560,stroke:#1a1a2e,color:#fff
    style MULTIPLY fill:#2b2d42,stroke:#e94560,color:#fff
    style ADD fill:#2b2d42,stroke:#e94560,color:#fff
    style SORT fill:#0f3460,stroke:#1a1a2e,color:#fff
    style TOP10 fill:#e94560,stroke:#1a1a2e,color:#fff
```

**Formula:**

```
Final Score = all_time_count + (recent_count x 50)
```

| Mechanism | Detail |
|-----------|--------|
| Recent window | 2 hours (TTL on Redis keys) |
| Storage | Redis DB 8, sorted set + per-query counters |
| Decay | Keys auto-expire after 7200 seconds |
| Invalidation | Batch processor invalidates cache after flush |

---

## 8. Database Schema

```mermaid
erDiagram
    SEARCH_QUERIES {
        TEXT query PK "Primary key  the search term"
        BIGINT count "Cumulative search frequency"
    }
```

**Index:**

```sql
CREATE INDEX idx_query_prefix
ON search_queries (query text_pattern_ops);
```

The `text_pattern_ops` operator class enables B-tree index usage for `LIKE 'prefix%'` pattern matching, avoiding sequential scans on 100k+ rows.

**Connection Pooling:**

- Pool type: `psycopg2.pool.SimpleConnectionPool`
- Min connections: 2
- Max connections: 10

---

## 9. Redis Database Allocation

| DB Index | Purpose | Data Type |
|----------|---------|-----------|
| 0 | Cache node 0 | String (JSON-serialized suggestions) |
| 1 | Cache node 1 | String (JSON-serialized suggestions) |
| 2 | Cache node 2 | String (JSON-serialized suggestions) |
| 8 | Trending counters | Sorted set + String counters |
| 9 | Search queue | List (FIFO queue) |

---

## 10. Failure Modes and Trade-Offs

### 10.1 Batch Write Durability

The asynchronous write path trades strict durability for reduced database pressure. If Redis crashes before the batch processor flushes the queue, pending search submissions in the Redis List are lost. This is an intentional trade-off: Redis is more durable than a pure in-memory buffer (it supports AOF persistence), and the write reduction benefit outweighs the risk of losing a small number of recent searches.

### 10.2 Cache Staleness Window

Between a search submission and the next batch flush (up to 5 seconds), cached suggestions may not reflect the latest search counts. This is acceptable for a typeahead system where approximate ranking is sufficient.

### 10.3 Connection Pool Exhaustion

Under extreme concurrent load, all 10 pooled connections may be in use. Requests will block until a connection is returned. The pool size is configurable via `MAX_CONNECTIONS`.

```mermaid
graph TD
    subgraph TRADEOFFS["Design Trade-Offs"]
        style TRADEOFFS fill:#1a1a2e,stroke:#e94560,color:#fff

        A["Async Batch Writes"] -->|"Benefit"| A1["Reduced DB write load"]
        A -->|"Cost"| A2["Possible data loss on Redis crash"]

        B["Cache with TTL"] -->|"Benefit"| B1["Sub-millisecond reads"]
        B -->|"Cost"| B2["Up to 5min stale data"]

        C["Connection Pooling"] -->|"Benefit"| C1["Eliminates per-request connect overhead"]
        C -->|"Cost"| C2["Blocking under pool exhaustion"]
    end

    style A fill:#0f3460,stroke:#1a1a2e,color:#fff
    style A1 fill:#2b2d42,stroke:#0f3460,color:#fff
    style A2 fill:#2b2d42,stroke:#e94560,color:#fff
    style B fill:#533483,stroke:#1a1a2e,color:#fff
    style B1 fill:#2b2d42,stroke:#533483,color:#fff
    style B2 fill:#2b2d42,stroke:#e94560,color:#fff
    style C fill:#e94560,stroke:#1a1a2e,color:#fff
    style C1 fill:#2b2d42,stroke:#e94560,color:#fff
    style C2 fill:#2b2d42,stroke:#e94560,color:#fff
```

---

## 11. Data Ingestion Pipeline

```mermaid
graph LR
    subgraph INGESTION["Dataset Ingestion"]
        style INGESTION fill:#1a1a2e,stroke:#e94560,color:#fff
        SRC["count_2w.txt<br/>Google Web Corpus"] --> PARSE["Parse lines<br/>Split word + count"]
        PARSE --> BATCH["Batch records<br/>(5000 per batch)"]
        BATCH --> UPSERT["INSERT ON CONFLICT DO NOTHING<br/>into search_queries"]
        UPSERT --> PG["PostgreSQL"]
    end

    style SRC fill:#e94560,stroke:#1a1a2e,color:#fff
    style PARSE fill:#0f3460,stroke:#1a1a2e,color:#fff
    style BATCH fill:#533483,stroke:#1a1a2e,color:#fff
    style UPSERT fill:#2b2d42,stroke:#e94560,color:#fff
    style PG fill:#0f3460,stroke:#1a1a2e,color:#fff
```

| Property | Value |
|----------|-------|
| Dataset | Peter Norvig's Google Web Trillion Word Corpus (bigrams) |
| File | `count_2w.txt` |
| Batch insert size | 5000 rows per commit |
| Conflict handling | `ON CONFLICT DO NOTHING` (skip duplicates) |
| Pre-ingestion | Truncates table and flushes all Redis databases |

---

## 12. Measured Performance

All metrics captured via a standalone master stress test suite against a live server with the full dataset loaded.

| Metric | Value |
|--------|-------|
| `/suggest` p50 latency (cached) | 3ms |
| `/suggest` p95 latency | 28ms |
| Concurrent `/suggest` (30 parallel) | 30/30 success |
| Concurrent `/search` (30 parallel) | 30/30 success |
| Batch write accuracy | 10/10 exact count |
| Data integrity under load (20 concurrent writes) | 20/20 exact count |
| Cache hit detection | Verified via `/cache/debug` |
| Consistent hash determinism | Same prefix maps to same node across 10 calls |
| Hash distribution | Near-uniform across DB 0, 1, 2 |
| SQL injection resistance | Verified, data intact post-attempt |
| Overall pass rate | 31/31 (100%) |

> **Note:** On Windows, `localhost` resolves to IPv6 (`::1`) first and incurs a ~2 second fallback timeout to IPv4. Use `127.0.0.1` to bypass this. The measured latencies above use direct IPv4.

---
