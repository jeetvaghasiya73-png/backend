from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    leads,
    contacts,
    blogs,
    portfolio,
    services,
    faqs,
    testimonials,
    seo,
    users,
    api_tokens,
    public,
    scraped_leads,
    email
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(leads.router, prefix="/leads", tags=["leads"])
api_router.include_router(contacts.router, prefix="/contacts", tags=["contacts"])
api_router.include_router(blogs.router, prefix="/blogs", tags=["blogs"])
api_router.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
api_router.include_router(services.router, prefix="/services", tags=["services"])
api_router.include_router(faqs.router, prefix="/faqs", tags=["faqs"])
api_router.include_router(testimonials.router, prefix="/testimonials", tags=["testimonials"])
api_router.include_router(seo.router, prefix="/seo", tags=["seo"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(api_tokens.router, prefix="/api-tokens", tags=["api_tokens"])
api_router.include_router(public.router, prefix="/public", tags=["public"])
api_router.include_router(scraped_leads.router, prefix="/scraped-leads", tags=["scraped_leads"])
api_router.include_router(email.router, prefix="/email", tags=["email"])

