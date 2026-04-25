from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Deadline:
    course: str
    title: str
    due_date: datetime
    type: str  # "Abgabe" | "Klausur" | "Übung" | "Quiz"
    description: str = ""
    url: str = ""
    course_id: str = ""

    def is_upcoming(self, days: int = 14) -> bool:
        delta = self.due_date - datetime.now()
        return 0 <= delta.days <= days

    def days_remaining(self) -> int:
        return (self.due_date - datetime.now()).days

    def calendar_title(self) -> str:
        return f"[{self.course}] {self.type}: {self.title}"

    def __str__(self) -> str:
        return f"{self.calendar_title()} — fällig am {self.due_date.strftime('%d.%m.%Y %H:%M')}"
