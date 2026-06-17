-- Example SQL file: Create a sample table
-- This SQL file demonstrates how to create a table in PostgreSQL

CREATE TABLE IF NOT EXISTS sample_data (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    value INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

