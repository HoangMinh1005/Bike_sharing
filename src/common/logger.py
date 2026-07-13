import logging
import sys

def get_logger(name: str) -> logging.Logger:
    """
    Return a logger with a unified formatting (timestamp - level - name - message).
    Prevents duplicate handlers and log propagation issues.
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Define logging format
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Stream logs to stdout (highly compatible with Docker and standard logs logging)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Prevent logs from double-bubbling to parent logger
        logger.propagate = False
        
    return logger
