"""The five interfaces the rest of the app depends on.

A chat turn uses the index (stored passages), the LLM (the written answer),
and the session (short chat memory). The catalog and the extractor run only
while the offline job is building the dump.
"""

from bcra_rag.ports.catalog import CatalogPort
from bcra_rag.ports.extractor import ExtractorPort
from bcra_rag.ports.index import IndexPort
from bcra_rag.ports.llm import LlmPort
from bcra_rag.ports.session import SessionStore

__all__ = [
    "CatalogPort",
    "ExtractorPort",
    "IndexPort",
    "LlmPort",
    "SessionStore",
]
