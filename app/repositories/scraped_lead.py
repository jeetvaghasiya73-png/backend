from app.models.scraped_lead import ScrapedLead
from app.repositories.base import BaseRepository

class ScrapedLeadRepository(BaseRepository[ScrapedLead]):
    pass

scraped_lead_repo = ScrapedLeadRepository(ScrapedLead)
