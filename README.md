# ECURGT

## Setup

```env
GITLAB_TOKEN="your_gitlab_personal_access_token"
INTERNAL_LLM_API_BASE="https://your-internal-llm-gateway/v1"
INTERNAL_LLM_API_KEY="your-internal-api-key"
LLM_MODEL_NAME="your-approved-model-string"
```

```sh
docker-compose up --build
```

Project ECURGT (Context-Aware Secure Pipeline Error Resolver) is an automated Root Cause Analysis (RCA) tool built to accelerate the triage of failed enterprise GitLab CI/CD pipelines. Its core goal is to save developer time by instantly analyzing failed job traces and active Merge Request (MR) file diffs, returning actionable, two-sentence remediation steps and a confidence score directly as a resolved comment on the MR. Designed to navigate strict corporate security and AppSec constraints, the tool is built entirely on ubiquitous, vetted technologies (Python standard library, SQLite), operating asynchronously to ensure successful pipelines experience zero computational overhead.

Technically, ECURGT acts as a lightweight, memory-augmented agent interface. Upon a pipeline failure, it quickly strips out log noise (like ANSI codes) and isolates the error signature and relevant MR file changes. It then utilizes a local SQLite database with an FTS5 extension to perform lexical RAG (BM25 string matching). This instantly retrieves historically identical or similar pipeline errors and their verified code fixes. To track common pipeline health issues, the system also checks for exact duplicate errors, incrementing occurrence counts to inform preventative metrics rather than wasting LLM tokens on known issues.

For complex or novel failures, ECURGT packages the parsed log, diff summary, and historic analogs into a payload for an internal enterprise LLM to synthesize a root-cause suggestion and MR change categorization. Finally, ECURGT features a closed-loop learning mechanism: when a broken pipeline is ultimately fixed and passes, the system evaluates the fixing commit against its original suggestion to automatically verify accuracy and adjust future historical confidence scores. The current Dockerized POC includes a "Manual LLM Mode" that exports prompts to local text files, allowing the team to manually process inferences while awaiting corporate API access approvals.
