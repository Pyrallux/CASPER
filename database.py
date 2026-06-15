import sqlite3
from config import Config

def get_db_connection():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Core data storage
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS historical_failures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pipeline_id TEXT NOT NULL,
        job_id TEXT NOT NULL,
        project_id TEXT NOT NULL,
        error_signature TEXT NOT NULL,
        file_diff_summary TEXT NOT NULL,
        resolution_summary TEXT,
        confidence_score INTEGER DEFAULT 0,
        is_verified_by_fix BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # FTS5 Virtual table for lexical BM25 matching
    cursor.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS fts_failures_index 
    USING fts5(
        error_signature, 
        content='historical_failures', 
        content_rowid='id'
    );
    """)

    # Triggers keeping FTS mapping perfectly synchronized
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS sync_fts_insert AFTER INSERT ON historical_failures BEGIN
        INSERT INTO fts_failures_index (rowid, error_signature) VALUES (new.id, new.error_signature);
    END;
    """)

    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS sync_fts_delete AFTER DELETE ON historical_failures BEGIN
        INSERT INTO fts_failures_index (fts_failures_index, rowid, error_signature) VALUES ('delete', old.id, old.error_signature);
    END;
    """)

    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS sync_fts_update AFTER UPDATE ON historical_failures BEGIN
        INSERT INTO fts_failures_index (fts_failures_index, rowid, error_signature) VALUES ('delete', old.id, old.error_signature);
        INSERT INTO fts_failures_index (rowid, error_signature) VALUES (new.id, new.error_signature);
    END;
    """)

    conn.commit()
    conn.close()

def query_historical_context(current_error_signature: str, limit: int = 3):
    """Executes a BM25 lexical search over historical pipeline errors."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Sanitizing search parameters to bypass syntax breaks in FTS5
    clean_query = current_error_signature.replace('"', ' ').replace("'", " ")
    # Take the first few terms if signature is too massive
    clean_query = " OR ".join([f'"{token}"' for token in clean_query.split()[:15] if token.isalnum()])

    if not clean_query:
        return []

    sql = """
        SELECT h.*, f.rank 
        FROM fts_failures_index f
        JOIN historical_failures h ON f.rowid = h.id
        WHERE f.error_signature MATCH ?
        ORDER BY rank
        LIMIT ?
    """
    try:
        cursor.execute(sql, (clean_query, limit))
        results = [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        results = []
    finally:
        conn.close()
    return results

def save_initial_failure(project_id, pipeline_id, job_id, error_sig, diff_summary):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO historical_failures (project_id, pipeline_id, job_id, error_signature, file_diff_summary)
        VALUES (?, ?, ?, ?, ?)
    """, (project_id, pipeline_id, job_id, error_sig, diff_summary))
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return record_id

def update_resolution(record_id, resolution, confidence, is_verified=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE historical_failures 
        SET resolution_summary = ?, confidence_score = ?, is_verified_by_fix = ?
        WHERE id = ?
    """, (resolution, confidence, 1 if is_verified else 0, record_id))
    conn.commit()
    conn.close()