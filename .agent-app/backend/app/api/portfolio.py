from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from backend.app.services.portfolio import PortfolioService
from backend.app.auth.user_auth_handler import require_roles
from backend.app.models.portfolio import PortfolioCreate, PortfolioUpdate, PortfolioResponse

router = APIRouter()

# GET /portfolio - Get all portfolios
@router.get("/portfolio", response_model=List[PortfolioResponse], dependencies=[Depends(require_roles(["admin", "user"]))])
def get_all_portfolios():
    try:
        return PortfolioService.get_all_portfolios()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve portfolios: {str(e)}"
        )

# GET /portfolio/{id} - Get portfolio by ID
@router.get("/portfolio/{id}", response_model=PortfolioResponse, dependencies=[Depends(require_roles(["admin", "user"]))])
def get_portfolio_by_id(id: int):
    try:
        return PortfolioService.get_portfolio_by_id(id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve portfolio: {str(e)}"
        )

# POST /portfolio - Create a new portfolio
@router.post("/portfolio", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_roles(["admin", "user"]))])
def create_portfolio(data: PortfolioCreate):
    try:
        return PortfolioService.create_portfolio(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create portfolio: {str(e)}"
        )

# PUT /portfolio/{id} - Update an existing portfolio
@router.put("/portfolio/{id}", response_model=PortfolioResponse, dependencies=[Depends(require_roles(["admin", "user"]))])
def update_portfolio(id: int, data: PortfolioUpdate):
    try:
        return PortfolioService.update_portfolio(id, data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update portfolio: {str(e)}"
        )

# DELETE /portfolio/{id} - Delete a portfolio
@router.delete("/portfolio/{id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_roles(["admin", "user"]))])
def delete_portfolio(id: int):
    try:
        PortfolioService.delete_portfolio(id)
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete portfolio: {str(e)}"
        )