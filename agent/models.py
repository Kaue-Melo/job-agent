import re
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Job:
    title: str
    company: str
    url: str
    description: str
    location: str = ""
    source: str = ""
    published: datetime | None = None

    @property
    def key(self) -> str:
        """Chave para deduplicar a mesma vaga vinda de fontes diferentes."""
        return normalize(f"{self.company}|{self.title}")


@dataclass
class Evaluation:
    job: Job
    score: int
    classification: str          # Candidatar | Revisar | Descartar
    eligibility: str             # elegivel | revisar | inelegivel
    eligibility_reason: str
    strengths: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    required_years: int | None = None
    breakdown: dict = field(default_factory=dict)


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9|]+", " ", (text or "").lower()).strip()


def compile_any(patterns: list[str]) -> re.Pattern:
    """Une uma lista de regex em um único padrão case-insensitive."""
    return re.compile("|".join(f"(?:{p})" for p in patterns), re.IGNORECASE)
