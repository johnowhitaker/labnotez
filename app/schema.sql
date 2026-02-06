CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    body_markdown TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('notebook_page', 'photo')),
    file_path TEXT NOT NULL,
    caption TEXT NOT NULL DEFAULT '',
    sort_index INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (entry_id) REFERENCES entries(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entries_date ON entries(entry_date DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_assets_entry_kind ON assets(entry_id, kind);
CREATE INDEX IF NOT EXISTS idx_assets_entry_sort ON assets(entry_id, sort_index, id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_notebook_unique_per_entry
    ON assets(entry_id)
    WHERE kind = 'notebook_page';
