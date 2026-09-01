from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_admin_user
from app.models.scraped_lead import ScrapedLead
from app.schemas.scraped_lead import ScrapedLeadOut, ScrapedLeadUpdate

import csv
import io
from fastapi.responses import StreamingResponse

router = APIRouter()

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

@router.get("/")
def get_scraped_leads(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=5000, description="Items per page"),
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

