from typing import List, Optional
from sqlalchemy.orm import Session
from backend.app.db.models.portfolio import Portfolio
from backend.app.models.portfolio import PortfolioCreate, PortfolioUpdate, PortfolioResponse
from fastapi import HTTPException, status


class PortfolioService:
    @staticmethod
    def get_all_portfolios(db: Session) -> List[PortfolioResponse]:
        try:
            portfolios = db.query(Portfolio).filter(Portfolio.is_active == True).all()
            return [PortfolioResponse.model_validate(portfolio) for portfolio in portfolios]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve portfolios: {str(e)}"
            )

    @staticmethod
    def get_portfolio_by_id(db: Session, id: int) -> PortfolioResponse:
        try:
            portfolio = db.query(Portfolio).filter(Portfolio.id == id, Portfolio.is_active == True).first()
            if not portfolio:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Portfolio with id {id} not found"
                )
            return PortfolioResponse.model_validate(portfolio)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve portfolio: {str(e)}"
            )

    @staticmethod
    def create_portfolio(db: Session, data: PortfolioCreate) -> PortfolioResponse:
        try:
            # Check if portfolio with same name already exists
            existing_portfolio = db.query(Portfolio).filter(
                Portfolio.name == data.name,
                Portfolio.is_active == True
            ).first()
            if existing_portfolio:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Portfolio with name '{data.name}' already exists"
                )
            
            # Create new portfolio
            portfolio = Portfolio(
                name=data.name,
                description=data.description,
                status=data.status or 'active',
                owner_id=data.owner_id
            )
            
            db.add(portfolio)
            db.commit()
            db.refresh(portfolio)
            
            return PortfolioResponse.model_validate(portfolio)
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create portfolio: {str(e)}"
            )

    @staticmethod
    def update_portfolio(db: Session, id: int, data: PortfolioUpdate) -> PortfolioResponse:
        try:
            # Check if portfolio exists
            portfolio = db.query(Portfolio).filter(Portfolio.id == id, Portfolio.is_active == True).first()
            if not portfolio:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Portfolio with id {id} not found"
                )
            
            # Check if another portfolio with same name already exists (excluding current one)
            existing_portfolio = db.query(Portfolio).filter(
                Portfolio.name == data.name,
                Portfolio.id != id,
                Portfolio.is_active == True
            ).first()
            if existing_portfolio:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Portfolio with name '{data.name}' already exists"
                )
            
            # Update portfolio fields
            portfolio.name = data.name
            portfolio.description = data.description
            portfolio.status = data.status or portfolio.status
            portfolio.owner_id = data.owner_id
            portfolio.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(portfolio)
            
            return PortfolioResponse.model_validate(portfolio)
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update portfolio: {str(e)}"
            )

    @staticmethod
    def delete_portfolio(db: Session, id: int) -> bool:
        try:
            # Check if portfolio exists
            portfolio = db.query(Portfolio).filter(Portfolio.id == id, Portfolio.is_active == True).first()
            if not portfolio:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Portfolio with id {id} not found"
                )
            
            # Mark as inactive instead of deleting
            portfolio.is_active = False
            portfolio.updated_at = datetime.utcnow()
            
            db.commit()
            
            return True
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete portfolio: {str(e)}"
            )

    @staticmethod
    def get_portfolio_by_name(db: Session, name: str) -> Optional[PortfolioResponse]:
        try:
            portfolio = db.query(Portfolio).filter(
                Portfolio.name == name,
                Portfolio.is_active == True
            ).first()
            if not portfolio:
                return None
            return PortfolioResponse.model_validate(portfolio)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve portfolio by name: {str(e)}"
            )
