from bcra_rag.composition import get_app
from bcra_rag.logconfig import configure_logging

configure_logging()
app = get_app().fastapi
