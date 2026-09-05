from bcra_rag.composition import get_app
from bcra_rag.logconfig import configure_logging
from bcra_rag.settings import Settings

configure_logging(log_file=Settings().data_dir / "logs" / "chat.log")
app = get_app().fastapi
