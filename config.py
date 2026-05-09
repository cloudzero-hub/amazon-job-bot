import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ── Required ──────────────────────────────────────────────────────────────
    DISCORD_TOKEN            = os.getenv("DISCORD_TOKEN", "")
    NOTIFICATION_CHANNEL_ID  = int(os.getenv("NOTIFICATION_CHANNEL_ID", "0"))

    # ── Optional ──────────────────────────────────────────────────────────────
    CHECK_INTERVAL_MINUTES   = int(os.getenv("CHECK_INTERVAL_MINUTES", "30"))
    LOCATION_FILTER          = os.getenv("LOCATION_FILTER", "")          # e.g. "Moncton" or "Fredericton"
    JOB_URL                  = os.getenv("JOB_URL", "https://hiring.amazon.ca/app#/jobSearch")
