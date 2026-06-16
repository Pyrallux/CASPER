import sqlite3
from config import Config

def get_db_connection():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # [CHANGED: Added occurrence_count and mr_type_description to schema]
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS historical_failures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pipeline_id TEXT NOT NULL,
        job_id TEXT NOT NULL,
        project_id TEXT NOT NULL,
        error_signature TEXT NOT NULL,
        file_diff_summary TEXT NOT NULL,
        mr_type_description TEXT,          -- [NEW]
        resolution_summary TEXT,
        confidence_score INTEGER DEFAULT 0,
        occurrence_count INTEGER DEFAULT 1,  -- [NEW]
        is_verified_by_fix BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

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
    
    clean_query = current_error_signature.replace('"', ' ').replace("'", " ")
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

# [NEW: Added deduplication checker]
def check_for_duplicate(current_error_signature: str) -> int:
    """Checks if an identical or highly similar error already exists in the DB to avoid duplicates."""
    matches = query_historical_context(current_error_signature, limit=1)
    if matches:
        # In a production app, you might check if rank is past a certain threshold.
        # For this POC, if the top match shares the core signature, we consider it a duplicate.
        return matches[0]['id']
    return None

# [NEW: Function to bump the error count for preventative metrics]
def increment_occurrence(record_id: int):
    """Increments the occurrence count of a known error."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE historical_failures 
        SET occurrence_count = occurrence_count + 1 
        WHERE id = ?
    """, (record_id,))
    conn.commit()
    conn.close()

def save_initial_failure(project_id, pipeline_id, job_id, error_sig, diff_summary, mr_type_desc, resolution, confidence):
    # [CHANGED: Now includes mr_type_desc, resolution, and confidence immediately upon creation]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO historical_failures (project_id, pipeline_id, job_id, error_signature, file_diff_summary, mr_type_description, resolution_summary, confidence_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (project_id, pipeline_id, job_id, error_sig, diff_summary, mr_type_desc, resolution, confidence))
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return record_id

def update_resolution_verification(record_id, is_verified=True):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE historical_failures 
        SET is_verified_by_fix = ?
        WHERE id = ?
    """, (1 if is_verified else 0, record_id))
    conn.commit()
    conn.close()
