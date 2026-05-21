import re
import json
import requests
from llm import call_llm
from schemas import CredentialInput

OLLAMA_HOST = "http://10.123.0.218:8080"
MODEL = "llama3.1:8b"

# -------------------------
# LLM CALL (local wrapper)
# -------------------------
def call_llm(prompt: str) -> str:
    response = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        }
    )
    return response.json()["response"]


# -------------------------
# SAFE JSON PARSER
# -------------------------
def safe_json_parse(text: str):
    try:
        return json.loads(text)
    except:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                return {}
    return {}


# -------------------------
# MAIN EXTRACTION FUNCTION
# -------------------------
def extract_credential(user_input: str) -> dict:
    prompt = f"""
You are a production-grade credential extraction engine for an internal security system.

Your job is to extract ALL access-related information from user messages and convert it into a STRICT JSON object.

────────────────────────────────────
RULES (MANDATORY)
────────────────────────────────────
1. Output ONLY valid JSON (no markdown, no explanation, no extra text)
2. Never guess missing values — use null
3. If multiple credentials exist, merge into ONE object (prioritize most complete)
4. Normalize names (e.g., "aws console" → "AWS")
5. Detect credential type accurately
6. If uncertain, set type = "secret"
7. Do NOT fabricate data

────────────────────────────────────
SUPPORTED TYPES
────────────────────────────────────
- website: web logins (AWS, Gmail, Jira, dashboards)
- server: SSH/RDP/VPS machines
- api: API keys / tokens / secrets
- database: DB access (Postgres, MySQL, MongoDB)
- cloud: AWS/GCP/Azure IAM credentials
- ssh_key: private key access
- vpn: VPN credentials
- internal_tool: company internal apps
- kubernetes: cluster access
- secret: fallback for unknown or mixed credentials

────────────────────────────────────
OUTPUT SCHEMA (STRICT)
────────────────────────────────────
Return EXACTLY this structure:

{{
  "type": "website | server | api | database | cloud | ssh_key | vpn | internal_tool | kubernetes | secret",
  "name": string or null,

  "host": string or null,
  "ip": string or null,
  "url": string or null,
  "port": number or null,

  "username": string or null,
  "password": string or null,

  "api_key": string or null,
  "secret_key": string or null,

  "db_name": string or null,
  "region": string or null,

  "notes": string or null
}}

────────────────────────────────────
DETECTION RULES
────────────────────────────────────

- If IP or port exists → likely "server" or "database"
- If URL exists → likely "website" or "api"
- If "ssh", "login to server", "ubuntu", "root" → server
- If "api key", "token", "bearer" → api
- If "aws", "gcp", "azure credentials" → cloud
- If "kubeconfig", "cluster", "kubectl" → kubernetes
- If "vpn" → vpn
- If "-----BEGIN PRIVATE KEY-----" → ssh_key

────────────────────────────────────
EXAMPLES
────────────────────────────────────

Input:
"I use AWS console https://aws.amazon.com username admin password 1234"

Output:
{{
  "type": "website",
  "name": "AWS",
  "url": "https://aws.amazon.com",
  "username": "admin",
  "password": "1234",
  "ip": null,
  "host": null,
  "port": null,
  "api_key": null,
  "secret_key": null,
  "db_name": null,
  "region": null,
  "notes": null
}}

---

Input:
"SSH into server 10.0.0.5 port 22 root password abc123"

Output:
{{
  "type": "server",
  "name": "Server 10.0.0.5",
  "ip": "10.0.0.5",
  "port": 22,
  "username": "root",
  "password": "abc123",
  "host": null,
  "url": null,
  "api_key": null,
  "secret_key": null,
  "db_name": null,
  "region": null,
  "notes": null
}}

---

Input:
"My Stripe API key is sk_test_123456"

Output:
{{
  "type": "api",
  "name": "Stripe",
  "api_key": "sk_test_123456",
  "secret_key": null,
  "username": null,
  "password": null,
  "notes": null
}}

────────────────────────────────────
USER INPUT:
{user_input}
"""

    response = call_llm(prompt)
    return safe_json_parse(response)


# -------------------------
# MISSING FIELD CHECK
# -------------------------
def missing_fields(data: dict):
    required_common = ["username", "password"]

    # type-specific requirements
    if data.get("type") == "website":
        required_common.append("name")

    if data.get("type") == "server":
        required_common.extend(["ip"])

    return [k for k in required_common if not data.get(k)]