┌────────────────────────────────────────────────────────────┐
│                 STANDARD DATA INGESTION PIPELINE            │
└────────────────────────────────────────────────────────────┘

[1] Data Sources
    APIs / Databases / Files / Web pages / Logs / Streams
           │
           ▼
[2] Extract
    Fetch, crawl, query, read, or stream raw data
           │
           ▼
[3] Validate Input
    Check schema, required fields, file format, encoding
           │
           ▼
[4] Clean & Normalize
    Remove noise, fix formatting, standardize structure
           │
           ▼
[5] Transform
    Convert into target format:
    JSON / CSV / Markdown / Parquet / Documents / Chunks
           │
           ▼
[6] Deduplicate & Detect Changes
    Compare IDs, hashes, timestamps, versions
           │
           ▼
[7] Enrich Metadata
    Add source URL, title, author, timestamp, tags, permissions
           │
           ▼
[8] Store Raw + Processed Data
    Save original data and cleaned output for traceability
           │
           ▼
[9] Load to Target System
    Database / Data warehouse / Search index / Vector store
           │
           ▼
[10] Log & Monitor
     Record added, updated, skipped, failed, latency, cost
           │
           ▼
[11] Schedule / Trigger
     Cron job, event trigger, queue, webhook, or streaming loop
           │
           ▼
[12] Retry & Alert
     Handle failures, retry safely, notify when needed