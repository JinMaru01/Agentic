import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_get_portfolio_requires_auth():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/ade/api/portfolio")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_get_portfolio_returns_200_when_authenticated(auth_client):
    response = await auth_client.get("/ade/api/portfolio")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total" in data
    assert "items" in data

@pytest.mark.asyncio
async def test_get_portfolio_by_id_returns_200_when_exists(auth_client):
    # Assume a portfolio with id=1 exists in test DB
    response = await auth_client.get("/ade/api/portfolio/1")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["data"]["id"] == 1

@pytest.mark.asyncio
async def test_get_portfolio_by_id_returns_404_when_not_exists(auth_client):
    response = await auth_client.get("/ade/api/portfolio/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Portfolio not found"

@pytest.mark.asyncio
async def test_post_portfolio_creates_new_portfolio(auth_client):
    payload = {
        "name": "Test Portfolio 1",
        "description": "A test portfolio created via API",
        "owner_id": 1
    }
    response = await auth_client.post("/ade/api/portfolio", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "data" in data
    assert data["data"]["name"] == "Test Portfolio 1"
    assert data["data"]["id"] > 0

@pytest.mark.asyncio
async def test_post_portfolio_fails_with_409_when_duplicate_name(auth_client):
    # Create a portfolio with same name first
    payload = {
        "name": "Duplicate Portfolio",
        "description": "Existing portfolio",
        "owner_id": 1
    }
    await auth_client.post("/ade/api/portfolio", json=payload)

    # Try to create another with same name
    response = await auth_client.post("/ade/api/portfolio", json={
        "name": "Duplicate Portfolio",
        "description": "Second attempt",
        "owner_id": 1
    })
    assert response.status_code == 409
    assert response.json()["detail"] == "Portfolio with this name already exists"

@pytest.mark.asyncio
async def test_post_portfolio_fails_with_400_when_invalid_data(auth_client):
    # Missing required fields
    response = await auth_client.post("/ade/api/portfolio", json={"name": ""})
    assert response.status_code == 400
    assert "name" in response.json()["detail"]

@pytest.mark.asyncio
async def test_put_portfolio_updates_existing(auth_client):
    # First create a portfolio
    create_response = await auth_client.post("/ade/api/portfolio", json={
        "name": "Update Test",
        "description": "To be updated",
        "owner_id": 1
    })
    created_id = create_response.json()["data"]["id"]

    # Now update it
    update_payload = {
        "name": "Updated Name",
        "description": "Updated description",
        "owner_id": 1
    }
    response = await auth_client.put(f"/ade/api/portfolio/{created_id}", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["name"] == "Updated Name"
    assert data["data"]["description"] == "Updated description"

@pytest.mark.asyncio
async def test_put_portfolio_fails_with_404_when_not_exists(auth_client):
    response = await auth_client.put("/ade/api/portfolio/999999", json={"name": "Update"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Portfolio not found"

@pytest.mark.asyncio
async def test_put_portfolio_fails_with_409_when_duplicate_name(auth_client):
    # Create first portfolio
    await auth_client.post("/ade/api/portfolio", json={
        "name": "Unique Name",
        "description": "First",
        "owner_id": 1
    })

    # Create second
    await auth_client.post("/ade/api/portfolio", json={
        "name": "Duplicate Name",
        "description": "Second",
        "owner_id": 1
    })

    # Try to update first to duplicate name
    response = await auth_client.put("/ade/api/portfolio/1", json={
        "name": "Duplicate Name",
        "description": "Updated",
        "owner_id": 1
    })
    assert response.status_code == 409
    assert response.json()["detail"] == "Portfolio with this name already exists"

@pytest.mark.asyncio
async def test_delete_portfolio_deletes_existing(auth_client):
    # Create a portfolio
    create_response = await auth_client.post("/ade/api/portfolio", json={
        "name": "Delete Me",
        "description": "To be deleted",
        "owner_id": 1
    })
    created_id = create_response.json()["data"]["id"]

    # Delete it
    response = await auth_client.delete(f"/ade/api/portfolio/{created_id}")
    assert response.status_code == 200
    assert response.json()["data"] == {"message": "Portfolio deleted successfully"}

@pytest.mark.asyncio
async def test_delete_portfolio_fails_with_404_when_not_exists(auth_client):
    response = await auth_client.delete("/ade/api/portfolio/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Portfolio not found"

@pytest.mark.asyncio
async def test_portfolio_endpoints_handle_internal_errors_500(auth_client, monkeypatch):
    # Simulate DB error
    async def mock_get_portfolio(*args, **kwargs):
        raise Exception("Database error")
    
    monkeypatch.setattr("app.api.routes.portfolio.get_portfolio", mock_get_portfolio)
    
    response = await auth_client.get("/ade/api/portfolio")
    assert response.status_code == 500
    assert "detail" in response.json()
    assert "Internal Server Error" in response.json()["detail"]

# Optional: Add test for role-based access if applicable
@pytest.mark.asyncio
async def test_get_portfolio_requires_admin_role(dept_auth_client):
    # Use a non-admin dept role
    response = await dept_auth_client.get("/ade/api/portfolio")
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"

# Optional: Test for invalid ID format
@pytest.mark.asyncio
async def test_get_portfolio_by_invalid_id_returns_400(auth_client):
    response = await auth_client.get("/ade/api/portfolio/abc")
    assert response.status_code == 400
    assert "detail" in response.json()
    assert "Invalid ID format" in response.json()["detail"]

# Optional: Test for PUT with invalid ID format
@pytest.mark.asyncio
async def test_put_portfolio_by_invalid_id_returns_400(auth_client):
    response = await auth_client.put("/ade/api/portfolio/abc", json={"name": "Test"})
    assert response.status_code == 400
    assert "detail" in response.json()
    assert "Invalid ID format" in response.json()["detail"]

# Optional: Test for DELETE with invalid ID format
@pytest.mark.asyncio
async def test_delete_portfolio_by_invalid_id_returns_400(auth_client):
    response = await auth_client.delete("/ade/api/portfolio/abc")
    assert response.status_code == 400
    assert "detail" in response.json()
    assert "Invalid ID format" in response.json()["detail"]
