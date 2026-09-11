from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from pydantic import BaseModel
from app.dependencies.database import get_db
from app.dependencies.auth import get_current_admin_user
from app.models.scraped_lead import ScrapedLead
from app.schemas.scraped_lead import ScrapedLeadOut, ScrapedLeadUpdate

class BulkDeleteRequest(BaseModel):
    lead_ids: List[int]

import csv
import io
import pandas as pd
from fastapi.responses import StreamingResponse
import numpy as np

router = APIRouter()

def get_val(row, *variants):
    for v in variants:
        if v in row and row[v] is not None and str(row[v]).strip() != "" and str(row[v]).lower() != "nan":
            return str(row[v]).strip()
    return ""

from datetime import datetime, timezone

@router.post("/upload")
def upload_scraped_leads(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Ultra-fast bulk upload for CSV or Excel (.csv, .xlsx, .xls) spreadsheet files into PostgreSQL database.
    Enforces 100% unique data in Render database using O(1) in-memory email, phone, and city deduplication.
    """
    filename_lower = file.filename.lower() if file.filename else ""
    if not (filename_lower.endswith('.xlsx') or filename_lower.endswith('.xls') or filename_lower.endswith('.csv')):
        raise HTTPException(status_code=400, detail="Only .csv, .xlsx, or .xls spreadsheet files are supported")
        
    try:
        contents = file.file.read()
        if filename_lower.endswith('.csv'):
            try:
                df = pd.read_csv(io.BytesIO(contents))
            except Exception:
                df = pd.read_csv(io.BytesIO(contents), encoding="latin1")
        else:
            df = pd.read_excel(io.BytesIO(contents))
        
        # Map DataFrame column headers (lowercase trim for flexible matching)
        col_map = {str(col).strip().lower(): col for col in df.columns}
        
        def find_col(*candidates):
            for cand in candidates:
                if cand.lower() in col_map:
                    return col_map[cand.lower()]
            return None

        col_email = find_col("bussiness_email", "business_email", "email", "email address", "email_address", "e-mail", "contact_email", "mail", "emails", "mail_id", "email_id")
        col_name = find_col("bussiness_name", "business_name", "company", "company name", "company_name", "name", "lead name", "lead_name", "title", "business name", "store_name", "store name", "firm", "firm_name", "organization", "agency")
        col_city = find_col("scraped_city", "city", "location", "place", "town", "scraped city", "district", "state", "city_name")
        col_phone = find_col("bussiness_number", "business_number", "phone", "phone number", "phone_number", "mobile", "contact_number", "number", "business number", "mobile_number", "mobile number", "contact", "telephone", "phone_no")
        col_website = find_col("bussiness_website", "business_website", "website", "url", "site", "web", "business website", "link", "domain")
        col_category = find_col("category", "industry", "type", "business_type", "sector", "category_name")
        col_service = find_col("scraped_service", "service", "keyword", "scraped_keyword", "services", "scraped service", "sub_category")
        col_rating = find_col("rating", "score", "stars", "rate")
        col_address = find_col("bussiness_address", "business_address", "address", "full_address", "business address", "location_address")
        col_area = find_col("bussiness_area", "business_area", "area")
        col_landmark = find_col("landmark")
        col_reviews = find_col("total_review", "total reviews", "reviews")

        records = df.to_dict(orient="records")
        
        # Pre-fetch all existing unique keys from PostgreSQL database for O(1) deduplication
        existing_emails = set(
            e[0].lower().strip() for e in db.query(ScrapedLead.bussiness_email).filter(
                ScrapedLead.bussiness_email.isnot(None),
                ScrapedLead.bussiness_email != ""
            ).all() if e[0]
        )
        
        existing_name_phones = set(
            (n[0].lower().strip(), n[1].strip()) for n in db.query(ScrapedLead.bussiness_name, ScrapedLead.bussiness_number).filter(
                ScrapedLead.bussiness_name.isnot(None),
                ScrapedLead.bussiness_name != "",
                ScrapedLead.bussiness_number.isnot(None),
                ScrapedLead.bussiness_number != ""
            ).all() if n[0] and n[1]
        )

        existing_name_cities = set(
            (c[0].lower().strip(), c[1].lower().strip()) for c in db.query(ScrapedLead.bussiness_name, ScrapedLead.scraped_city).filter(
                ScrapedLead.bussiness_name.isnot(None),
                ScrapedLead.bussiness_name != "",
                ScrapedLead.scraped_city.isnot(None),
                ScrapedLead.scraped_city != ""
            ).all() if c[0] and c[1]
        )
        
        leads_to_insert = []
        cities_inserted = set()
        skipped_count = 0
        now_utc = datetime.now(timezone.utc)
        
        def safe_field(col_name, max_len=None, default=None):
            if not col_name or col_name not in row or row[col_name] is None:
                return default
            val = str(row[col_name]).strip()
            if not val or val.lower() == "nan" or val.lower() == "none" or val.lower() == "null":
                return default
            if max_len and len(val) > max_len:
                return val[:max_len]
            return val

        for row in records:
            raw_email = safe_field(col_email)
            b_name = safe_field(col_name, max_len=250)
            phone = safe_field(col_phone, max_len=50)
            city = safe_field(col_city, max_len=100, default="Outreach")
            
            # Must have at least a business name OR phone OR email to be a valid lead
            if not b_name and not raw_email and not phone:
                skipped_count += 1
                continue
            
            cleaned_email = None
            if raw_email:
                cand_email = raw_email.replace(";", ",").split(",")[0].strip().lower()
                if "@" in cand_email:
                    cleaned_email = cand_email[:250]

            # Uniqueness Check 1: Duplicate Email in Render DB or current upload
            if cleaned_email and cleaned_email in existing_emails:
                skipped_count += 1
                continue

            # Uniqueness Check 2: Duplicate Business Name + Phone Number in Render DB
            if b_name and phone:
                name_phone_key = (b_name.lower().strip(), phone.strip())
                if name_phone_key in existing_name_phones:
                    skipped_count += 1
                    continue

            # Uniqueness Check 3: Duplicate Business Name + City in Render DB
            if b_name and city:
                name_city_key = (b_name.lower().strip(), city.lower().strip())
                if name_city_key in existing_name_cities:
                    skipped_count += 1
                    continue

            # If business name is missing but email exists, derive title from email handle
            if not b_name:
                b_name = cleaned_email.split("@")[0].replace(".", " ").replace("_", " ").title() if cleaned_email else "Direct Lead"

            # Update tracking sets so duplicates inside the same uploaded file are also caught
            if cleaned_email:
                existing_emails.add(cleaned_email)
            if b_name and phone:
                existing_name_phones.add((b_name.lower().strip(), phone.strip()))
            if b_name and city:
                existing_name_cities.add((b_name.lower().strip(), city.lower().strip()))

            website = safe_field(col_website, max_len=500)
            category = safe_field(col_category, max_len=1000, default="B2B Lead")
            service = safe_field(col_service, max_len=1000, default="Digital Services")
            rating = safe_field(col_rating, max_len=20, default="4.5")
            address = safe_field(col_address, max_len=1000)
            area = safe_field(col_area, max_len=250)
            landmark = safe_field(col_landmark, max_len=250)
            total_review = safe_field(col_reviews, max_len=20)
            scraped_service_val = safe_field(col_service, max_len=250, default="Digital Services")

            leads_to_insert.append({
                "bussiness_name": b_name,
                "bussiness_email": cleaned_email,
                "bussiness_number": phone,
                "bussiness_area": area,
                "rating": rating,
                "landmark": landmark,
                "total_review": total_review,
                "bussiness_website": website,
                "category": category,
                "bussiness_address": address,
                "service": service,
                "scraped_city": city,
                "scraped_service": scraped_service_val,
                "email_status": "pending",
                "created_at": now_utc
            })
            if city:
                cities_inserted.add(city)
            
        if leads_to_insert:
            try:
                db.bulk_insert_mappings(ScrapedLead, leads_to_insert)
                db.commit()
            except Exception as insert_err:
                db.rollback()
                print("Bulk insert warning, falling back to individual object insertion:", insert_err)
                inserted_count = 0
                for item in leads_to_insert:
                    try:
                        lead_obj = ScrapedLead(**item)
                        db.add(lead_obj)
                        db.commit()
                        inserted_count += 1
                    except Exception as single_err:
                        db.rollback()
                        print(f"Skipping row due to db error: {single_err}")
                leads_to_insert = leads_to_insert[:inserted_count]
            try:
                from app.models.notification import Notification
                db.add(Notification(
                    title="Bulk Spreadsheet Import Completed",
                    message=f"Imported {len(leads_to_insert)} unique leads into database ({len(cities_inserted)} cities, {skipped_count} duplicates skipped).",
                    type="lead",
                    read=False,
                    link="/admin/dashboard/leads",
                    created_at=now_utc
                ))
            except Exception as notif_err:
                print("Failed to create upload notification:", notif_err)
            db.commit()

        return {
            "message": f"Successfully imported {len(leads_to_insert)} unique leads into database! ({skipped_count} duplicates skipped)",
            "inserted": len(leads_to_insert),
            "skipped": skipped_count,
            "total_rows": len(records),
            "cities_count": len(cities_inserted)
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")

@router.get("/export")
def export_scraped_leads(
    search: Optional[str] = Query(None, description="Search query"),
    city: Optional[str] = Query(None, description="Filter by city"),
    keyword: Optional[str] = Query(None, description="Filter by scraped keyword"),
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Export all scraped leads to a CSV file (Admin only).
    """
    query = db.query(ScrapedLead)
    
    # Apply filters
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                ScrapedLead.bussiness_name.ilike(search_term),
                ScrapedLead.bussiness_email.ilike(search_term),
                ScrapedLead.bussiness_number.ilike(search_term),
                ScrapedLead.bussiness_address.ilike(search_term),
                ScrapedLead.category.ilike(search_term)
            )
        )
        
    if city:
        query = query.filter(ScrapedLead.scraped_city.ilike(f"%{city}%"))
        
    if keyword:
        query = query.filter(ScrapedLead.scraped_service.ilike(f"%{keyword}%"))
        
    leads = query.order_by(ScrapedLead.created_at.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "ID", "Business Name", "Email", "Phone Number", "Area", "Landmark",
        "Total Reviews", "Building", "Pincode", "Website", "Category",
        "Address", "Service", "Scraped City", "Scraped Keyword", "Rating", "Created At"
    ])
    
    for lead in leads:
        writer.writerow([
            lead.id,
            lead.bussiness_name or "",
            lead.bussiness_email or "",
            lead.bussiness_number or "",
            lead.bussiness_area or "",
            lead.landmark or "",
            lead.total_review or "",
            lead.building or "",
            lead.pincode or "",
            lead.bussiness_website or "",
            lead.category or "",
            lead.bussiness_address or "",
            lead.service or "",
            lead.scraped_city or "",
            lead.scraped_service or "",
            lead.rating or "",
            lead.created_at.strftime("%Y-%m-%d %H:%M:%S") if lead.created_at else ""
        ])
        
    output.seek(0)
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=scraped_leads_export.csv"
    return response

@router.delete("/bulk")
def delete_all_scraped_leads(
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Delete all scraped leads from the SQLite database (Admin only).
    """
    try:
        num_deleted = db.query(ScrapedLead).delete()
        db.commit()
        return {"message": f"Successfully deleted all {num_deleted} scraped leads."}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear database: {str(e)}"
        )

@router.post("/bulk-delete")
def bulk_delete_scraped_leads(
    payload: BulkDeleteRequest,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Bulk delete specific scraped leads by ID (Admin only).
    """
    if not payload.lead_ids:
        return {"message": "No lead IDs provided.", "count": 0}
        
    try:
        num_deleted = db.query(ScrapedLead).filter(ScrapedLead.id.in_(payload.lead_ids)).delete(synchronize_session=False)
        db.commit()
        return {"message": f"Successfully deleted {num_deleted} scraped leads.", "count": num_deleted}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to bulk delete scraped leads: {str(e)}"
        )

@router.get("/stats")
def get_scraped_leads_stats(
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Ultra-fast SQL aggregated metrics for admin dashboard KPI cards and analytics.
    Exposed as /api/v1/scraped-leads/stats (Admin only).
    """
    total = db.query(ScrapedLead).count()

    city_counts = db.query(
        ScrapedLead.scraped_city,
        func.count(ScrapedLead.id).label("count")
    ).filter(
        ScrapedLead.scraped_city != None,
        ScrapedLead.scraped_city != ""
    ).group_by(ScrapedLead.scraped_city).order_by(func.count(ScrapedLead.id).desc()).limit(10).all()

    cities = [{"name": c[0], "value": c[1]} for c in city_counts]

    category_counts = db.query(
        func.coalesce(ScrapedLead.scraped_service, ScrapedLead.category, "General Business").label("cat"),
        func.count(ScrapedLead.id).label("count")
    ).group_by(func.coalesce(ScrapedLead.scraped_service, ScrapedLead.category, "General Business")).order_by(func.count(ScrapedLead.id).desc()).limit(10).all()

    categories = [{"name": c[0], "value": c[1]} for c in category_counts]

    unique_cities = db.query(func.count(func.distinct(ScrapedLead.scraped_city))).scalar() or 0
    unique_categories = db.query(func.count(func.distinct(ScrapedLead.scraped_service))).scalar() or 0

    return {
        "total": total,
        "cities": cities,
        "categories": categories,
        "unique_cities": unique_cities,
        "unique_categories": unique_categories
    }

@router.get("/")
def get_scraped_leads(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=10000, description="Items per page"),
    search: Optional[str] = Query(None, description="Search query"),
    city: Optional[str] = Query(None, description="Filter by city"),
    keyword: Optional[str] = Query(None, description="Filter by scraped keyword"),
    has_email: Optional[bool] = Query(None, description="Filter by email availability"),
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Retrieve scraped leads with search, filters, and pagination (Admin only).
    """
    query = db.query(ScrapedLead)
    
    if has_email is True:
        query = query.filter(ScrapedLead.bussiness_email.isnot(None), ScrapedLead.bussiness_email != "")
    elif has_email is False:
        query = query.filter(or_(ScrapedLead.bussiness_email.is_(None), ScrapedLead.bussiness_email == ""))

    # Apply filters
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                ScrapedLead.bussiness_name.ilike(search_term),
                ScrapedLead.bussiness_email.ilike(search_term),
                ScrapedLead.bussiness_number.ilike(search_term),
                ScrapedLead.bussiness_address.ilike(search_term),
                ScrapedLead.category.ilike(search_term)
            )
        )
        
    if city:
        query = query.filter(ScrapedLead.scraped_city.ilike(f"%{city}%"))
        
    if keyword:
        query = query.filter(ScrapedLead.scraped_service.ilike(f"%{keyword}%"))
        
    # Get total count before pagination
    total_count = query.count()
    
    # Apply pagination
    offset = (page - 1) * limit
    results = query.order_by(ScrapedLead.created_at.desc()).offset(offset).limit(limit).all()
    
    # Convert models to schema out format
    leads_out = [ScrapedLeadOut.model_validate(lead) for lead in results]
    
    return {
        "total": total_count,
        "page": page,
        "limit": limit,
        "leads": leads_out
    }

@router.delete("/{lead_id}")
def delete_scraped_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Delete a specific scraped lead (Admin only).
    """
    lead = db.query(ScrapedLead).filter(ScrapedLead.id == lead_id).first()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scraped lead not found."
        )
    db.delete(lead)
    db.commit()
    return {"message": "Scraped lead deleted successfully."}

@router.put("/{lead_id}", response_model=ScrapedLeadOut)
def update_scraped_lead(
    lead_id: int,
    lead_in: ScrapedLeadUpdate,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Update a specific scraped lead's outreach email status (Admin only).
    """
    lead = db.query(ScrapedLead).filter(ScrapedLead.id == lead_id).first()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scraped lead not found."
        )
    
    from datetime import datetime, timezone
    if lead_in.email_status is not None:
        lead.email_status = lead_in.email_status
        if lead_in.email_status == "sent":
            lead.email_sent_at = datetime.now(timezone.utc)
            
    if lead_in.email_sent_at is not None:
        lead.email_sent_at = lead_in.email_sent_at
        
    if lead_in.email_error is not None:
        lead.email_error = lead_in.email_error

    db.commit()
    db.refresh(lead)
    return lead

@router.post("/test-inject", response_model=ScrapedLeadOut)
def inject_test_lead(
    email: str = Query(..., description="The email address to inject"),
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Inject a fake lead to test the email worker (Admin only).
    """
    from datetime import datetime, timezone
    
    # Use default campaign
    from app.models.campaign import Campaign
    campaign = db.query(Campaign).filter(Campaign.name == "Default Autonomous Outreach").first()
    
    new_lead = ScrapedLead(
        bussiness_name="Test Business LLC",
        bussiness_email=email,
        bussiness_number="1234567890",
        bussiness_website="example.com",
        scraped_city="Test City",
        scraped_service="Test Service",
        category="Test Category",
        email_status="pending",
        campaign_id=campaign.id if campaign else None,
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_lead)
    db.commit()
    db.refresh(new_lead)
    return new_lead


class ScrapedLeadCreate(BaseModel):
    bussiness_name: str
    bussiness_email: Optional[str] = None
    bussiness_number: Optional[str] = None
    scraped_city: Optional[str] = None
    bussiness_website: Optional[str] = None
    scraped_service: Optional[str] = None
    category: Optional[str] = None
    rating: Optional[str] = "4.5"

@router.post("/", response_model=ScrapedLeadOut, status_code=status.HTTP_201_CREATED)
def create_scraped_lead(
    lead_in: ScrapedLeadCreate,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Manually create a new lead record in the database (Admin only).
    """
    from datetime import datetime, timezone
    
    if lead_in.bussiness_email and lead_in.bussiness_email.strip():
        existing = db.query(ScrapedLead).filter(
            func.lower(ScrapedLead.bussiness_email) == lead_in.bussiness_email.strip().lower()
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Lead with email '{lead_in.bussiness_email}' already exists in database."
            )

    new_lead = ScrapedLead(
        bussiness_name=lead_in.bussiness_name,
        bussiness_email=lead_in.bussiness_email.strip().lower() if lead_in.bussiness_email and lead_in.bussiness_email.strip() else None,
        bussiness_number=lead_in.bussiness_number,
        scraped_city=lead_in.scraped_city or "General",
        bussiness_website=lead_in.bussiness_website,
        scraped_service=lead_in.scraped_service or "Custom Service",
        category=lead_in.category or "B2B Prospect",
        rating=lead_in.rating or "4.5",
        email_status="pending",
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_lead)
    try:
        from app.models.notification import Notification
        db.add(Notification(
            title="New Lead Created",
            message=f"Lead '{new_lead.bussiness_name}' added to CRM database.",
            type="lead",
            read=False,
            link="/admin/dashboard/leads",
            created_at=datetime.now(timezone.utc)
        ))
    except Exception as notif_err:
        print("Failed to record lead creation notification:", notif_err)
    db.commit()
    db.refresh(new_lead)
    return new_lead


