CREATE TABLE IF NOT EXISTS operation_log (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  operation_id TEXT NOT NULL UNIQUE,
  device_id TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  operation_type TEXT NOT NULL,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS device_sync_state (
  device_id TEXT PRIMARY KEY,
  last_cursor INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_operation_log_seq ON operation_log(seq);
CREATE INDEX IF NOT EXISTS idx_operation_log_device ON operation_log(device_id);
