from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import engine, SessionLocal, Base
from app.models.base import Base as _  # Force import of all models
from app.routers.api import api_router

# Auto-create tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ── Middleware stack (order matters: outermost first) ───────────────────────

# 1. CORS — must be outermost so preflight OPTIONS are handled immediately
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. GZip compression — reduces payload sizes for large JSON responses
app.add_middleware(GZipMiddleware, minimum_size=500)

# 3. Login rate-limiting — pure ASGI middleware (no BaseHTTPMiddleware)
from app.middleware.rate_limit import LoginRateLimitMiddleware
app.add_middleware(LoginRateLimitMiddleware)

# 4. API token usage tracking — pure ASGI middleware (no BaseHTTPMiddleware)
from app.middleware.token_usage import TokenUsageMiddleware
app.add_middleware(TokenUsageMiddleware)

# ── Global exception handler ──────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all so unhandled exceptions return clean JSON instead of
    letting the server hang or return HTML tracebacks."""
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

# ── Routes ─────────────────────────────────────────────────────────────────

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def read_root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}!"}

# ── Startup seeding logic ─────────────────────────────────────────────────

@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    try:
        # Automatic migration checks for scraped_leads and campaigns
        from sqlalchemy import text, inspect
        inspector = inspect(db.bind)
        
        # Check and migrate scraped_leads columns
        if "scraped_leads" in inspector.get_table_names():
            columns = [col["name"] for col in inspector.get_columns("scraped_leads")]
            if "email_status" not in columns:
                db.execute(text("ALTER TABLE scraped_leads ADD COLUMN email_status VARCHAR(50) DEFAULT 'pending'"))
                db.commit()
                print("Migration: Added email_status column to scraped_leads")
            if "email_sent_at" not in columns:
                db.execute(text("ALTER TABLE scraped_leads ADD COLUMN email_sent_at DATETIME NULL"))
                db.commit()
                print("Migration: Added email_sent_at column to scraped_leads")
            if "email_error" not in columns:
                db.execute(text("ALTER TABLE scraped_leads ADD COLUMN email_error TEXT NULL"))
                db.commit()
                print("Migration: Added email_error column to scraped_leads")
            if "email_subject" not in columns:
                db.execute(text("ALTER TABLE scraped_leads ADD COLUMN email_subject VARCHAR(255) NULL"))
                db.commit()
                print("Migration: Added email_subject column to scraped_leads")
            if "email_body" not in columns:
                db.execute(text("ALTER TABLE scraped_leads ADD COLUMN email_body TEXT NULL"))
                db.commit()
                print("Migration: Added email_body column to scraped_leads")
            if "personalization_status" not in columns:
                db.execute(text("ALTER TABLE scraped_leads ADD COLUMN personalization_status VARCHAR(50) DEFAULT 'pending'"))
                db.commit()
                print("Migration: Added personalization_status column to scraped_leads")
            if "last_email_at" not in columns:
                db.execute(text("ALTER TABLE scraped_leads ADD COLUMN last_email_at DATETIME NULL"))
                db.commit()
                print("Migration: Added last_email_at column to scraped_leads")
            if "next_followup_at" not in columns:
                db.execute(text("ALTER TABLE scraped_leads ADD COLUMN next_followup_at DATETIME NULL"))
                db.commit()
                print("Migration: Added next_followup_at column to scraped_leads")
            if "followup_count" not in columns:
                db.execute(text("ALTER TABLE scraped_leads ADD COLUMN followup_count INTEGER DEFAULT 0"))
                db.commit()
                print("Migration: Added followup_count column to scraped_leads")
            if "reply_status" not in columns:
                db.execute(text("ALTER TABLE scraped_leads ADD COLUMN reply_status VARCHAR(50) DEFAULT 'unprocessed'"))
                db.commit()
                print("Migration: Added reply_status column to scraped_leads")
            if "unsubscribe" not in columns:
                db.execute(text("ALTER TABLE scraped_leads ADD COLUMN unsubscribe BOOLEAN DEFAULT FALSE"))
                db.commit()
                print("Migration: Added unsubscribe column to scraped_leads")
            if "bounced" not in columns:
                db.execute(text("ALTER TABLE scraped_leads ADD COLUMN bounced BOOLEAN DEFAULT FALSE"))
                db.commit()
                print("Migration: Added bounced column to scraped_leads")
            if "campaign_id" not in columns:
                db.execute(text("ALTER TABLE scraped_leads ADD COLUMN campaign_id INTEGER NULL REFERENCES campaigns(id) ON DELETE SET NULL"))
                db.commit()
                print("Migration: Added campaign_id column to scraped_leads")

        # Automatic migration checks for campaigns table
        if "campaigns" in inspector.get_table_names():
            campaign_columns = [col["name"] for col in inspector.get_columns("campaigns")]
            if "target_city" not in campaign_columns:
                db.execute(text("ALTER TABLE campaigns ADD COLUMN target_city VARCHAR(100) NULL"))
                db.commit()
                print("Migration: Added target_city column to campaigns")
            if "target_service" not in campaign_columns:
                db.execute(text("ALTER TABLE campaigns ADD COLUMN target_service VARCHAR(100) NULL"))
                db.commit()
                print("Migration: Added target_service column to campaigns")

        seed_admin_user(db)
        seed_services(db)
        seed_faqs(db)
        seed_testimonials(db)
        seed_seo_settings(db)
        
        # Start the background email worker
        from app.services.email_worker import email_worker
        email_worker.start()
    finally:
        db.close()

@app.on_event("shutdown")
def shutdown_event():
    from app.services.email_worker import email_worker
    email_worker.stop()

def seed_admin_user(db: Session):
    from app.repositories.user import user_repo
    from app.core.security import get_password_hash
    
    admin = user_repo.get_by_username(db, username=settings.ADMIN_USERNAME)
    if not admin:
        hashed_password = get_password_hash(settings.ADMIN_PASSWORD)
        user_repo.create(db, obj_in={
            "username": settings.ADMIN_USERNAME,
            "hashed_password": hashed_password,
            "is_active": True,
            "is_admin": True,
            "is_superadmin": True
        })
        print(f"Default super admin user created: {settings.ADMIN_USERNAME}")

def seed_services(db: Session):
    from app.repositories.service import service_repo
    
    if len(service_repo.get_multi(db)) == 0:
        services_data = [
            {
                "title": "AI Agents",
                "slug": "ai-agents",
                "description": "Custom autonomous AI agents trained on company datasets to execute workflows, resolve tickets, and operate autonomously.",
                "icon": "Cpu",
                "features": ["Autonomous Task Execution", "Custom Knowledgebase Integrations", "Multi-Agent System Orchestration", "24/7 Operations"],
                "active": True
            },
            {
                "title": "AI Automation",
                "slug": "ai-automation",
                "description": "End-to-end integration of LLMs and logic engines to automate repetitive email, billing, and notification workflows.",
                "icon": "Workflow",
                "features": ["Zero-touch operations", "LLM-driven decision paths", "System-to-system mapping", "Error self-healing"],
                "active": True
            },
            {
                "title": "SaaS Development",
                "slug": "saas-development",
                "description": "Full-stack cloud-native software built with modern frontends, robust APIs, and multi-tenant logic.",
                "icon": "Layers",
                "features": ["React/Next.js dynamic views", "FastAPI modular APIs", "Secure stripe subscriptions", "Scale-ready Docker setups"],
                "active": True
            },
            {
                "title": "Web Scraping & APIs",
                "slug": "web-scraping-and-apis",
                "description": "Enterprise-grade scraping pipelines extracting web data bypassing firewalls and rate limits, returning clean API payloads.",
                "icon": "Database",
                "features": ["Bypass Cloudflare and Captchas", "Playwright & Selenium clustering", "Scheduled extraction tasks", "REST/GraphQL outputs"],
                "active": True
            }
        ]
        for s in services_data:
            service_repo.create(db, obj_in=s)
        print("Initial services seeded.")

def seed_faqs(db: Session):
    from app.repositories.faq import faq_repo
    
    if len(faq_repo.get_multi(db)) == 0:
        faqs_data = [
            {
                "question": "What is Nexora AI and what do you do?",
                "answer": "Nexora AI is an elite enterprise-grade AI automation and software development agency. We build autonomous agent networks, custom SaaS systems, web scrapers, and dashboard infrastructures designed to cut operational costs and scale revenue.",
                "category": "General",
                "order_index": 1
            },
            {
                "question": "How do you ensure data security with LLMs?",
                "answer": "We enforce enterprise security standards: SOC2-compliant cloud deployments, local model hosting (Ollama/vLLM) where necessary to prevent data leakage, and rigorous transit/at-rest encryption protocols.",
                "category": "Security",
                "order_index": 2
            },
            {
                "question": "What is the timeline for a custom AI project?",
                "answer": "A standard AI automation or agent deployment takes 4 to 8 weeks. Complex SaaS applications or customized multi-agent systems range from 8 to 12 weeks including testing and deployment.",
                "category": "Process",
                "order_index": 3
            }
        ]
        for f in faqs_data:
            faq_repo.create(db, obj_in=f)
        print("Initial FAQs seeded.")

def seed_testimonials(db: Session):
    from app.repositories.testimonial import testimonial_repo
    
    if len(testimonial_repo.get_multi(db)) == 0:
        testimonials_data = [
            {
                "name": "Sarah Jenkins",
                "role": "VP of Operations",
                "company": "Vortex Analytics",
                "content": "Nexora AI completely transformed our customer lifecycle. Their autonomous agents now handle 80% of incoming requests with zero human intervention. Absolutely stellar engineering.",
                "image": "",
                "rating": 5
            },
            {
                "name": "David Chen",
                "role": "CTO",
                "company": "CloudForge",
                "content": "Building our custom AI scheduling pipeline with Nexora AI saved us hundreds of engineering hours. The code is exceptionally clean, type-safe, and scalable.",
                "image": "",
                "rating": 5
            }
        ]
        for t in testimonials_data:
            testimonial_repo.create(db, obj_in=t)
        print("Initial testimonials seeded.")

def seed_seo_settings(db: Session):
    from app.repositories.seo import seo_repo
    
    if len(seo_repo.get_multi(db)) == 0:
        seo_data = [
            {
                "page_route": "/",
                "title": "Nexora AI | Building Intelligent Systems For Modern Businesses",
                "description": "We design and deploy enterprise-grade AI automation, custom software, autonomous agents, web scraping systems, and premium SaaS dashboards.",
                "keywords": "AI agents, automation, enterprise software, FastAPI, Next.js, web scraping, SEO",
                "og_image": "/images/og-main.jpg"
            }
        ]
        for s in seo_data:
            seo_repo.create(db, obj_in=s)
        print("Initial SEO settings seeded.")
