import logging
import os
from datetime import datetime


# =========================================================
# LOG DIRECTORY
# =========================================================

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)


# =========================================================
# FORMATTER
# =========================================================

class AgentFormatter(logging.Formatter):

    def format(self, record):
        record.asctime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return super().format(record)


# =========================================================
# FACTORY
# =========================================================

def get_agent_logger(agent_name: str) -> logging.Logger:
    """
    Returns a logger that writes to both:
    - logs/<agent_name>.log  (agent-specific file)
    - logs/all_agents.log    (combined file)
    """

    logger = logging.getLogger(f"agent.{agent_name}")

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    fmt = AgentFormatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )

    date_str = datetime.now().strftime("%Y-%m-%d")

    # --- agent-specific file ------------------------------
    agent_handler = logging.FileHandler(
        os.path.join(LOG_DIR, f"{date_str}_{agent_name}.log"),
        encoding="utf-8",
    )
    agent_handler.setLevel(logging.DEBUG)
    agent_handler.setFormatter(fmt)

    # --- combined file ------------------------------------
    combined_handler = logging.FileHandler(
        os.path.join(LOG_DIR, f"{date_str}_all_agents.log"),
        encoding="utf-8",
    )
    combined_handler.setLevel(logging.DEBUG)
    combined_handler.setFormatter(fmt)

    logger.addHandler(agent_handler)
    logger.addHandler(combined_handler)
    logger.propagate = False

    return logger