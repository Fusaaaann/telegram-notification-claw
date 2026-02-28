from __future__ import annotations

from src.api import create_api
from src.config import settings
from src.db import ReminderDB

db = ReminderDB.from_settings(settings)
app = create_api(db)
