-- Run once in the Cloudflare D1 console for the visitor counter.
CREATE TABLE IF NOT EXISTS visitor_counter (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  value INTEGER NOT NULL
);

-- Start the public-facing visit sequence at 1,100.
-- Re-running this statement will NOT reset an existing counter.
INSERT OR IGNORE INTO visitor_counter (id, value) VALUES (1, 1100);
