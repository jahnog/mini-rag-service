"""BCRA CAMEX mini-RAG.

A question is answered from a frozen local dump of BCRA foreign-exchange
circulars. The page does not fetch bcra.gob.ar, and the chat model does not
answer from memory. Terms (chunk, hit, citation, silencio) are defined at the
top of use_cases/answer_query.py.

composition wires the process. api.routes is the HTTP surface. ui.gradio_app
is the page. use_cases.answer_query is one turn. jobs.ingest fills the index.
"""

__version__ = "0.1.0"
