from app.models.testimonial import Testimonial
from app.repositories.base import BaseRepository

class TestimonialRepository(BaseRepository[Testimonial]):
    pass

testimonial_repo = TestimonialRepository(Testimonial)
