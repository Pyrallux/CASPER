import requests
from config import Config

class GitLabClient:
    def __init__(self):
        self.headers = {"PRIVATE-TOKEN": Config.GITLAB_TOKEN}
        self.base_url = Config.GITLAB_URL

    def get_job_log(self, project_id: str, job_id: str) -> str:
        """Fetches the raw console output string from a specific pipeline runner execution trace."""
        url = f"{self.base_url}/api/v4/projects/{project_id}/jobs/{job_id}/trace"
        response = requests.get(url, headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.text

    def get_mr_changes(self, project_id: str, merge_request_iid: str) -> list:
        """Extracts files modified and actual raw diff contents for an active Merge Request."""
        url = f"{self.base_url}/api/v4/projects/{project_id}/merge_requests/{merge_request_iid}/changes"
        response = requests.get(url, headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.json().get("changes", [])

    def post_mr_discussion(self, project_id: str, merge_request_iid: str, body: str):
        """Creates an automatically resolved comment block directly on the target MR thread."""
        url = f"{self.base_url}/api/v4/projects/{project_id}/merge_requests/{merge_request_iid}/discussions"
        # Using native GitLab attributes to open a discussion thread that starts already marked resolved
        payload = {
            "body": body,
            "resolved": True
        }
        response = requests.post(url, headers=self.headers, json=payload, timeout=15)
        response.raise_for_status()
        return response.json()