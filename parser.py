import re

def clean_and_parse_log(raw_log: str, tail_lines: int = 150) -> str:
    """Strips terminal color controls and slices out the trailing lines containing the trace."""
    if not raw_log:
        return ""
        
    # Standard Regex tracking down ANSI Escape Codes / Terminal Graphic Settings
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    clean_text = ansi_escape.sub('', raw_log)
    
    # Isolate lines, drop empty items, and return the tail end signature area
    lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
    log_tail = lines[-tail_lines:]
    
    return "\n".join(log_tail)

def format_diff_summary(changes: list) -> str:
    """Transforms raw complex JSON change payloads into structured text contexts."""
    summary_blocks = []
    for change in changes:
        filename = change.get("new_path") or change.get("old_path")
        diff_content = change.get("diff", "")
        # Filter down diff sizes to keep context sizes light
        truncated_diff = "\n".join(diff_content.splitlines()[:40]) 
        
        summary_blocks.append(f"File: {filename}\nDiff:\n{truncated_diff}\n")
        
    return "\n".join(summary_blocks)