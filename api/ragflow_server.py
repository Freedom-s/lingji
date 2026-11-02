import logging
import os
import signal
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

from werkzeug.serving import run_simple

from api import settings, utils
from api.apps import app
from api.db.db_models import init_database_tables as init_web_db
from api.db.init_data import init_llm_factory, init_web_data
from api.db.runtime_config import RuntimeConfig
from api.db.services.document_service import DocumentService
from api.utils import show_configs
from api.utils.log_utils import initRootLogger
from api.versions import get_ragflow_version
from rag.settings import print_rag_settings
from rag.utils.redis_conn import RedisDistributedLock

initRootLogger("ragflow_server")

stop_event = threading.Event()
_progress_executor = None


def update_progress():
    redis_lock = RedisDistributedLock("update_progress", timeout=60)
    while not stop_event.is_set():
        try:
            if not redis_lock.acquire():
                continue
            DocumentService.update_progress()
            stop_event.wait(6)
        except Exception:
            logging.exception("update_progress exception")
        finally:
            redis_lock.release()


def signal_handler(sig, frame):
    logging.info("Received interrupt signal, shutting down...")
    stop_event.set()
    time.sleep(1)
    sys.exit(0)


def initialize_application(start_background_tasks=True):
    """Initialize the RAGFlow application for either Gunicorn or the dev runner."""
    global _progress_executor

    logging.info(r"""
 ___       ___  ________   ________                     ___  ___
|\  \     |\  \|\   ___  \|\   ____\                   |\  \|\  \
\ \  \    \ \  \ \  \\ \  \ \  \___|   ____________    \ \  \ \  \
 \ \  \    \ \  \ \  \\ \  \ \  \  ___|\____________\__ \ \  \ \  \
  \ \  \____\ \  \ \  \\ \  \ \  \|\  \|____________|\  \\_\  \ \  \
   \ \_______\ \__\ \__\\ \__\ \_______\            \ \________\ \__\
    \|_______|\|__|\|__| \|__|\|_______|             \|________|\|__|
    """)
    logging.info(f"RAGFlow base version: {get_ragflow_version()}")
    logging.info(f"project base: {utils.file_utils.get_project_base_directory()}")
    show_configs()

    settings.init_settings()
    print_rag_settings()
    init_web_db()
    init_web_data()

    RuntimeConfig.init_env()
    RuntimeConfig.init_config(JOB_SERVER_HOST=settings.HOST_IP, HTTP_PORT=settings.HOST_PORT)

    if start_background_tasks:
        _progress_executor = ThreadPoolExecutor(max_workers=1)
        _progress_executor.submit(update_progress)

    return app


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default=False, help="RAGFlow version", action="store_true")
    parser.add_argument("--debug", default=False, help="debug mode", action="store_true")
    args = parser.parse_args()
    if args.version:
        print(get_ragflow_version())
        sys.exit(0)

    RuntimeConfig.DEBUG = args.debug
    if RuntimeConfig.DEBUG:
        logging.info("run on debug mode")

    initialize_application(start_background_tasks=True)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # start http server
    try:
        logging.info("RAGFlow HTTP server start...")
        run_simple(
            hostname=settings.HOST_IP,
            port=settings.HOST_PORT,
            application=app,
            threaded=True,
            use_reloader=RuntimeConfig.DEBUG,
            use_debugger=RuntimeConfig.DEBUG,
        )
    except Exception:
        traceback.print_exc()
        stop_event.set()
        time.sleep(1)
        os.kill(os.getpid(), signal.SIGKILL)
