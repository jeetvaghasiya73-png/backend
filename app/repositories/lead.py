from app.models.lead import Lead
from app.repositories.base import BaseRepository

class LeadRepository(BaseRepository[Lead]):
    pass

lead_repo = LeadRepository(Lead)
