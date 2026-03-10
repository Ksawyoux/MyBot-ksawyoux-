"""
scripts/memory_profiler.py — Simple memory footprint check
Run this to see how much RAM the Python process is using given the ML models.
"""

import os
import psutil
from src.utils.logging import get_logger

logger = get_logger(__name__)

def log_memory_usage(tag: str = "Memory Profile"):
    """Log current process memory usage."""
    process = psutil.Process(os.getpid())
    # memory_info().rss is Resident Set Size in bytes
    mem_mb = process.memory_info().rss / 1024 / 1024
    logger.info("[%s] Python process using %.2f MB of RAM", tag, mem_mb)

if __name__ == "__main__":
    from src.utils.embeddings import _get_model
    
    log_memory_usage("Baseline")
    
    logger.info("Loading semantic embedding model (all-MiniLM-L6-v2)...")
    model = _get_model()
    
    log_memory_usage("After Model Load")
    
    if model:
        logger.info("Model loaded successfully. The memory delta shows the model's footprint.")
    else:
        logger.error("Failed to load model.")
