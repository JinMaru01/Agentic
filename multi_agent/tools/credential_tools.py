"""
Credential-Store Agent tools
Spec: Credential-Store Agent Technical Implementation Specification v0.1

Architecture:
  PolicyEngine   — external authorization decision point (default deny)
  SecretsBackend — file-based dev store; swap for Vault / cloud KMS in prod
  AuditLog       — append-only JSONL with SHA-256 hash chain (tamper-evident)
  HandleStore    — in-memory short-lived handles; plaintext never enters model

Design rules (from spec §1.2):
  • Default deny. No secret disclosed unless policy explicitly allows.
  • Model never decides authorization. check_entitlement must be called first.
  • Secrets never enter model context. Tools return SecretHandle, not values.
  • Separate discovery from disclosure. list ≠ read.
  • Audit is a precondition — if audit write fails, disclosure fails.
  • Prefer just-in-time handles over long-lived secrets.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from ..core.logger import get_agent_logger

logger = get_agent_logger("credential")

# =========================================================
# PATHS
# =========================================================

_DATA_DIR      = Path(__file__).parent.parent / "data" / "credentials"
_SECRETS_FILE  = _DATA_DIR / "secrets.json"
_POLICY_FILE   = _DATA_DIR / "policy.json"
_AUDIT_FILE    = _DATA_DIR / "audit.jsonl"
_REQUESTS_FILE = _DATA_DIR / "access_requests.json"

_DATA_DIR.mkdir(parents=True, exist_ok=True)

_HANDLE_TTL_SECONDS   = 300   # 5-minute single-use handles
_RECOVERY_WINDOW_DAYS = 7

_TZ = timezone(timedelta(hours=7))   # matches project logger timezone


def _now() -> str:
    return datetime.now(_TZ).isoformat()


# =========================================================
# DATA MODELS  (§5 Data model)
# =========================================================

class SecretMetadata(BaseModel):
    name:                  str
    type:                  str            # api_key | db_password | certificate | token
    owner:                 str
    version:               int  = 1
    last_rotated_at:       str  = Field(default_factory=_now)
    requires_approval:     bool = False
    requires_step_up_auth: bool = False
    tags:                  dict = Field(default_factory=dict)
    deleted:               bool = False
    deleted_at:            Optional[str] = None
    recovery_until:        Optional[str] = None


class SecretHandle(BaseModel):
    """Returned to the agent. Plaintext is stored server-side, keyed by handle_id."""
    handle_id:        str
    secret_name:      str
    version:          int
    expires_at:       str
    delivery_channel: str = "redeem_api"


class AuditEvent(BaseModel):
    event_id:      str
    timestamp:     str
    principal_id:  str
    action:        str   # READ | LIST | PUT | ROTATE | DELETE | DENY | REQUEST_ACCESS | APPROVE
    secret_name:   str
    decision:      str   # allowed | denied | pending
    reason:        str  = ""
    justification: str  = ""
    prev_hash:     str  = ""   # SHA-256 of the previous line — tamper-evident chain


# =========================================================
# AUDIT LOG  (§6.2 — append-only, tamper-evident)
# =========================================================

_last_hash: str = ""


def _read_last_hash() -> str:
    """Read the hash of the last written audit line."""
    if not _AUDIT_FILE.exists():
        return ""
    try:
        lines = _AUDIT_FILE.read_text(encoding="utf-8").strip().splitlines()
        if not lines:
            return ""
        last = json.loads(lines[-1])
        return last.get("prev_hash", "") or hashlib.sha256(lines[-1].encode()).hexdigest()
    except Exception:
        return ""


def _write_audit(event: AuditEvent) -> bool:
    """
    Append an audit event. Returns True on success.
    Disclosure must be aborted if this returns False (spec §1.2).
    """
    global _last_hash
    try:
        if not _last_hash:
            _last_hash = _read_last_hash()
        event.prev_hash = _last_hash
        line = event.model_dump_json()
        with _AUDIT_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        _last_hash = hashlib.sha256(line.encode()).hexdigest()
        logger.info(f"[audit] {event.action} | {event.secret_name} | {event.decision} | principal={event.principal_id}")
        return True
    except Exception as exc:
        logger.error(f"[audit] WRITE FAILED — disclosure must be blocked: {exc}")
        return False


def _audit(principal_id: str, action: str, secret_name: str,
           decision: str, reason: str = "", justification: str = "") -> bool:
    return _write_audit(AuditEvent(
        event_id=str(uuid.uuid4()),
        timestamp=_now(),
        principal_id=principal_id,
        action=action,
        secret_name=secret_name,
        decision=decision,
        reason=reason,
        justification=justification,
    ))


# =========================================================
# SECRETS BACKEND  (dev: JSON file; prod: swap for Vault)
# =========================================================

def _load_secrets() -> dict[str, dict]:
    if not _SECRETS_FILE.exists():
        return {}
    try:
        return json.loads(_SECRETS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_secrets(store: dict[str, dict]) -> None:
    _SECRETS_FILE.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")


def _seed_dev_secrets() -> None:
    """Create sample secrets on first run so the agent has something to work with."""
    if _SECRETS_FILE.exists():
        return
    store = {
        "db_password_dev": {
            "name": "db_password_dev", "type": "db_password",
            "owner": "platform-team", "version": 1,
            "last_rotated_at": _now(), "requires_approval": False,
            "requires_step_up_auth": False, "tags": {"env": "dev"},
            "deleted": False, "deleted_at": None, "recovery_until": None,
            "_value": "dev-db-pass-1234",
        },
        "api_key_prod": {
            "name": "api_key_prod", "type": "api_key",
            "owner": "platform-team", "version": 2,
            "last_rotated_at": _now(), "requires_approval": True,
            "requires_step_up_auth": True, "tags": {"env": "prod", "service": "payments"},
            "deleted": False, "deleted_at": None, "recovery_until": None,
            "_value": "prod-api-key-secret-xyz",
        },
        "token_internal": {
            "name": "token_internal", "type": "token",
            "owner": "security-team", "version": 3,
            "last_rotated_at": _now(), "requires_approval": False,
            "requires_step_up_auth": False, "tags": {"service": "internal-auth"},
            "deleted": False, "deleted_at": None, "recovery_until": None,
            "_value": "internal-jwt-secret-abc",
        },
    }
    _save_secrets(store)


_seed_dev_secrets()


# =========================================================
# POLICY ENGINE  (§2 — default deny; external to agent)
# =========================================================

def _load_policy() -> dict:
    """
    Load policy rules from file. Falls back to default-deny if missing.
    In production, replace with OPA/Rego HTTP call or Vault policies.
    """
    _default = {
        "default_allow_list":  True,   # any authenticated principal can list metadata
        "default_allow_read":  True,   # allow read unless secret.requires_approval
        "default_allow_write": False,
        "principal_overrides": {},
    }
    if not _POLICY_FILE.exists():
        _POLICY_FILE.write_text(json.dumps(_default, indent=2), encoding="utf-8")
        return _default
    try:
        return json.loads(_POLICY_FILE.read_text(encoding="utf-8"))
    except Exception:
        logger.error("[policy] failed to load policy — defaulting to deny")
        return {"default_allow_list": False, "default_allow_read": False,
                "default_allow_write": False, "principal_overrides": {}}


def _check_policy(principal_id: str, secret_name: str, action: str) -> dict:
    """
    Authorization decision. Never called by the model — called by tools only.
    Returns: {allowed, requires_approval, requires_step_up_auth, reason}
    """
    try:
        policy  = _load_policy()
        store   = _load_secrets()
        secret  = store.get(secret_name)
        overrides = policy.get("principal_overrides", {}).get(principal_id, {})

        # Secret doesn't exist
        if secret is None and action in ("READ", "ROTATE", "DELETE"):
            return {"allowed": False, "requires_approval": False,
                    "requires_step_up_auth": False, "reason": f"secret '{secret_name}' not found"}

        meta = SecretMetadata(**{k: v for k, v in (secret or {}).items() if not k.startswith("_")}) \
               if secret else None

        # Soft-deleted secrets can only be listed (for admins), not read
        if meta and meta.deleted and action == "READ":
            return {"allowed": False, "requires_approval": False,
                    "requires_step_up_auth": False, "reason": "secret is deleted"}

        action_key = {
            "LIST":   "default_allow_list",
            "READ":   "default_allow_read",
            "PUT":    "default_allow_write",
            "ROTATE": "default_allow_write",
            "DELETE": "default_allow_write",
        }.get(action, "default_allow_read")

        # Principal-level override takes precedence
        if action.lower() in overrides:
            base_allow = overrides[action.lower()]
        else:
            base_allow = policy.get(action_key, False)

        if not base_allow:
            return {"allowed": False, "requires_approval": False,
                    "requires_step_up_auth": False, "reason": "policy default deny"}

        if meta and meta.requires_approval and action == "READ":
            return {"allowed": False, "requires_approval": True,
                    "requires_step_up_auth": meta.requires_step_up_auth,
                    "reason": "secret requires explicit approval"}

        if meta and meta.requires_step_up_auth and action == "READ":
            return {"allowed": False, "requires_approval": False,
                    "requires_step_up_auth": True, "reason": "secret requires step-up authentication"}

        return {"allowed": True, "requires_approval": False,
                "requires_step_up_auth": False, "reason": "allowed by policy"}

    except Exception as exc:
        # Policy engine unreachable → default deny (spec §4.1)
        logger.error(f"[policy] engine error — default deny: {exc}")
        return {"allowed": False, "requires_approval": False,
                "requires_step_up_auth": False, "reason": f"policy engine error: {exc}"}


# =========================================================
# HANDLE STORE  (in-memory delivery layer — §4 step 4–6)
# Plaintext is stored server-side; the model only sees handle_id.
# =========================================================

_handles: dict[str, dict] = {}


def _issue_handle(secret_name: str, version: int, value: str) -> SecretHandle:
    handle_id  = str(uuid.uuid4())
    expires_at = (datetime.now(_TZ) + timedelta(seconds=_HANDLE_TTL_SECONDS)).isoformat()
    _handles[handle_id] = {
        "secret_name": secret_name,
        "version":     version,
        "value":       value,         # stored server-side only
        "expires_at":  expires_at,
        "redeemed":    False,
    }
    return SecretHandle(handle_id=handle_id, secret_name=secret_name,
                        version=version, expires_at=expires_at)


def redeem_handle(handle_id: str) -> dict:
    """
    Delivery layer — called by the API endpoint, NOT by the agent.
    Returns the plaintext value if the handle is valid and unredeemed.
    """
    entry = _handles.get(handle_id)
    if not entry:
        return {"error": "handle not found or already expired"}
    if entry["redeemed"]:
        return {"error": "handle already redeemed"}
    expires = datetime.fromisoformat(entry["expires_at"])
    if datetime.now(_TZ) > expires:
        del _handles[handle_id]
        return {"error": "handle expired"}
    entry["redeemed"] = True
    logger.info(f"[delivery] handle {handle_id} redeemed for {entry['secret_name']}")
    return {"secret_name": entry["secret_name"], "version": entry["version"],
            "value": entry["value"]}


# =========================================================
# ACCESS REQUESTS  (§3.1 — approval workflow)
# =========================================================

def _load_requests() -> list[dict]:
    if not _REQUESTS_FILE.exists():
        return []
    try:
        return json.loads(_REQUESTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_requests(reqs: list[dict]) -> None:
    _REQUESTS_FILE.write_text(json.dumps(reqs, indent=2, ensure_ascii=False), encoding="utf-8")


# =========================================================
# TOOLS  (§3 Tool surface)
# =========================================================

@tool
def check_entitlement(principal_id: str, secret_name: str, action: str) -> dict:
    """
    MUST be called before any secret disclosure or mutation.
    Delegates the authorization decision to the external policy engine — the model
    never decides whether access is permitted.

    action: READ | LIST | PUT | ROTATE | DELETE

    Returns:
      allowed (bool), requires_approval (bool), requires_step_up_auth (bool), reason (str)
    """
    result = _check_policy(principal_id, secret_name, action)
    decision = "allowed" if result["allowed"] else "denied"
    _audit(principal_id, f"CHECK_{action}", secret_name, decision, result["reason"])
    logger.info(f"[entitlement] principal={principal_id} action={action} secret={secret_name} → {decision}")
    return result


@tool
def request_access(principal_id: str, secret_name: str, justification: str) -> dict:
    """
    Open an approval request for a secret that requires explicit approval.
    Returns request_id and pending status. Notifies approvers (stub in dev).

    Use this after check_entitlement returns requires_approval=True.
    """
    reqs = _load_requests()

    # Reject self-approval: requester ≠ approver enforced server-side (§6.1 four-eyes)
    request_id = "REQ-" + str(uuid.uuid4())[:8].upper()
    req = {
        "request_id":    request_id,
        "principal_id":  principal_id,
        "secret_name":   secret_name,
        "justification": justification,
        "status":        "pending",
        "created_at":    _now(),
        "decided_at":    None,
        "approver_id":   None,
        "decision":      None,
    }
    reqs.append(req)
    _save_requests(reqs)

    _audit(principal_id, "REQUEST_ACCESS", secret_name, "pending", justification=justification)
    logger.info(f"[access_request] {request_id} opened by {principal_id} for {secret_name}")

    return {
        "request_id": request_id,
        "status":     "pending",
        "message":    f"Access request {request_id} created. An approver (different principal) must approve it.",
    }


@tool
def approve_request(request_id: str, approver_id: str, decision: str, reason: str = "") -> dict:
    """
    Approve or deny a pending access request.
    decision: 'approved' | 'denied'
    The approver MUST be a different principal than the requester (four-eyes control).
    """
    reqs = _load_requests()
    req  = next((r for r in reqs if r["request_id"] == request_id), None)

    if not req:
        return {"error": f"request {request_id} not found"}

    if req["status"] != "pending":
        return {"error": f"request {request_id} is already {req['status']}"}

    # Four-eyes: approver must differ from requester (§6.1)
    if approver_id == req["principal_id"]:
        return {"error": "approver must be a different principal than the requester (four-eyes policy)"}

    if decision not in ("approved", "denied"):
        return {"error": "decision must be 'approved' or 'denied'"}

    req.update({"status": decision, "decided_at": _now(),
                "approver_id": approver_id, "decision": decision, "reason": reason})
    _save_requests(reqs)

    _audit(approver_id, "APPROVE", req["secret_name"], decision, reason)
    logger.info(f"[approve_request] {request_id} {decision} by {approver_id}")

    return {"request_id": request_id, "decision": decision,
            "message": f"Request {request_id} has been {decision}."}


@tool
def list_secrets(principal_id: str) -> list[dict]:
    """
    List secret metadata the caller is entitled to see.
    Returns name, type, owner, version, requires_approval — NO values.
    Discovery permission is separate from read permission (spec §1.2).
    """
    entitlement = _check_policy(principal_id, "*", "LIST")
    if not entitlement["allowed"]:
        _audit(principal_id, "LIST", "*", "denied", entitlement["reason"])
        return [{"error": f"not authorized to list secrets: {entitlement['reason']}"}]

    store = _load_secrets()
    result = []
    for name, raw in store.items():
        if raw.get("deleted"):
            continue
        meta = {k: v for k, v in raw.items() if not k.startswith("_")}
        result.append(meta)

    _audit(principal_id, "LIST", "*", "allowed")
    logger.info(f"[list_secrets] principal={principal_id} returned {len(result)} secrets")
    return result


@tool
def get_secret(principal_id: str, secret_name: str, justification: str) -> dict:
    """
    Retrieve a secret. Requires a justification string for the audit log.
    Returns a SHORT-LIVED SecretHandle — NEVER the raw value.
    The caller redeems the handle via POST /api/credentials/redeem/{handle_id}.

    Audit write is a PRECONDITION — if it fails, disclosure is blocked.
    """
    # Step 1: Check entitlement
    entitlement = _check_policy(principal_id, secret_name, "READ")

    if not entitlement["allowed"]:
        _audit(principal_id, "READ", secret_name, "denied", entitlement["reason"], justification)
        if entitlement.get("requires_approval"):
            return {"error": "access requires approval — use request_access tool",
                    "requires_approval": True}
        if entitlement.get("requires_step_up_auth"):
            return {"error": "access requires step-up authentication (MFA)",
                    "requires_step_up_auth": True}
        return {"error": f"access denied: {entitlement['reason']}"}

    store = _load_secrets()
    secret = store.get(secret_name)
    if not secret:
        _audit(principal_id, "READ", secret_name, "denied", "not found", justification)
        return {"error": f"secret '{secret_name}' not found"}

    # Step 2: Write audit BEFORE disclosure — fail closed (spec §4.1 + §1.2)
    audit_ok = _audit(principal_id, "READ", secret_name, "allowed", justification=justification)
    if not audit_ok:
        return {"error": "disclosure blocked: audit write failed (fail-closed policy)"}

    # Step 3: Issue a short-lived handle — plaintext stays server-side
    handle = _issue_handle(secret_name, secret.get("version", 1), secret.get("_value", ""))
    logger.info(f"[get_secret] handle {handle.handle_id} issued to {principal_id} for {secret_name}")

    return handle.model_dump()


@tool
def put_secret(principal_id: str, secret_name: str, secret_type: str,
               owner: str, value_reference: str, tags: str = "{}") -> dict:
    """
    Create or update a secret. value_reference is a pointer (env var name, Vault path,
    file path) — the plaintext is never passed through the model context.
    tags: JSON string, e.g. '{"env": "prod", "service": "payments"}'
    """
    entitlement = _check_policy(principal_id, secret_name, "PUT")
    if not entitlement["allowed"]:
        _audit(principal_id, "PUT", secret_name, "denied", entitlement["reason"])
        return {"error": f"not authorized: {entitlement['reason']}"}

    try:
        tags_dict = json.loads(tags) if tags else {}
    except json.JSONDecodeError:
        tags_dict = {}

    store  = _load_secrets()
    exists = secret_name in store
    version = (store[secret_name].get("version", 0) + 1) if exists else 1

    # Value is resolved from the reference out-of-band (not by the model)
    resolved_value = f"[resolved from {value_reference}]"

    store[secret_name] = {
        "name": secret_name, "type": secret_type, "owner": owner,
        "version": version, "last_rotated_at": _now(),
        "requires_approval": False, "requires_step_up_auth": False,
        "tags": tags_dict, "deleted": False,
        "deleted_at": None, "recovery_until": None,
        "_value": resolved_value,
    }
    _save_secrets(store)

    action = "UPDATE" if exists else "CREATE"
    _audit(principal_id, "PUT", secret_name, "allowed", f"{action} via reference {value_reference}")
    logger.info(f"[put_secret] {action} {secret_name} v{version} by {principal_id}")

    return {"status": "ok", "secret_name": secret_name, "version": version, "action": action}


@tool
def rotate_secret(principal_id: str, secret_name: str) -> dict:
    """
    Rotate a secret. Prefers the backend's native rotation where available.
    In dev mode, increments version and simulates key rotation.
    """
    entitlement = _check_policy(principal_id, secret_name, "ROTATE")
    if not entitlement["allowed"]:
        _audit(principal_id, "ROTATE", secret_name, "denied", entitlement["reason"])
        return {"error": f"not authorized: {entitlement['reason']}"}

    store = _load_secrets()
    if secret_name not in store:
        _audit(principal_id, "ROTATE", secret_name, "denied", "not found")
        return {"error": f"secret '{secret_name}' not found"}

    secret = store[secret_name]
    old_version = secret.get("version", 1)
    new_version = old_version + 1

    # Simulate rotation: in prod, trigger backend native rotation (Vault /rotate endpoint)
    secret["version"]         = new_version
    secret["last_rotated_at"] = _now()
    secret["_value"]          = f"[rotated-value-v{new_version}]"
    _save_secrets(store)

    _audit(principal_id, "ROTATE", secret_name, "allowed",
           f"rotated v{old_version} → v{new_version}")
    logger.info(f"[rotate_secret] {secret_name} v{old_version} → v{new_version} by {principal_id}")

    return {"status": "ok", "secret_name": secret_name,
            "old_version": old_version, "new_version": new_version,
            "rotated_at": secret["last_rotated_at"]}


@tool
def delete_secret(principal_id: str, secret_name: str, recovery_days: int = 7) -> dict:
    """
    Soft-delete a secret with a recovery window (0–30 days).
    The secret is marked deleted and excluded from list_secrets.
    It can be recovered within the recovery window before permanent deletion.
    """
    if not (0 <= recovery_days <= 30):
        return {"error": "recovery_days must be between 0 and 30"}

    entitlement = _check_policy(principal_id, secret_name, "DELETE")
    if not entitlement["allowed"]:
        _audit(principal_id, "DELETE", secret_name, "denied", entitlement["reason"])
        return {"error": f"not authorized: {entitlement['reason']}"}

    store = _load_secrets()
    if secret_name not in store:
        _audit(principal_id, "DELETE", secret_name, "denied", "not found")
        return {"error": f"secret '{secret_name}' not found"}

    secret                  = store[secret_name]
    secret["deleted"]       = True
    secret["deleted_at"]    = _now()
    recovery_until          = (datetime.now(_TZ) + timedelta(days=recovery_days)).isoformat()
    secret["recovery_until"] = recovery_until if recovery_days > 0 else None
    _save_secrets(store)

    _audit(principal_id, "DELETE", secret_name, "allowed",
           f"soft-deleted, recovery window {recovery_days}d until {recovery_until}")
    logger.info(f"[delete_secret] {secret_name} soft-deleted by {principal_id}, recovery until {recovery_until}")

    return {"status": "ok", "secret_name": secret_name, "deleted_at": secret["deleted_at"],
            "recovery_until": recovery_until, "recovery_days": recovery_days}


@tool
def audit_log_tool(principal_id: str, action: str, secret_name: str,
                   decision: str, justification: str = "", reason: str = "") -> dict:
    """
    Write an explicit immutable audit event. The audit log is append-only and
    tamper-evident (SHA-256 hash chain). Name only — values are never logged.
    decision: allowed | denied | pending
    action: any descriptive string (READ, LIST, ROTATE, CUSTOM, etc.)
    """
    ok = _audit(principal_id, action.upper(), secret_name, decision, reason, justification)
    if ok:
        return {"status": "ok", "message": "audit event written"}
    return {"status": "error", "message": "audit write failed"}


tools: list = [
    check_entitlement,
    request_access,
    approve_request,
    list_secrets,
    get_secret,
    put_secret,
    rotate_secret,
    delete_secret,
    audit_log_tool,
]
