from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import engine, SessionLocal, Base
from app.models.base import Base as _  # Force import of all models
from app.routers.api import api_router

# Auto-create tables on startup (resilient)
try:
    Base.metadata.create_all(bind=engine)
except Exception as db_err:
    print(f"Table creation warning on module load: {db_err}")

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
    allow_origin_regex=r"https?://.*",
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

# 5. Public Cache-Control middleware for high performance and fast response speeds
@app.middleware("http")
async def add_cache_control_header(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if request.method == "GET" and (
        "/public/" in path or
        "/blogs" in path or
        "/portfolio" in path or
        "/services" in path or
        "/faqs" in path or
        "/testimonials" in path
    ):
        response.headers["Cache-Control"] = "public, max-age=60, s-maxage=300, stale-while-revalidate=600"
    return response

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
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Startup create_all notice: {e}")

    db = SessionLocal()
    try:
        # Automatic migration checks for scraped_leads and campaigns
        from sqlalchemy import text, inspect
        inspector = inspect(db.bind)
        dialect_name = db.bind.dialect.name if (db.bind and hasattr(db.bind, "dialect")) else "sqlite"
        ts_type = "TIMESTAMP" if dialect_name == "postgresql" else "TIMESTAMP"
        
        # Check and migrate scraped_leads columns
        if "scraped_leads" in inspector.get_table_names():
            columns = [col["name"] for col in inspector.get_columns("scraped_leads")]
            migrations = [
                ("email_status", "ALTER TABLE scraped_leads ADD COLUMN email_status VARCHAR(50) DEFAULT 'pending'"),
                ("email_sent_at", f"ALTER TABLE scraped_leads ADD COLUMN email_sent_at {ts_type} NULL"),
                ("email_error", "ALTER TABLE scraped_leads ADD COLUMN email_error TEXT NULL"),
                ("email_subject", "ALTER TABLE scraped_leads ADD COLUMN email_subject VARCHAR(255) NULL"),
                ("email_body", "ALTER TABLE scraped_leads ADD COLUMN email_body TEXT NULL"),
                ("email_message", "ALTER TABLE scraped_leads ADD COLUMN email_message TEXT NULL"),
                ("personalization_status", "ALTER TABLE scraped_leads ADD COLUMN personalization_status VARCHAR(50) DEFAULT 'pending'"),
                ("last_email_at", f"ALTER TABLE scraped_leads ADD COLUMN last_email_at {ts_type} NULL"),
                ("next_followup_at", f"ALTER TABLE scraped_leads ADD COLUMN next_followup_at {ts_type} NULL"),
                ("followup_count", "ALTER TABLE scraped_leads ADD COLUMN followup_count INTEGER DEFAULT 0"),
                ("reply_status", "ALTER TABLE scraped_leads ADD COLUMN reply_status VARCHAR(50) DEFAULT 'unprocessed'"),
                ("unsubscribe", "ALTER TABLE scraped_leads ADD COLUMN unsubscribe BOOLEAN DEFAULT FALSE"),
                ("bounced", "ALTER TABLE scraped_leads ADD COLUMN bounced BOOLEAN DEFAULT FALSE"),
                ("campaign_id", "ALTER TABLE scraped_leads ADD COLUMN campaign_id INTEGER NULL REFERENCES campaigns(id) ON DELETE SET NULL")
            ]
            for col_name, sql in migrations:
                if col_name not in columns:
                    try:
                        db.execute(text(sql))
                        db.commit()
                        print(f"Migration: Added {col_name} column to scraped_leads")
                    except Exception as col_err:
                        db.rollback()
                        print(f"Migration notice for {col_name}: {col_err}")

        # Automatic migration checks for users table
        if "users" in inspector.get_table_names():
            user_columns = [col["name"] for col in inspector.get_columns("users")]
            if "is_main_admin" not in user_columns:
                try:
                    db.execute(text("ALTER TABLE users ADD COLUMN is_main_admin BOOLEAN DEFAULT FALSE"))
                    db.commit()
                    print("Migration: Added is_main_admin column to users")
                except Exception as col_err:
                    db.rollback()

        # Automatic migration checks for campaigns table
        if "campaigns" in inspector.get_table_names():
            campaign_columns = [col["name"] for col in inspector.get_columns("campaigns")]
            if "target_city" not in campaign_columns:
                try:
                    db.execute(text("ALTER TABLE campaigns ADD COLUMN target_city VARCHAR(100) NULL"))
                    db.commit()
                    print("Migration: Added target_city column to campaigns")
                except Exception as col_err:
                    db.rollback()
            if "target_service" not in campaign_columns:
                try:
                    db.execute(text("ALTER TABLE campaigns ADD COLUMN target_service VARCHAR(100) NULL"))
                    db.commit()
                    print("Migration: Added target_service column to campaigns")
                except Exception as col_err:
                    db.rollback()

        # Ensure high-performance indexes exist on critical filter and sorting columns
        index_queries = [
            "CREATE INDEX IF NOT EXISTS idx_scraped_leads_created_at ON scraped_leads(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_scraped_leads_email_status ON scraped_leads(email_status);",
            "CREATE INDEX IF NOT EXISTS idx_scraped_leads_reply_status ON scraped_leads(reply_status);",
            "CREATE INDEX IF NOT EXISTS idx_scraped_leads_campaign_id ON scraped_leads(campaign_id);",
            "CREATE INDEX IF NOT EXISTS idx_email_messages_status ON email_messages(status);",
            "CREATE INDEX IF NOT EXISTS idx_email_messages_lead_id ON email_messages(lead_id);",
            "CREATE INDEX IF NOT EXISTS idx_email_messages_created_at ON email_messages(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_followups_status ON followups(status);",
            "CREATE INDEX IF NOT EXISTS idx_followups_scheduled_at ON followups(scheduled_at);",
            "CREATE INDEX IF NOT EXISTS idx_followups_lead_id ON followups(lead_id);",
            "CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at);"
        ]
        for idx_sql in index_queries:
            try:
                db.execute(text(idx_sql))
                db.commit()
            except Exception:
                db.rollback()

        try:
            seed_admin_user(db)
        except Exception as err:
            print(f"Seed admin notice: {err}")
        try:
            seed_services(db)
        except Exception as err:
            print(f"Seed services notice: {err}")
        try:
            seed_faqs(db)
        except Exception as err:
            print(f"Seed faqs notice: {err}")
        try:
            seed_testimonials(db)
        except Exception as err:
            print(f"Seed testimonials notice: {err}")
        try:
            seed_portfolio(db)
        except Exception as err:
            print(f"Seed portfolio notice: {err}")
        try:
            seed_seo_settings(db)
        except Exception as err:
            print(f"Seed seo notice: {err}")
        
        # Start the background email worker
        try:
            from app.services.email_worker import email_worker
            email_worker.start()
        except Exception as worker_err:
            print(f"Worker start notice: {worker_err}")
    except Exception as startup_err:
        print(f"General startup event notice: {startup_err}")
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
            "is_superadmin": True,
            "is_main_admin": True
        })
        print(f"Default Main Admin user created: {settings.ADMIN_USERNAME}")
    else:
        # Ensure initial seed user has Main Admin role
        if not getattr(admin, "is_main_admin", False):
            admin.is_main_admin = True
            admin.is_superadmin = True
            db.add(admin)
            db.commit()
            print(f"Granted Main Admin role to primary user: {settings.ADMIN_USERNAME}")

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

def seed_portfolio(db: Session):
    from app.repositories.portfolio import portfolio_repo
    
    if len(portfolio_repo.get_multi(db)) == 0:
        portfolio_data = [
            {
                "title": "Intellect CRM System",
                "client": "Vortex Analytics",
                "slug": "intellect-crm-system",
                "description": "Autonomous AI Agent node processing incoming customer tickets, analyzing sentiment, and updating CRM records in real-time.",
                "image": "",
                "year": 2026,
                "services_used": ["AI Agents", "CRM Sync"],
                "url": "",
                "featured": True
            },
            {
                "title": "Aether Data Farms",
                "client": "Aether Holdings",
                "slug": "aether-data-farms",
                "description": "High-throughput Playwright and Selenium crawler cluster fetching thousands of business listings per hour with automated proxy rotation.",
                "image": "",
                "year": 2025,
                "services_used": ["Scraping", "Lead Gen"],
                "url": "",
                "featured": True
            },
            {
                "title": "Helios SaaS Platform",
                "client": "Helios Energy",
                "slug": "helios-saas-platform",
                "description": "Modern cloud-native dashboard for monitoring energy grid metrics, featuring real-time WebSocket telemetry and analytics graphs.",
                "image": "",
                "year": 2025,
                "services_used": ["Next.js Web Application", "FastAPI"],
                "url": "",
                "featured": True
            },
            {
                "title": "Apex Outbound Automator",
                "client": "Apex Growth",
                "slug": "apex-outbound-automator",
                "description": "Personalized AI outreach engine that scrapes prospective leads, drafts tailored email pitches, and manages automated follow-ups.",
                "image": "",
                "year": 2026,
                "services_used": ["Email Automation", "SEO"],
                "url": "",
                "featured": True
            }
        ]
        for p in portfolio_data:
            portfolio_repo.create(db, obj_in=p)
        print("Initial portfolio seeded.")

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
