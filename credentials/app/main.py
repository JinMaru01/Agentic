import uuid
import uvicorn

from llm import call_llm
from pydantic import BaseModel
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from services import extract_credential, missing_fields

app = FastAPI()

# simple in-memory session store (Phase 1 only)
DEV_KEY = "secret123"
SESSION = {}
DRAFTS = {}
SAVED_CREDENTIALS = []

class ChatRequest(BaseModel):
    user_id: str
    message: str

from fastapi.responses import HTMLResponse


@app.get("/", response_class=HTMLResponse)
def ui():
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Credential Agent Dashboard</title>

    <style>
        body {
            font-family: Arial;
            max-width: 1200px;
            margin: auto;
            padding: 20px;
            background: #f5f5f5;
        }

        h1 {
            color: #222;
        }

        .card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }

        input, button, select {
            padding: 10px;
            margin: 5px;
        }

        button {
            cursor: pointer;
        }

        pre {
            background: #111;
            color: #0f0;
            padding: 15px;
            overflow-x: auto;
            border-radius: 8px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
        }

        th, td {
            padding: 12px;
            border-bottom: 1px solid #ddd;
            text-align: left;
        }

        th {
            background: #222;
            color: white;
        }

        .password-mask {
            font-family: monospace;
            letter-spacing: 2px;
        }

        .toolbar {
            margin-bottom: 15px;
        }
    </style>
</head>
<body>

<h1>🧠 Credential Agent Dashboard</h1>

<div class="card">
    <h2>Add Credential</h2>

    <input id="userId" placeholder="User ID" value="u1" />

    <br>

    <input
        id="message"
        placeholder="Enter credential message"
        style="width: 70%"
    />

    <button onclick="sendChat()">Send</button>

    <h3>LLM Response</h3>
    <pre id="output"></pre>

    <div id="actions" style="display:none;">
        <p id="draftId"></p>

        <button onclick="confirmDraft('yes')">
            ✅ Confirm Save
        </button>

        <button onclick="confirmDraft('no')">
            ❌ Cancel
        </button>
    </div>
</div>

<div class="card">
    <h2>Stored Credentials</h2>

    <div class="toolbar">
        <button onclick="loadCredentials()">
            🔄 Refresh
        </button>

        <select id="filterType" onchange="filterCredentials()">
            <option value="all">All Types</option>
            <option value="website">Website</option>
            <option value="server">Server</option>
            <option value="api">API</option>
            <option value="database">Database</option>
            <option value="cloud">Cloud</option>
        </select>
    </div>

    <table>
        <thead>
            <tr>
                <th>Type</th>
                <th>Name</th>
                <th>Host/IP</th>
                <th>Username</th>
                <th>Password</th>
                <th>Port</th>
            </tr>
        </thead>

        <tbody id="credentialTable"></tbody>
    </table>
</div>

<script>
let currentDraft = null;
let allCredentials = [];

const API = "http://localhost:8000";

async function sendChat() {
    const userId = document.getElementById("userId").value;
    const message = document.getElementById("message").value;

    const res = await fetch(API + "/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            user_id: userId,
            message: message
        })
    });

    const data = await res.json();

    document.getElementById("output").innerText = JSON.stringify(data, null, 2);

    if (data.draft_id) {
        currentDraft = data.draft_id;

        document.getElementById("actions").style.display = "block";
        document.getElementById("draftId").innerText = "Draft ID: " + currentDraft;
    }
}

async function confirmDraft(action) {
    const res = await fetch(
        API + "/confirm?draft_id=" + currentDraft + "&action=" + action,
        {
            method: "POST"
        }
    );

    const data = await res.json();

    document.getElementById("output").innerText = JSON.stringify(data, null, 2);

    document.getElementById("actions").style.display = "none";

    currentDraft = null;

    await loadCredentials();
}

async function loadCredentials() {
    const res = await fetch(API + "/credentials");

    const data = await res.json();

    allCredentials = data.data || [];

    renderTable(allCredentials);
}

function renderTable(items) {
    const table = document.getElementById("credentialTable");

    table.innerHTML = "";

    for (const item of items) {
        const row = `
            <tr>
                <td>${item.type || '-'}</td>
                <td>${item.name || '-'}</td>
                <td>${item.ip || item.host || item.url || '-'}</td>
                <td>${item.username || '-'}</td>
                <td class="password-mask">
                    ${item.password ? '••••••••' : '-'}
                </td>
                <td>${item.port || '-'}</td>
            </tr>
        `;

        table.innerHTML += row;
    }
}

function filterCredentials() {
    const type = document.getElementById("filterType").value;

    if (type === "all") {
        renderTable(allCredentials);
        return;
    }

    const filtered = allCredentials.filter(x => x.type === type);

    renderTable(filtered);
}

loadCredentials();
</script>

</body>
</html>
"""


@app.post("/chat")
def chat(req: ChatRequest):
    user_id = req.user_id

    extracted = extract_credential(req.message)

    # DO NOT persist yet
    temp_state = extracted

    missing = missing_fields(temp_state)

    if missing:
        return {
            "status": "incomplete",
            "message": f"Please provide: {', '.join(missing)}"
        }

    draft_id = str(uuid.uuid4())

    DRAFTS[draft_id] = {
        "user_id": user_id,
        "data": temp_state
    }

    return {
        "status": "pending_confirmation",
        "draft_id": draft_id,
        "message": "Please confirm to save this credential.",
        "data": temp_state
    }


@app.post("/confirm")
def confirm(draft_id: str, action: str):
    draft = DRAFTS.get(draft_id)

    if not draft:
        return {
            "status": "error",
            "message": "Invalid draft_id"
        }

    if action.lower() == "no":
        del DRAFTS[draft_id]

        return {
            "status": "cancelled",
            "message": "Draft discarded"
        }

    if action.lower() != "yes":
        return {
            "status": "error",
            "message": "Invalid action"
        }

    data = draft["data"]

    # temporary storage
    SAVED_CREDENTIALS.append(data)

    del DRAFTS[draft_id]

    return {
        "status": "saved",
        "message": "Credential saved successfully",
        "data": data
    }


@app.get("/credentials")
def get_credentials():
    return {
        "count": len(SAVED_CREDENTIALS),
        "data": SAVED_CREDENTIALS
    }


@app.get("/debug/all")
def get_all_sessions(x_api_key: str = "secret123"):
    if x_api_key != DEV_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")

    return SESSION