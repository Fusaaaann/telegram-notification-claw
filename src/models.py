from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ReminderCreate(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    due_at: Optional[datetime] = None


class ReminderUpdate(BaseModel):
    text: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    due_at: Optional[datetime] = None
    done: Optional[bool] = None


class Reminder(BaseModel):
    id: int
    user_id: int
    text: str
    due_at: Optional[datetime]
    done: bool
    created_at: datetime
    updated_at: datetime


class ChatBinding(BaseModel):
    user_id: int
    chat_id: int
    created_at: datetime
