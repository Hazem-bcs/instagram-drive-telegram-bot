CREATE TABLE IF NOT EXISTS youtube_jobs (
  video_id TEXT PRIMARY KEY,
  url TEXT NOT NULL,
  created_at INTEGER NOT NULL DEFAULT (unixepoch()),
  lease_until INTEGER NOT NULL DEFAULT 0,
  lease TEXT,
  drive_id TEXT
);
