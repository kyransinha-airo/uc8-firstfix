-- Documents the agents open by pointer (02_documents/: agreements, manuals, bulletins,
-- history notes) and their pages. Pages come from the "--- page N ---" markers; char
-- offsets are into the page text, so a citation can quote an exact span.

CREATE TABLE IF NOT EXISTS documents (
    doc_id             TEXT PRIMARY KEY,
    doc_type           TEXT NOT NULL
                       CHECK (doc_type IN ('agreement', 'schedule', 'amendment', 'manual',
                                           'bulletin', 'history', 'report', 'closeout')),
    title              TEXT NOT NULL,
    source_path        TEXT NOT NULL,
    sha256             TEXT NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    page_count         INTEGER NOT NULL CHECK (page_count > 0),
    extractor_version  TEXT NOT NULL,
    pack_version       TEXT NOT NULL,
    loaded_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document_pages (
    doc_id             TEXT NOT NULL REFERENCES documents ON DELETE CASCADE,
    page               INTEGER NOT NULL CHECK (page >= 1),
    text               TEXT NOT NULL,
    -- Offsets of this page within the whole document text.
    char_start         INTEGER NOT NULL CHECK (char_start >= 0),
    char_end           INTEGER NOT NULL,
    extractor_version  TEXT NOT NULL,
    pack_version       TEXT NOT NULL,
    PRIMARY KEY (doc_id, page),
    CHECK (char_end >= char_start)
);
