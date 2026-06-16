import sys
from config import Config
import database as db
from gitlab_client import GitLabClient
import parser
from llm_client import LLMClient

def process_pipeline_failure(project_id: str, mr_iid: str, job_id: str, pipeline_id: str):
    print(f"[*] ECURGT Initializing analysis for Project {project_id}, Job {job_id}...")
    
    gl = GitLabClient()
    llm = LLMClient()
    
    print("[*] Retrieving failure traces and MR diff details...")
    # NOTE: Uncomment below to pull live GitLab data, using mocked data for POC standalone test.
    # raw_log = gl.get_job_log(project_id, job_id)
    # raw_changes = gl.get_mr_changes(project_id, mr_iid)
    
    raw_log = "Error: Cannot find module 'react-router-dom'\n    at Function.Module._resolveFilename (internal/modules/cjs/loader.js)\n    at exit code 1"
    raw_changes = [{"new_path": "package.json", "diff": "- \"react-router-dom\": \"^5.2.0\"\n+ \"react-router-dom\": \"^6.0.0\""}]
    
    parsed_log = parser.clean_and_parse_log(raw_log)
    diff_summary = parser.format_diff_summary(raw_changes)
    
    print("[*] Performing database lexical match query...")
    
    # [NEW: Deduplication Check - Check if this exact/similar error already exists]
    duplicate_id = db.check_for_duplicate(parsed_log)
    if duplicate_id:
        print(f"[+] Known Error Detected! Bumping occurrence count for tracking ID {duplicate_id} to inform prevention metrics.")
        db.increment_occurrence(duplicate_id)
        
        # We can exit early here to save LLM tokens, or optionally fetch the existing RCA and post it to GitLab
        print("[+] Processing halted: Duplicate context handled.")
        return duplicate_id

    # If it is a new error, get historical context (different errors but maybe conceptually similar)
    historical_matches = db.query_historical_context(parsed_log, limit=2)
    
    print("[*] Synthesizing context arrays inside model layers...")
    ai_response = llm.generate_rca_suggestion(parsed_log, diff_summary, historical_matches)
    
    # [CHANGED: Safely extracting all expected fields including the new MR type categorization]
    suggestion = ai_response.get("suggestion", "Unable to establish distinct automated RCA recommendation.")
    confidence = ai_response.get("confidence", 0)
    mr_type_desc = ai_response.get("mr_type_description", "Unknown File Changes")
    
    # Save the brand new error track to the database
    record_id = db.save_initial_failure(
        project_id, pipeline_id, job_id, parsed_log, diff_summary, 
        mr_type_desc, suggestion, confidence
    )
    
    comment_body = (
        f"### 🤖 ECURGT Automated Root Cause Analysis\n\n"
        f"**Change Type:** {mr_type_desc}\n"
        f"**Suggested Remediation:** {suggestion}\n\n"
        f"* **Confidence Score:** {confidence}%\n"
        f"*Note: This thread has been pre-resolved to minimize manual workflow clutter.*"
    )
    
    print("[*] Injecting analytical insight blocks into GitLab discussions...")
    # gl.post_mr_discussion(project_id, mr_iid, comment_body)
    print(f"\n[+] RCA processed successfully. Tracking Record Saved with ID: {record_id}\n")
    return record_id

def verify_subsequent_fix(record_id: int, fixing_commit_diff: str):
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
        print("[+] Verification confirms commit actions align with CASPER guidance.")
        db.update_resolution_verification(record_id, is_verified=True)
    else:
        print("[-] Commit changes strayed from initial suggestions.")

if __name__ == "__main__":
    try:
        Config.validate()
    except ValueError as err:
        print(f"Configuration Error: {err}")
        sys.exit(1)
        
    db.init_db()
    
    print("====================================================")
    print("       ECURGT POC EXECUTION ENGINE ACTIVATED        ")
    print("====================================================\n")
    
    SAMPLE_PROJECT_ID = "101"
    SAMPLE_MR_IID = "12"
    SAMPLE_JOB_ID = "4509"
    SAMPLE_PIPELINE_ID = "2023"
    
    print(">>> Executing Test Pipeline Failure #1 (New Error)")
    rec_id = process_pipeline_failure(SAMPLE_PROJECT_ID, SAMPLE_MR_IID, SAMPLE_JOB_ID, SAMPLE_PIPELINE_ID)
    
    print("\n>>> Executing Test Pipeline Failure #2 (Duplicate Error test)")
    # This should trigger the new deduplication / occurrence_count logic
    process_pipeline_failure(SAMPLE_PROJECT_ID, SAMPLE_MR_IID, SAMPLE_JOB_ID, SAMPLE_PIPELINE_ID)
