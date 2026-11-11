"""Fontes gratuitas e permitidas de vagas remotas.

Cada coletor devolve uma lista de Job. Se uma fonte falhar (fora do ar,
formato mudou), o erro é registrado e as outras continuam rodando.
LinkedIn, Glassdoor e Jobright entram na fase 2, pelos alertas no Gmail.
"""
import html
import logging
import re
from datetime import datetime, timezone

import feedparser
import requests

from .models import Job

log = logging.getLogger(__name__)
HEADERS = {"User-Agent": "job-agent/1.0 (+https://github.com/Kaue-Melo)"}
TIMEOUT = 30


def clean_html(raw: str | None) -> str:
    text = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>|<li[^>]*>", "\n", raw or "", flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def parse_date(value) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000 if value > 1e12 else value, tz=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def fetch_remotive() -> list[Job]:
    # A Remotive pede poucas chamadas por dia: 2 execuções estão dentro do uso razoável.
    r = requests.get("https://remotive.com/api/remote-jobs", params={"category": "data"},
                     headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return [
        Job(title=j.get("title", ""), company=j.get("company_name", ""), url=j.get("url", ""),
            description=clean_html(j.get("description")),
            location=j.get("candidate_required_location", ""), source="Remotive",
            published=parse_date(j.get("publication_date")))
        for j in r.json().get("jobs", [])
    ]


def fetch_remoteok() -> list[Job]:
    r = requests.get("https://remoteok.com/api", headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    jobs = []
    for j in r.json():
        if not isinstance(j, dict) or "position" not in j:   # 1º item é o aviso legal
            continue
        jobs.append(Job(
            title=j.get("position", ""), company=j.get("company", ""),
            url=j.get("url") or j.get("apply_url", ""), description=clean_html(j.get("description")),
            location=j.get("location", ""), source="RemoteOK",
            published=parse_date(j.get("date") or j.get("epoch"))))
    return jobs


def fetch_weworkremotely() -> list[Job]:
    r = requests.get("https://weworkremotely.com/remote-jobs.rss", headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    jobs = []
    for e in feedparser.parse(r.content).entries:
        company, _, title = e.get("title", "").partition(": ")
        if not title:
            company, title = "", company
        published = (datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
                     if e.get("published_parsed") else None)
        jobs.append(Job(title=title, company=company, url=e.get("link", ""),
                        description=clean_html(e.get("summary")), location=e.get("region", ""),
                        source="We Work Remotely", published=published))
    return jobs


def fetch_himalayas(pages: int = 5, page_size: int = 20) -> list[Job]:
    jobs = []
    for offset in range(0, pages * page_size, page_size):
        r = requests.get("https://himalayas.app/jobs/api", params={"limit": page_size, "offset": offset},
                         headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        batch = r.json().get("jobs", [])
        if not batch:
            break
        for j in batch:
            restrictions = j.get("locationRestrictions") or []
            names = [x if isinstance(x, str) else x.get("name", "") for x in restrictions]
            jobs.append(Job(
                title=j.get("title", ""), company=j.get("companyName", ""),
                url=j.get("applicationLink") or j.get("guid", ""),
                description=clean_html(j.get("description") or j.get("excerpt")),
                # Sem restrição na Himalayas = aceita qualquer país
                location=", ".join(n for n in names if n) or "Worldwide",
                source="Himalayas", published=parse_date(j.get("pubDate"))))
    return jobs


SOURCES = {
    "remotive": fetch_remotive,
    "remoteok": fetch_remoteok,
    "weworkremotely": fetch_weworkremotely,
    "himalayas": fetch_himalayas,
}


def collect(source_names: list[str]) -> tuple[list[Job], dict[str, str]]:
    """Roda todas as fontes. Devolve (vagas, status por fonte)."""
    jobs, status = [], {}
    for name in source_names:
        try:
            found = SOURCES[name]()
            jobs.extend(found)
            status[name] = f"{len(found)} vagas"
        except Exception as exc:  # uma fonte quebrada não derruba as outras
            log.warning("Fonte %s falhou: %s", name, exc)
            status[name] = f"ERRO: {exc.__class__.__name__}"
    return jobs, status
