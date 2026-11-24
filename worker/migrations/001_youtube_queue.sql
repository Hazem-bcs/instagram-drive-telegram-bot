CREATE TABLE IF NOT EXISTS youtube_jobs (
  id TEXT PRIMARY KEY,
  url TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','leased','done','failed')),
  created_at INTEGER NOT NULL DEFAULT (unixepoch()),
  lease_until INTEGER NOT NULL DEFAULT 0,
  lease_token TEXT,
  file_id TEXT
);
CREATE INDEX IF NOT EXISTS youtube_jobs_pending ON youtube_jobs(state, created_at);
