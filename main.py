import sys
from config import Config
import database as db
from gitlab_client import GitLabClient
import parser
from llm_client import LLMClient

def process_pipeline_failure(project_id: str, mr_iid: str, job_id: str, pipeline_id: str):
    print(f"[*] CASPER Initializing analysis for Project {project_id}, Job {job_id}...")
    
    gl = GitLabClient()
    llm = LLMClient()
    
    # 1. Fetching telemetry artifacts from GitLab
    print("[*] Retrieving failure traces and MR diff details...")
    raw_log = gl.get_job_log(project_id, job_id)
    raw_changes = gl.get_mr_changes(project_id, mr_iid)
    
    # 2. Parsing telemetry to minimize runtime footprints
    parsed_log = parser.clean_and_parse_log(raw_log)
    diff_summary = parser.format_diff_summary(raw_changes)
    
    # 3. Running local FTS5 Lexical Retrieval
    print("[*] Performing database lexical match query...")
    historical_matches = db.query_historical_context(parsed_log, limit=2)
    
    # 4. Save tracking baseline record into local SQLite storage
    record_id = db.save_initial_failure(project_id, pipeline_id, job_id, parsed_log, diff_summary)
    
    # 5. Execute inference through upstream internal pipeline engine
    print("[*] Synthesizing context arrays inside model layers...")
    ai_response = llm.generate_rca_suggestion(parsed_log, diff_summary, historical_matches)
    
    suggestion = ai_response.get("suggestion", "Unable to establish distinct automated RCA recommendation.")
    confidence = ai_response.get("confidence", 0)
    
    # Update baseline tracking data entry with inference results
    db.update_resolution(record_id, suggestion, confidence, is_verified=False)
    
    # 6. Formatting and pushing results onto GitLab Merge Request threads
    comment_body = (
        f"### 🤖 CASPER Automated Root Cause Analysis\n\n"
        f"**Suggested Remediation:** {suggestion}\n\n"
        f"* **Confidence Score:** {confidence}%\n"
        f"*Note: This thread has been pre-resolved to minimize manual workflow clutter.*"
    )
    
    print("[*] Injecting analytical insight blocks into GitLab discussions...")
    gl.post_mr_discussion(project_id, mr_iid, comment_body)
    print(f"[+] RCA processed successfully. Tracking Record Saved with ID: {record_id}\n")
    return record_id

def verify_subsequent_fix(record_id: int, fixing_commit_diff: str):
    """
    Simulates the post-fix automated validation phase loop.
    This reads what was originally logged, maps it to the fix payload, and updates confirmation statuses.
    """
    print(f"[*] Starting validation loops for tracking record ID: {record_id}...")
    conn = db.get_db_connection()
    row = conn.execute("SELECT * FROM historical_failures WHERE id = ?", (record_id,)).fetchone()
    conn.close()
    
    if not row:
        print("[-] Target tracking history index target not located.")
        return

    llm = LLMClient()
    is_valid_fix = llm.verify_resolution_delta(
        historical_error=row['error_signature'],
        casper_suggestion=row['resolution_summary'],
        fixing_commit_diff=fixing_commit_diff
    )
    
    if is_valid_fix:
        print("[+] Verification confirms commit actions align with CASPER guidance. Promoting context weight.")
        db.update_resolution(record_id, row['resolution_summary'], row['confidence_score'], is_verified=True)
    else:
        print("[-] Commit changes strayed from initial suggestions. Retaining baseline weights.")

if __name__ == "__main__":
    # Validate environment declarations before execution loops start
    try:
        Config.validate()
    except ValueError as err:
        print(f"Configuration Error: {err}")
        sys.exit(1)
        
    # Standard DB execution initialization tasks
    db.init_db()
    
    print("====================================================")
    print("       CASPER POC EXECUTION ENGINE ACTIVATED        ")
    print("====================================================\n")
    
    # --- MANUAL TESTING VALUES FOR FIRST PROOF RUNS ---
    # Replace these mock string variables with actual internal testing resources to evaluate functional flows
    SAMPLE_PROJECT_ID = "101"
    SAMPLE_MR_IID = "12"
    SAMPLE_JOB_ID = "4509"
    SAMPLE_PIPELINE_ID = "2023"
    
    # Uncomment lines below once environmental target configurations match internal assets
    # rec_id = process_pipeline_failure(SAMPLE_PROJECT_ID, SAMPLE_MR_IID, SAMPLE_JOB_ID, SAMPLE_PIPELINE_ID)
    #
    # MOCK_FIXING_DIFF = "File: requirements.txt\nDiff:\n+ pyyaml==6.0.1\n- pyyaml==5.4.1"
    # verify_subsequent_fix(rec_id, MOCK_FIXING_DIFF)