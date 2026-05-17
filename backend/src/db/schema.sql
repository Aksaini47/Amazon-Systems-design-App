-- Orders synced from Amazon SP-API
CREATE TABLE IF NOT EXISTS orders (
  order_id TEXT PRIMARY KEY,
  purchase_date TEXT,
  order_status TEXT,
  fulfillment_channel TEXT,
  asin TEXT,
  sku TEXT,
  product_title TEXT,
  quantity INTEGER,
  marketplace_id TEXT,
  has_return INTEGER DEFAULT 0,
  synced_at TEXT
);

-- AWB barcode → Order ID mapping (FBM orders)
CREATE TABLE IF NOT EXISTS awb_mappings (
  awb_number TEXT PRIMARY KEY,
  order_id TEXT REFERENCES orders(order_id),
  carrier TEXT,
  package_status TEXT
);

-- Packing and unpacking videos
CREATE TABLE IF NOT EXISTS videos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id TEXT REFERENCES orders(order_id),
  type TEXT CHECK(type IN ('packing', 'unpacking')),
  file_path TEXT,
  file_name TEXT,
  duration_seconds REAL,
  file_size_bytes INTEGER,
  recorded_at TEXT,
  uploaded_at TEXT DEFAULT (datetime('now'))
);

-- Evidence photos
CREATE TABLE IF NOT EXISTS images (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id TEXT REFERENCES orders(order_id),
  file_path TEXT,
  file_name TEXT,
  captured_at TEXT DEFAULT (datetime('now'))
);

-- Returns from SP-API returns reports
CREATE TABLE IF NOT EXISTS returns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id TEXT REFERENCES orders(order_id),
  return_date TEXT,
  amazon_rma_id TEXT,
  return_tracking TEXT,
  reason_code TEXT,
  refund_amount REAL,
  claim_status TEXT DEFAULT 'none',
  updated_at TEXT DEFAULT (datetime('now'))
);

-- FBA inbound shipments (seller → Amazon warehouse)
CREATE TABLE IF NOT EXISTS fba_shipments (
  shipment_id TEXT PRIMARY KEY,
  shipment_name TEXT,
  destination_fc TEXT,
  shipment_status TEXT,
  unit_count INTEGER DEFAULT 0,
  created_date TEXT,
  synced_at TEXT
);

-- Sync job state tracking
CREATE TABLE IF NOT EXISTS sync_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_name TEXT,
  last_run TEXT,
  status TEXT,
  message TEXT
);
