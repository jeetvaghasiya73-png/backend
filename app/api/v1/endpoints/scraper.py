import os
import sys
import json
import subprocess
import threading
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_admin_user
from app.database.session import SessionLocal
from app.models.scraped_lead import ScrapedLead
from app.core.security import decode_token
from app.repositories.user import user_repo

router = APIRouter()

# WebSocket clients tracking
active_websockets: List[WebSocket] = []
main_loop: Optional[asyncio.AbstractEventLoop] = None

# Schema for request validation
class ScraperRunRequest(BaseModel):
    cities: List[str]
    keywords: List[str]
    max_pages: Optional[int] = 5

# Global state for scraper execution
scraper_state: Dict[str, Any] = {
    "is_running": False,
    "status": "idle",
    "cities": [],
    "services": [],
    "started_at": None,
    "finished_at": None,
    "error": None,
    "current_step": None,
    "log_history": []
}

state_lock = threading.Lock()

# Per-run cancellation mechanism
_run_id: int = 0
_cancel_event: threading.Event = threading.Event()

# Global process tracker
active_process: Optional[subprocess.Popen] = None

def broadcast_state():
    if not active_websockets or not main_loop:
        return
        
    with state_lock:
        state_copy = dict(scraper_state)
        
    async def send_to_all():
        for ws in list(active_websockets):
            try:
                await ws.send_json(state_copy)
            except Exception:
                if ws in active_websockets:
                    active_websockets.remove(ws)
                    
    asyncio.run_coroutine_threadsafe(send_to_all(), main_loop)

def add_log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] {message}"
    print(formatted_msg)
    with state_lock:
        scraper_state["log_history"].append(formatted_msg)
        # Keep last 150 log lines to save memory
        if len(scraper_state["log_history"]) > 150:
            scraper_state["log_history"].pop(0)
    broadcast_state()

def sync_pdp_to_sqlite(scraper_dir: str):
    """Read today's PDP data from MySQL and upsert into SQLite scraped_leads table."""
    add_log("Starting MySQL -> SQLite sync for scraped leads...")
    
    try:
        import mysql.connector
        
        # Load MySQL config from the scraper's config.json
        config_path = os.path.join(scraper_dir, "config", "config.json")
        if not os.path.exists(config_path):
            config_path = os.path.join(scraper_dir, "config.json")
        
        if not os.path.exists(config_path):
            add_log("[Sync] WARNING: config.json not found, skipping sync.")
            return
        
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        
        db_config = config_data.get("database", {})
        host = db_config.get("host", "localhost")
        port = db_config.get("port", 3306)
        user = db_config.get("user", "root")
        password = db_config.get("password", "")
        database_name = db_config.get("database_name", "leads")
        
        # Resolve today's PDP table name
        date_str = datetime.now().strftime('%Y_%m_%d')
        pdp_table = f"justdial_pdp_{date_str}"
        
        add_log(f"[Sync] Connecting to MySQL database '{database_name}', table '{pdp_table}'...")
        
        mysql_conn = mysql.connector.connect(
            host=host, port=port, user=user,
            password=password, database=database_name
        )
        cursor = mysql_conn.cursor(dictionary=True)
        
        # Check if PDP table exists
        cursor.execute("SHOW TABLES LIKE %s", (pdp_table,))
        if not cursor.fetchone():
            add_log(f"[Sync] PDP table '{pdp_table}' not found in MySQL. Skipping sync.")
            cursor.close()
            mysql_conn.close()
            return
        
        # Fetch all PDP records with non-empty emails
        cursor.execute(f"SELECT * FROM `{pdp_table}` WHERE bussiness_email IS NOT NULL AND TRIM(bussiness_email) != ''")
        pdp_rows = cursor.fetchall()
        cursor.close()
        mysql_conn.close()
        
        add_log(f"[Sync] Loaded {len(pdp_rows)} leads from MySQL.")
        
        if not pdp_rows:
            add_log("[Sync] No leads found to sync. Sync complete.")
            return
        
        # Upsert into SQLite
        db = SessionLocal()
        synced = 0
        skipped = 0
        seen_leads = set()
        
        try:
            for row in pdp_rows:
                email = (row.get("bussiness_email") or "").strip().lower()
                phone = (row.get("bussiness_number") or "").strip()
                
                if not email or "@" not in email:
                    skipped += 1
                    continue
                
                # Prevent duplicate inserts within the same batch sync session
                if email in seen_leads:
                    skipped += 1
                    continue
                seen_leads.add(email)
                
                # Check if this email already exists in SQLite
                existing = db.query(ScrapedLead).filter(ScrapedLead.bussiness_email == email).first()
                if existing:
                    skipped += 1
                    continue
                
                # Check for active campaign auto-assignment
                from app.models.campaign import Campaign
                active_campaigns = db.query(Campaign).filter(Campaign.status == "RUNNING").all()
                assigned_camp_id = None
                for camp in active_campaigns:
                    city_match = not camp.target_city or (row.get("scraped_city") and camp.target_city.lower() in str(row.get("scraped_city")).lower())
                    service_match = not camp.target_service or (
                        (row.get("scraped_service") and camp.target_service.lower() in str(row.get("scraped_service")).lower()) or 
                        (row.get("category") and camp.target_service.lower() in str(row.get("category")).lower())
                    )
                    if city_match and service_match:
                        assigned_camp_id = camp.id
                        break

                # Create new record in SQLite
                new_lead = ScrapedLead(
                    bussiness_name=row.get("bussiness_name", ""),
                    bussiness_email=email,
                    bussiness_number=phone,
                    bussiness_area=row.get("bussiness_area", ""),
                    rating=row.get("rating", ""),
                    landmark=row.get("landmark", ""),
                    total_review=row.get("total_review", ""),
                    building=row.get("building", ""),
                    pincode=row.get("pincode", ""),
                    bussiness_website=row.get("bussiness_website", ""),
                    category=row.get("category", ""),
                    bussiness_address=row.get("bussiness_address", ""),
                    service=row.get("service", ""),
                    scraped_city=row.get("scraped_city", ""),
                    scraped_service=row.get("scraped_service", ""),
                    campaign_id=assigned_camp_id,
                    email_status="pending" if assigned_camp_id else "pending",
                    created_at=datetime.now(timezone.utc)
                )
                db.add(new_lead)
                synced += 1
                
                # Batch commit every 50 records
                if synced % 50 == 0:
                    db.commit()
                    add_log(f"[Sync] Progress: {synced} new leads synced...")
            
            db.commit()
            add_log(f"[Sync] [OK] Sync complete: {synced} new leads added, {skipped} duplicates skipped.")
        except Exception as sync_err:
            db.rollback()
            add_log(f"[Sync] ERROR during SQLite upsert: {sync_err}")
        finally:
            db.close()
            
    except ImportError:
        add_log("[Sync] WARNING: mysql-connector-python not installed. Cannot sync from MySQL.")
    except Exception as e:
        add_log(f"[Sync] ERROR: {str(e)}")


def save_and_broadcast_lead(record: dict):
    """Save lead to SQLite in real-time and broadcast to WebSocket clients."""
    email = (record.get("bussiness_email") or "").strip().lower()
    phone = (record.get("bussiness_number") or "").strip()
    if not email or "@" not in email:
        return
        
    db = SessionLocal()
    try:
        # Check if this email already exists in SQLite
        existing = db.query(ScrapedLead).filter(ScrapedLead.bussiness_email == email).first()
        if existing:
            return
            
        # Create new record in SQLite
        new_lead = ScrapedLead(
            bussiness_name=record.get("bussiness_name", ""),
            bussiness_email=email,
            bussiness_number=phone,
            bussiness_area=record.get("bussiness_area", ""),
            rating=record.get("rating", ""),
            landmark=record.get("landmark", ""),
            total_review=record.get("total_review", ""),
            building=record.get("building", ""),
            pincode=record.get("pincode", ""),
            bussiness_website=record.get("bussiness_website", ""),
            category=record.get("category", ""),
            bussiness_address=record.get("bussiness_address", ""),
            service=record.get("service", ""),
            scraped_city=record.get("scraped_city", ""),
            scraped_service=record.get("scraped_service", ""),
            created_at=datetime.now(timezone.utc)
        )
        db.add(new_lead)
        db.commit()
        db.refresh(new_lead)
        
        # Broadcast via WebSocket!
        if active_websockets and main_loop:
            lead_data = {
                "id": new_lead.id,
                "bussiness_name": new_lead.bussiness_name,
                "bussiness_email": new_lead.bussiness_email,
                "bussiness_number": new_lead.bussiness_number,
                "bussiness_area": new_lead.bussiness_area,
                "rating": new_lead.rating,
                "landmark": new_lead.landmark,
                "total_review": new_lead.total_review,
                "building": new_lead.building,
                "pincode": new_lead.pincode,
                "bussiness_website": new_lead.bussiness_website,
                "category": new_lead.category,
                "bussiness_address": new_lead.bussiness_address,
                "service": new_lead.service,
                "scraped_city": new_lead.scraped_city,
                "scraped_service": new_lead.scraped_service,
                "created_at": new_lead.created_at.isoformat() if new_lead.created_at else None
            }
            
            async def send_lead():
                for ws in list(active_websockets):
                    try:
                        await ws.send_json({
                            "type": "lead",
                            "lead": lead_data
                        })
                    except Exception:
                        if ws in active_websockets:
                            active_websockets.remove(ws)
                            
            asyncio.run_coroutine_threadsafe(send_lead(), main_loop)
    except Exception as e:
        db.rollback()
        print(f"Error saving real-time lead to SQLite: {e}")
    finally:
        db.close()


def run_scraper_in_background(cities: List[str], keywords: List[str], max_pages: int,
                               my_run_id: int, cancel_event: threading.Event):
    """Background worker for a single scraper run.
    
    `my_run_id` and `cancel_event` are captured at dispatch time so that
    a stale thread from a previous (stopped) run can never corrupt the
    state of a newer run.
    """
    global scraper_state, active_process
    
    with state_lock:
        scraper_state["is_running"] = True
        scraper_state["status"] = "running"
        scraper_state["cities"] = cities
        scraper_state["services"] = keywords
        scraper_state["started_at"] = datetime.now().isoformat()
        scraper_state["finished_at"] = None
        scraper_state["error"] = None
        scraper_state["current_step"] = "updating_config"
        scraper_state["log_history"] = []
        
    broadcast_state()
    add_log(f"Starting background scraper job for cities: {cities}, keywords: {keywords}")
    
    def _cancelled() -> bool:
        """Check whether this specific run has been cancelled."""
        return cancel_event.is_set()
    
    def _is_current_run() -> bool:
        """Return True if this thread still owns the global run slot."""
        return _run_id == my_run_id
    
    try:
        # 1. Update config.json in just_dial_scraper
        current_file = os.path.abspath(__file__)
        backend_dir = current_file
        while backend_dir and os.path.basename(backend_dir) != "backend":
            parent = os.path.dirname(backend_dir)
            if parent == backend_dir:
                break
            backend_dir = parent
        
        # The scraper code lives in a nested directory: just_dial_scraper/just_dial_scraper/
        scraper_dir = os.path.join(backend_dir, "just_dial_scraper", "just_dial_scraper")
        config_path = os.path.join(scraper_dir, "config", "config.json")
        
        add_log(f"Reading existing config from {config_path}")
        if not os.path.exists(config_path):
            config_path = os.path.join(scraper_dir, "config.json")
            
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"config.json not found in {scraper_dir}")
            
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
            
        if "scraper" not in config_data:
            config_data["scraper"] = {}
            
        config_data["scraper"]["cities"] = cities
        config_data["scraper"]["services"] = keywords
        config_data["scraper"]["max_pages"] = max_pages
        
        # Save updated config
        add_log(f"Updating config.json with target cities and keywords...")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
        add_log("config.json updated successfully.")
        
        # Determine the Python executable
        python_exe = sys.executable
        
        # Prepare environment (unbuffered output and no bytecode writes to prevent uvicorn reload loops)
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        
        # 2. Run run.py --scrape
        if _cancelled():
            add_log("Pipeline aborted before listings scrape.")
            return
        with state_lock:
            scraper_state["current_step"] = "scraping_listings"
        broadcast_state()
        add_log("Executing justdial listings scraper (run.py --scrape)...")
        
        cmd_scrape = [python_exe, "run.py", "--scrape"]
        process = subprocess.Popen(
            cmd_scrape,
            cwd=scraper_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            env=env
        )
        active_process = process
        
        # Read logs in real-time
        if process.stdout:
            for line in process.stdout:
                if _cancelled():
                    break
                clean_line = line.strip()
                if clean_line:
                    add_log(f"[Scraper] {clean_line}")
                    
        process.wait()
        
        if _cancelled():
            add_log("Listings scrape aborted early.")
            return
                
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd_scrape)
            
        add_log("Listings scraper finished successfully.")
        
        # 3. Run run.py --crawl-pdp
        if _cancelled():
            add_log("Pipeline aborted before PDP crawl.")
            return
        with state_lock:
            scraper_state["current_step"] = "crawling_pdp"
        broadcast_state()
        add_log("Executing detailed PDP crawler (run.py --crawl-pdp)...")
        
        cmd_pdp = [python_exe, "run.py", "--crawl-pdp"]
        process_pdp = subprocess.Popen(
            cmd_pdp,
            cwd=scraper_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            env=env
        )
        active_process = process_pdp
        
        if process_pdp.stdout:
            for line in process_pdp.stdout:
                if _cancelled():
                    break
                clean_line = line.strip()
                if clean_line:
                    if clean_line.startswith("[DATA] "):
                        try:
                            record_json = clean_line[len("[DATA] "):]
                            record = json.loads(record_json)
                            save_and_broadcast_lead(record)
                        except Exception as e:
                            add_log(f"Error parsing real-time lead: {e}")
                    else:
                        add_log(f"[PDP Crawler] {clean_line}")
                    
        process_pdp.wait()
        
        if _cancelled():
            add_log("PDP crawl aborted early.")
            return
                
        if process_pdp.returncode != 0:
            raise subprocess.CalledProcessError(process_pdp.returncode, cmd_pdp)
            
        add_log("PDP crawling finished successfully.")
        
        # 4. Sync PDP leads from MySQL to SQLite so they appear in the admin panel
        if _cancelled():
            add_log("Pipeline aborted before sync.")
            return
        with state_lock:
            scraper_state["current_step"] = "syncing_to_db"
        broadcast_state()
        add_log("Syncing scraped leads from MySQL to admin panel database...")
        sync_pdp_to_sqlite(scraper_dir)
        
        with state_lock:
            scraper_state["status"] = "completed"
            scraper_state["current_step"] = None
        broadcast_state()
            
    except Exception as e:
        if _cancelled():
            # Job was intentionally stopped; don't overwrite with failure state
            return
        error_msg = f"Job failed with error: {str(e)}"
        add_log(error_msg)
        with state_lock:
            scraper_state["status"] = "failed"
            scraper_state["error"] = str(e)
            scraper_state["current_step"] = None
        broadcast_state()
    finally:
        with state_lock:
            # Only touch global state if this thread still owns the current run.
            # If a newer run has already started (_run_id was bumped), this stale
            # thread must not reset is_running or overwrite finished_at.
            if _is_current_run():
                active_process = None
                scraper_state["is_running"] = False
                if not _cancelled():
                    scraper_state["finished_at"] = datetime.now().isoformat()
        broadcast_state()
        add_log("Background scraper job finished.")

@router.post("/run")
def trigger_scraper(
    payload: ScraperRunRequest,
    background_tasks: BackgroundTasks,
    admin_user = Depends(get_current_admin_user)
):
    """
    Trigger the Justdial scraper job in the background (Admin only).
    """
    global scraper_state, _run_id, _cancel_event
    
    if not payload.cities or not payload.keywords:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one city and one business search keyword is required."
        )
        
    with state_lock:
        if scraper_state["is_running"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A scraper job is already running."
            )
        # Bump run_id and create a fresh cancel event so that any lingering
        # thread from a previous (stopped) run cannot interfere with this one.
        _run_id += 1
        _cancel_event = threading.Event()
        current_run_id = _run_id
        current_cancel = _cancel_event
            
    background_tasks.add_task(
        run_scraper_in_background,
        payload.cities, payload.keywords, payload.max_pages,
        current_run_id, current_cancel
    )
    return {"message": "Scraper job started in the background."}

@router.get("/status")
def get_scraper_status(admin_user = Depends(get_current_admin_user)):
    """
    Get the status of the current or last scraping job (Admin only).
    """
    return scraper_state

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = None):
    await websocket.accept()
    
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
        
    db = SessionLocal()
    try:
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
            
        user_id_str = payload.get("sub")
        if user_id_str is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
            
        try:
            user_id = int(user_id_str)
        except ValueError:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
            
        user = user_repo.get(db, id=user_id)
        if not user or not user.is_active or not user.is_admin:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    finally:
        db.close()
        
    global main_loop
    main_loop = asyncio.get_running_loop()
    active_websockets.append(websocket)
    
    # Send the current state immediately upon connection
    with state_lock:
        state_copy = dict(scraper_state)
    await websocket.send_json(state_copy)
    
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if websocket in active_websockets:
            active_websockets.remove(websocket)

@router.post("/stop")
def stop_scraper(admin_user = Depends(get_current_admin_user)):
    """
    Stop the currently running scraper job (Admin only).
    """
    global scraper_state, active_process, _cancel_event
    
    with state_lock:
        if not scraper_state["is_running"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No scraper job is currently running."
            )
    
    # Signal the background thread to stop via the per-run cancel event
    _cancel_event.set()
    add_log("Stopping scraper execution requested by user...")
    
    terminated = False
    if active_process and active_process.poll() is None:
        try:
            # Kill process tree on Windows using taskkill
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(active_process.pid)], capture_output=True, check=True)
            add_log(f"Terminated process tree with PID {active_process.pid}.")
            terminated = True
        except Exception as e:
            add_log(f"Error terminating process tree via taskkill: {e}")
            try:
                active_process.kill()
                terminated = True
            except Exception as kill_err:
                add_log(f"Fallback kill failed: {kill_err}")
    else:
        # Process already finished or not started
        terminated = True
                
    if terminated:
        with state_lock:
            scraper_state["is_running"] = False
            scraper_state["status"] = "stopped"
            scraper_state["current_step"] = None
            scraper_state["finished_at"] = datetime.now().isoformat()
            active_process = None
        add_log("Scraper execution stopped successfully.")
        broadcast_state()
        return {"message": "Scraper execution stopped successfully."}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop the scraper process. It might have already exited."
        )

@router.post("/sync")
def trigger_manual_sync(admin_user = Depends(get_current_admin_user)):
    """
    Manually sync scraped leads from MySQL to SQLite database (Admin only).
    """
    current_file = os.path.abspath(__file__)
    backend_dir = current_file
    while backend_dir and os.path.basename(backend_dir) != "backend":
        parent = os.path.dirname(backend_dir)
        if parent == backend_dir:
            break
        backend_dir = parent
    
    scraper_dir = os.path.join(backend_dir, "just_dial_scraper", "just_dial_scraper")
    
    try:
        add_log("Manual sync requested by user...")
        sync_pdp_to_sqlite(scraper_dir)
        return {"message": "Sync completed successfully."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )
