from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_admin_user, get_current_user_from_api_token
from app.repositories.portfolio import portfolio_repo
from app.services.portfolio import portfolio_service
from app.schemas.portfolio import PortfolioCreate, PortfolioUpdate, PortfolioOut

router = APIRouter()

@router.post("/", response_model=PortfolioOut, status_code=status.HTTP_201_CREATED)
def create_portfolio_item(
    portfolio_in: PortfolioCreate,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Create a new portfolio item (Admin only).
    """
    return portfolio_service.create_portfolio(db, portfolio_in=portfolio_in)

@router.get("/", response_model=List[PortfolioOut])
def read_portfolios(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_from_api_token)
):
    """
    Get all portfolio items (Protected).
    """
    return portfolio_repo.get_multi(db, skip=skip, limit=limit)

@router.get("/featured", response_model=List[PortfolioOut])
def read_featured_portfolio_items(
    db: Session = Depends(get_db)
):
    """
    Get only featured portfolio items (Public endpoint).
    """
    return portfolio_repo.get_featured(db)

@router.get("/{slug}", response_model=PortfolioOut)
def read_portfolio_by_slug(
    slug: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_from_api_token)
):
    """
    Get a single portfolio item by slug (Protected).
    """
    portfolio = portfolio_repo.get_by_slug(db, slug=slug)
    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio item not found"
        )
    return portfolio

@router.put("/{portfolio_id}", response_model=PortfolioOut)
def update_portfolio_item(
    portfolio_id: int,
    portfolio_in: PortfolioUpdate,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Update a portfolio item (Admin only).
    """
    portfolio = portfolio_repo.get(db, id=portfolio_id)
    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio item not found"
        )
    return portfolio_service.update_portfolio(db, db_obj=portfolio, portfolio_in=portfolio_in)

@router.delete("/{portfolio_id}", response_model=PortfolioOut)
def delete_portfolio_item(
    portfolio_id: int,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Delete a portfolio item (Admin only).
    """
    portfolio = portfolio_repo.get(db, id=portfolio_id)
    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio item not found"
        )
    return portfolio_repo.remove(db, id=portfolio_id)
