from openai import OpenAI
from config import Config
import json

class LLMClient:
    def __init__(self):
        # Configured to look strictly at internal gateways safely
        self.client = OpenAI(
            base_url=Config.INTERNAL_LLM_API_BASE,
            api_key=Config.INTERNAL_LLM_API_KEY
        )
        self.model = Config.LLM_MODEL_NAME

    def generate_rca_suggestion(self, current_log: str, current_diff: str, historical_context: list) -> dict:
        """Assembles context data blocks and prompts the model for standard analytical recommendations."""
        
        # Build history context block string
        history_str = ""
        for index, item in enumerate(historical_context):
            history_str += f"--- Historical Incident #{index+1} ---\n"
            history_str += f"Past Error:\n{item['error_signature']}\n"
            history_str += f"Past Solution Summary:\n{item['resolution_summary']}\n\n"

        system_prompt = (
            "You are CASPER, an automated CI/CD Root Cause Analysis agent.\n"
            "Analyze the pipeline failure log and current code changes. Use the provided historical examples if relevant.\n"
            "You must respond ONLY with a valid JSON object matching this structure:\n"
            "{\n"
            "  \"suggestion\": \"A strict, 2-sentence maximum remediation plan action item for human reviewers or future AI code review tools.\",\n"
            "  \"confidence\": 85\n"
            "}\n"
            "The confidence parameter must be an integer between 0 and 100 representing how well current variables map to past context or signature certainties."
        )

        user_content = (
            f"=== HISTORICAL ANALOGS FOR CONTEXT ===\n{history_str or 'No historic analogs match this signature.'}\n\n"
            f"=== CURRENT PIPELINE FAILURE SNIPPET ===\n{current_log}\n\n"
            f"=== CURRENT MERGE REQUEST FILE DIFFS ===\n{current_diff}\n"
        )

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

    def verify_resolution_delta(self, historical_error: str, casper_suggestion: str, fixing_commit_diff: str) -> bool:
        """Evaluates whether the physical code delta checked in by a user matches what CASPER prescribed."""
        system_prompt = (
            "You are a strict code verification system. Evaluate whether a developer's real code modifications "
            "align with or were guided by an AI's previous root cause recommendation.\n"
            "Respond with a single JSON structural object containing a single boolean flag:\n"
            "{\n"
            "  \"is_aligned\": true/false\n"
            "}"
        )

        user_content = (
            f"The original error signature was:\n{historical_error}\n\n"
            f"CASPER suggested resolution:\n{casper_suggestion}\n\n"
            f"The developer later committed this diff to fix the build:\n{fixing_commit_diff}\n"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        data = json.loads(response.choices[0].message.content)
        return bool(data.get("is_aligned", False))