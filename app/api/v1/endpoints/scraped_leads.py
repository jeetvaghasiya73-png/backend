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
    Ultra-fast bulk upload for CSV or Excel (.csv, .xlsx, .xls) spreadsheet files into PostgreSQL/SQLite database.
    Flexible column resolver handles both snake_case and human Excel title columns with high performance bulk insertion.
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

        col_email = find_col("bussiness_email", "business_email", "email", "email address", "email_address", "e-mail", "contact_email")
        col_name = find_col("bussiness_name", "business_name", "company", "company name", "company_name", "name", "lead name", "lead_name", "title", "business name", "store_name")
        col_city = find_col("scraped_city", "city", "location", "place", "town", "scraped city")
        col_phone = find_col("bussiness_number", "business_number", "phone", "phone number", "phone_number", "mobile", "contact_number", "number", "business number")
        col_website = find_col("bussiness_website", "business_website", "website", "url", "site", "web", "business website")
        col_category = find_col("category", "industry", "type", "business_type", "sector")
        col_service = find_col("scraped_service", "service", "keyword", "scraped_keyword", "services", "scraped service")
        col_rating = find_col("rating", "score", "stars", "rate")
        col_address = find_col("bussiness_address", "business_address", "address", "full_address", "business address")
        col_area = find_col("bussiness_area", "business_area", "area")
        col_landmark = find_col("landmark")
        col_reviews = find_col("total_review", "total reviews", "reviews")

        records = df.to_dict(orient="records")
        
        # Pre-fetch all existing emails in ONE SQL query for O(1) in-memory check
        existing_emails = set(
            e[0].lower() for e in db.query(ScrapedLead.bussiness_email).filter(
                ScrapedLead.bussiness_email.isnot(None),
                ScrapedLead.bussiness_email != ""
            ).all()
        )
        
        seen_emails = set()
        leads_to_insert = []
        cities_inserted = set()
        skipped_count = 0
        now_utc = datetime.now(timezone.utc)
        
        for row in records:
            raw_email = str(row[col_email]).strip() if col_email and row.get(col_email) is not None and str(row[col_email]).lower() != "nan" else ""
            b_name = str(row[col_name]).strip() if col_name and row.get(col_name) is not None and str(row[col_name]).lower() != "nan" else ""
            
            if not b_name and not raw_email:
                skipped_count += 1
                continue
            
            first_email = None
            if raw_email:
                cleaned_email = raw_email.replace(";", ",").split(",")[0].strip().lower()
                if "@" in cleaned_email and cleaned_email not in seen_emails and cleaned_email not in existing_emails:
                    first_email = cleaned_email
                    seen_emails.add(first_email)
                    existing_emails.add(first_email)

            if not b_name:
                b_name = first_email.split("@")[0].title() if first_email else "Direct Prospect"

            city = str(row[col_city]).strip() if col_city and row.get(col_city) is not None and str(row[col_city]).lower() != "nan" else "Outreach"
            phone = str(row[col_phone]).strip() if col_phone and row.get(col_phone) is not None and str(row[col_phone]).lower() != "nan" else None
            website = str(row[col_website]).strip() if col_website and row.get(col_website) is not None and str(row[col_website]).lower() != "nan" else None
            category = str(row[col_category]).strip() if col_category and row.get(col_category) is not None and str(row[col_category]).lower() != "nan" else "B2B Lead"
            service = str(row[col_service]).strip() if col_service and row.get(col_service) is not None and str(row[col_service]).lower() != "nan" else "Digital Services"
            rating = str(row[col_rating]).strip() if col_rating and row.get(col_rating) is not None and str(row[col_rating]).lower() != "nan" else "4.5"
            address = str(row[col_address]).strip() if col_address and row.get(col_address) is not None and str(row[col_address]).lower() != "nan" else None
            area = str(row[col_area]).strip() if col_area and row.get(col_area) is not None and str(row[col_area]).lower() != "nan" else None
            landmark = str(row[col_landmark]).strip() if col_landmark and row.get(col_landmark) is not None and str(row[col_landmark]).lower() != "nan" else None
            total_review = str(row[col_reviews]).strip() if col_reviews and row.get(col_reviews) is not None and str(row[col_reviews]).lower() != "nan" else None

            leads_to_insert.append({
                "bussiness_name": b_name,
                "bussiness_email": first_email,
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
                "scraped_service": service,
                "email_status": "pending",
                "created_at": now_utc
            })
            if city:
                cities_inserted.add(city)
            
        if leads_to_insert:
            db.bulk_insert_mappings(ScrapedLead, leads_to_insert)
            try:
                from app.models.notification import Notification
                db.add(Notification(
                    title="Bulk Excel Import Completed",
                    message=f"Imported {len(leads_to_insert)} scraped leads into database ({len(cities_inserted)} cities).",
                    type="lead",
                    read=False,
                    link="/admin/dashboard/leads",
                    created_at=now_utc
                ))
            except Exception as notif_err:
                print("Failed to create upload notification:", notif_err)
            db.commit()

        return {
            "message": f"Successfully imported {len(leads_to_insert)} leads into database!",
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
    Export scraped leads to a CSV file (Admin only).
    """
    query = db.query(ScrapedLead).filter(
        ScrapedLead.bussiness_email != None,
        ScrapedLead.bussiness_email != ""
    )
    
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
    total = db.query(ScrapedLead).filter(
        ScrapedLead.bussiness_email != None,
        ScrapedLead.bussiness_email != ""
    ).count()

    city_counts = db.query(
        ScrapedLead.scraped_city,
        func.count(ScrapedLead.id).label("count")
    ).filter(
        ScrapedLead.bussiness_email != None,
        ScrapedLead.bussiness_email != "",
        ScrapedLead.scraped_city != None,
        ScrapedLead.scraped_city != ""
    ).group_by(ScrapedLead.scraped_city).order_by(func.count(ScrapedLead.id).desc()).limit(10).all()

    cities = [{"name": c[0], "value": c[1]} for c in city_counts]

    category_counts = db.query(
        func.coalesce(ScrapedLead.scraped_service, ScrapedLead.category, "General Business").label("cat"),
        func.count(ScrapedLead.id).label("count")
    ).filter(
        ScrapedLead.bussiness_email != None,
        ScrapedLead.bussiness_email != ""
    ).group_by(func.coalesce(ScrapedLead.scraped_service, ScrapedLead.category, "General Business")).order_by(func.count(ScrapedLead.id).desc()).limit(10).all()

    categories = [{"name": c[0], "value": c[1]} for c in category_counts]

    unique_cities = db.query(func.count(func.distinct(ScrapedLead.scraped_city))).filter(
        ScrapedLead.bussiness_email != None, ScrapedLead.bussiness_email != ""
    ).scalar() or 0

    unique_categories = db.query(func.count(func.distinct(ScrapedLead.scraped_service))).filter(
        ScrapedLead.bussiness_email != None, ScrapedLead.bussiness_email != ""
    ).scalar() or 0

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
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Retrieve all scraped leads (with email) with search, filters, and pagination (Admin only).
    """
    query = db.query(ScrapedLead).filter(
        ScrapedLead.bussiness_email != None,
        ScrapedLead.bussiness_email != ""
    )
    
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


