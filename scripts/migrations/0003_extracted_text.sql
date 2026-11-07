-- Retain parsed text so failed ingestion can be retried without storing uploaded files on disk.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS extracted_text TEXT;
