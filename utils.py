import os
import logging
from datetime import datetime

# Ensure log directories exist
os.makedirs("data/logs", exist_ok=True)
os.makedirs("data/logs/Errors", exist_ok=True)

# Timestamp for filenames
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
log_dir = os.path.join("data", "logs")
error_log_dir = os.path.join(log_dir, "Errors")
general_log = os.path.join(log_dir, f"resume_parser{ts}.log")
error_log   = os.path.join(error_log_dir, f"error_resume_parser{ts}.log")

# --- Logging Setup ---
def setup_logging():
    """
    Set up logging only once for the whole application.
    """
    root_logger = logging.getLogger()
    if getattr(root_logger, '_logging_configured', False):
        return
    root_logger.setLevel(logging.INFO)
    # Remove all handlers if any (avoid duplicate logs)
    while root_logger.handlers:
        root_logger.handlers.pop()
    # General log handler
    file_handler = logging.FileHandler(general_log, mode="a")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    # Error log handler
    err_handler = logging.FileHandler(error_log, mode="a")
    err_handler.setLevel(logging.ERROR)
    err_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    # Console handler
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    # Add handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(err_handler)
    root_logger.addHandler(stream_handler)
    root_logger._logging_configured = True

setup_logging()

def get_logger(name: str = __name__) -> logging.Logger:
    """
    Get a logger with the given name. Logging is configured globally.
    """
    logger = logging.getLogger(name)
    # Avoid log message duplication
    logger.propagate = True
    return logger
