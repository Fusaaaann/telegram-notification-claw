import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional at runtime
    def load_dotenv() -> None:
        return None

load_dotenv()

@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

    admin_token: str = os.getenv("REMINDER_ADMIN_TOKEN", "").strip()

    db_path: str = os.getenv("REMINDER_DB_PATH", "").strip()

    blob_path: str = os.getenv("REMINDER_BLOB_PATH", "reminders.sqlite3").strip()
    blob_access: str = os.getenv("REMINDER_BLOB_ACCESS", "private").strip().lower()
    blob_token: str = os.getenv("REMINDER_BLOB_TOKEN", "").strip()
    reminder_timezone: str = os.getenv("REMINDER_TIMEZONE", "UTC").strip() or "UTC"

    host: str = os.getenv("REMINDER_API_HOST", "0.0.0.0").strip()
    port: int = int(os.getenv("REMINDER_API_PORT", "8088"))

    def zoneinfo(self) -> ZoneInfo:
        return ZoneInfo(self.reminder_timezone)

settings = Settings()
