import pytest
from httpx import AsyncClient

base_url = "http://localhost:8000"

@pytest.mark.anyio
async def test_full_chat_flow():
    async with AsyncClient(base_url=base_url, timeout=30.0) as ac:

        # -------------------------
        # STEP 1: send credential
        # -------------------------
        res = await ac.post("/chat", json={
            "user_id": "u1",
            "message": "aws login url https://aws.amazon.com username admin password 1234"
        })

        assert res.status_code == 200
        data = res.json()

        assert data["status"] == "pending_confirmation"
        assert "draft_id" in data

        draft_id = data["draft_id"]

        # -------------------------
        # STEP 2: confirm YES
        # -------------------------
        res2 = await ac.post("/confirm", params={
            "draft_id": draft_id,
            "action": "yes"
        })

        assert res2.status_code == 200
        data2 = res2.json()

        assert data2["status"] == "saved"


@pytest.mark.anyio
async def test_cancel_flow():
    async with AsyncClient(base_url=base_url, timeout=30.0) as ac:

        res = await ac.post("/chat", json={
            "user_id": "u2",
            "message": "github username dev password 1234 url https://github.com"
        })

        draft_id = res.json()["draft_id"]

        res2 = await ac.post("/confirm", params={
            "draft_id": draft_id,
            "action": "no"
        })

        assert res2.json()["status"] == "cancelled"


@pytest.mark.anyio
async def test_missing_fields():
    async with AsyncClient(base_url=base_url, timeout=30.0) as ac:

        res = await ac.post("/chat", json={
            "user_id": "u3",
            "message": "save aws login"
        })

        data = res.json()

        assert data["status"] == "incomplete"
        assert "username" in data["message"] or "password" in data["message"]