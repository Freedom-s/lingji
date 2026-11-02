"""Gunicorn entry point for the RAGFlow API."""

from concurrent.futures import ThreadPoolExecutor

from api.ragflow_server import initialize_application, update_progress


application = initialize_application(start_background_tasks=False)

# Each Gunicorn worker owns one lightweight progress updater.  The existing
# Redis lock in update_progress() prevents workers from updating the same data
# concurrently.
_progress_executor = ThreadPoolExecutor(max_workers=1)
_progress_executor.submit(update_progress)

