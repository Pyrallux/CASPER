from openai import OpenAI
from config import Config
import json
import os
import time

class LLMClient:
    def __init__(self):
        if not Config.MANUAL_LLM_MODE:
            self.client = OpenAI(
                base_url=Config.INTERNAL_LLM_API_BASE,
                api_key=Config.INTERNAL_LLM_API_KEY
            )
        self.model = Config.LLM_MODEL_NAME

    # [NEW: Core helper to intercept and export LLM prompts for manual execution]
    def _execute_prompt(self, task_name: str, system_prompt: str, user_content: str) -> dict:
        if Config.MANUAL_LLM_MODE:
            os.makedirs(Config.PROMPT_EXPORT_DIR, exist_ok=True)
            filename = f"prompt_{task_name}_{int(time.time())}.txt"
            filepath = os.path.join(Config.PROMPT_EXPORT_DIR, filename)
            
            with open(filepath, "w") as f:
                f.write("--- SYSTEM PROMPT ---\n")
                f.write(system_prompt + "\n\n")
                f.write("--- USER CONTENT ---\n")
                f.write(user_content + "\n")
                
            print(f"\n[!] MANUAL LLM MODE TRIGGERED")
            print(f"[!] The prompt has been exported to: {filepath}")
            print(f"[!] Please copy the contents of that file, submit it to your approved LLM interface, and paste the resulting JSON below.")
            print("[!] Type 'EOF' on a new line and press Enter when finished pasting.\n")
            
            lines = []
            while True:
                try:
                    line = input()
                    if line.strip() == "EOF":
                        break
                    lines.append(line)
                except EOFError:
                    break
                    
            try:
                return json.loads("\n".join(lines))
            except json.JSONDecodeError:
                print("[-] Failed to parse JSON. Returning empty fallback.")
                return {}
        else:
            # Automated API Execution
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)

    def generate_rca_suggestion(self, current_log: str, current_diff: str, historical_context: list) -> dict:
        history_str = ""
        for index, item in enumerate(historical_context):
            history_str += f"--- Historical Incident #{index+1} ---\n"
            history_str += f"Past Error:\n{item['error_signature']}\n"
            history_str += f"Past Solution Summary:\n{item['resolution_summary']}\n\n"

        # [CHANGED: Updated the system prompt to mandate the mr_type_description parameter]
        system_prompt = (
            "You are CASPER, an automated CI/CD Root Cause Analysis agent.\n"
            "Analyze the pipeline failure log and current code changes. Use the provided historical examples if relevant.\n"
            "You must respond ONLY with a valid JSON object matching this structure:\n"
            "{\n"
            "  \"suggestion\": \"A strict, 2-sentence maximum remediation plan action item.\",\n"
            "  \"mr_type_description\": \"A 3-5 word categorization of the file diffs (e.g., 'Python Dependency Update', 'Frontend UI Component').\",\n"
            "  \"confidence\": 85\n"
            "}\n"
            "The confidence parameter must be an integer between 0 and 100."
        )

        user_content = (
            f"=== HISTORICAL ANALOGS FOR CONTEXT ===\n{history_str or 'No historic analogs match this signature.'}\n\n"
            f"=== CURRENT PIPELINE FAILURE SNIPPET ===\n{current_log}\n\n"
            f"=== CURRENT MERGE REQUEST FILE DIFFS ===\n{current_diff}\n"
        )

        return self._execute_prompt("rca_generation", system_prompt, user_content)

    def verify_resolution_delta(self, historical_error: str, casper_suggestion: str, fixing_commit_diff: str) -> bool:
        system_prompt = (
            "You are a strict code verification system. Evaluate whether a developer's real code modifications "
            "align with or were guided by an AI's previous root cause recommendation.\n"
            "Respond with a single JSON structural object containing a single boolean flag:\n"
            "{\n"
            "  \"is_aligned\": true\n"
            "}"
        )

        user_content = (
            f"The original error signature was:\n{historical_error}\n\n"
            f"CASPER suggested resolution:\n{casper_suggestion}\n\n"
            f"The developer later committed this diff to fix the build:\n{fixing_commit_diff}\n"
        )

        data = self._execute_prompt("fix_verification", system_prompt, user_content)
        return bool(data.get("is_aligned", False))
