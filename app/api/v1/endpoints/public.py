from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.repositories.service import service_repo
from app.repositories.faq import faq_repo
from app.repositories.testimonial import testimonial_repo
from app.repositories.portfolio import portfolio_repo
from app.schemas.service import ServiceOut
from app.schemas.faq import FAQOut
from app.schemas.testimonial import TestimonialOut
from app.schemas.portfolio import PortfolioOut

router = APIRouter()


@router.get("/services", response_model=List[ServiceOut])
def public_services(db: Session = Depends(get_db)):
    """
    Get all active services (Public - no auth required).
    """
    return service_repo.get_active(db)


@router.get("/faqs", response_model=List[FAQOut])
def public_faqs(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Get all FAQs ordered by order_index (Public - no auth required).
    """
    if category:
        return faq_repo.get_by_category(db, category=category)
    return faq_repo.get_all_ordered(db)


@router.get("/testimonials", response_model=List[TestimonialOut])
def public_testimonials(db: Session = Depends(get_db)):
    """
    Get all testimonials (Public - no auth required).
    """
    return testimonial_repo.get_multi(db)


@router.get("/portfolio", response_model=List[PortfolioOut])
def public_portfolio(db: Session = Depends(get_db)):
    """
    Get all portfolio items (Public - no auth required).
    """
    return portfolio_repo.get_multi(db)
