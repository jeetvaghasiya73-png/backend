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

@router.post("/upload")
def upload_scraped_leads(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Upload a CSV or Excel (.csv, .xlsx, .xls) file containing lead records and insert them into the database.
    Flexible column resolver handles both snake_case and human Excel title columns.
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
        
        # Replace NaNs with None
        df = df.replace({np.nan: None})
        
        # Pre-fetch all existing emails in ONE query for O(1) in-memory check
        existing_emails = set(
            e[0].lower() for e in db.query(ScrapedLead.bussiness_email).filter(
                ScrapedLead.bussiness_email.isnot(None),
                ScrapedLead.bussiness_email != ""
            ).all()
        )
        
        inserted_count = 0
        skipped_count = 0
        total_rows = len(df)
        cities_inserted = set()
        seen_emails = set()
        
        for _, row in df.iterrows():
            raw_email = get_val(row, "bussiness_email", "Business Email", "business_email", "Email", "email", "Email Address", "email_address")
            b_name = get_val(row, "bussiness_name", "Business Name", "business_name", "Name", "name", "Company", "company", "Lead Name", "Title", "title")
            
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

            city = get_val(row, "scraped_city", "City", "city", "location", "Location") or "Outreach"
            phone = get_val(row, "bussiness_number", "Business Number", "business_number", "Phone", "phone", "Mobile", "mobile")
            area = get_val(row, "bussiness_area", "Business Area", "business_area", "Area")
            rating = get_val(row, "rating", "Rating", "Score", "score") or "4.5"
            landmark = get_val(row, "landmark", "Landmark")
            total_review = get_val(row, "total_review", "Total Reviews", "Total Review", "Reviews")
            building = get_val(row, "building", "Building")
            pincode = get_val(row, "pincode", "Pincode")
            website = get_val(row, "bussiness_website", "Business Website", "business_website", "Website", "url", "URL")
            category = get_val(row, "category", "Category", "Industry", "industry") or "B2B Lead"
            address = get_val(row, "bussiness_address", "Business Address", "business_address", "Address")
            service = get_val(row, "service", "Services", "Service") or "Digital Services"
            scraped_service = get_val(row, "scraped_service", "Scraped Keyword", "Keyword", "scraped_keyword") or service
                
            new_lead = ScrapedLead(
                bussiness_name=b_name,
                bussiness_email=first_email,
                bussiness_number=phone,
                bussiness_area=area,
                rating=rating,
                landmark=landmark,
                total_review=total_review,
                building=building,
                pincode=pincode,
                bussiness_website=website,
                category=category,
                bussiness_address=address,
                service=service,
                scraped_city=city,
                scraped_service=scraped_service,
                email_status="pending"
            )
            db.add(new_lead)
            inserted_count += 1
            if city:
                cities_inserted.add(city)
            
        db.commit()
        return {
            "message": f"Successfully imported {inserted_count} leads into database!",
            "inserted": inserted_count,
            "skipped": skipped_count,
            "total_rows": total_rows,
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
    db.commit()
    db.refresh(new_lead)
    return new_lead


