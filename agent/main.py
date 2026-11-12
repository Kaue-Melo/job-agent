"""Executa um turno do agente.

    python -m agent.main            # execução completa (planilha + e-mail)
    python -m agent.main --dry-run  # só coleta e pontua, imprime no terminal
"""
import argparse
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from .models import compile_any
from .scoring import Scorer
from .sources import collect

log = logging.getLogger("agent")
CONFIG_PATH = Path(__file__).parents[1] / "config.yaml"
PRIORITY = {"Candidatar": 0, "Revisar": 1}


def load_config(path: Path = CONFIG_PATH) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def run(dry_run: bool = False) -> None:
    cfg = load_config()
    tz = ZoneInfo(cfg["run"]["timezone"])
    now = datetime.now(tz)
    today = now.strftime("%d/%m/%Y")
    period = "manhã" if now.hour < 15 else "noite"

    # 1) Coleta
    jobs, source_status = collect(cfg)
    collected = len(jobs)

    # 2) Recência, título e duplicadas dentro do próprio lote
    cutoff = datetime.now(timezone.utc) - timedelta(days=cfg["run"]["max_age_days"])
    include, exclude = compile_any(cfg["titles"]["include"]), compile_any(cfg["titles"]["exclude"])
    domestic_loc = compile_any(cfg["domestic"]["location"])
    domestic_title = compile_any(cfg["domestic"]["title"])
    seen, filtered, domestic = set(), [], 0
    for j in jobs:
        if j.published and j.published < cutoff:
            continue
        # Vagas só no Brasil ficam de fora (antes do filtro de título,
        # porque "Analista de BI" casaria com '\bbi\b')
        if domestic_loc.search(j.location or "") or domestic_title.search(j.title):
            domestic += 1
            continue
        if not include.search(j.title) or exclude.search(j.title):
            continue
        if j.url in seen or j.key in seen:
            continue
        seen.update({j.url, j.key})
        filtered.append(j)
    title_ok = len(filtered)

    # 3) Planilha: move aplicadas e remove o que já foi sugerido/aplicado
    sheet, promoted = None, []
    if not dry_run:
        from .sheets import Sheet
        sheet = Sheet(cfg)
        promoted = sheet.promote_applied(today)
        known = sheet.known_keys()
        filtered = [j for j in filtered if j.url not in known and j.key not in known]

    # 4) Score e seleção
    scorer = Scorer(cfg, today=now.date())
    evaluations = [scorer.evaluate(j) for j in filtered]
    candidates = [e for e in evaluations if e.classification in PRIORITY]
    candidates.sort(key=lambda e: (PRIORITY[e.classification], -e.score))
    selected = candidates[: cfg["run"]["max_per_run"]]

    stats = {"date": today, "collected": collected, "domestic": domestic, "title_ok": title_ok,
             "new": len(filtered), "sources": source_status}
    log.info("Resumo: %s | sugeridas: %d", stats, len(selected))

    # Log de avaliações: aparece no terminal e no log do GitHub Actions
    for e in sorted(evaluations, key=lambda e: -e.score):
        log.info("%3d %-10s %-45s | %-20s | %-10s | %s", e.score, e.classification,
                 e.job.title[:45], e.job.company[:20], e.job.source[:10], e.eligibility_reason[:60])

    if dry_run:
        return

    # 5) Registro e aviso
    from .notify import build_email, send_email
    sheet.add_to_triagem(selected, today)
    send_email(*build_email(selected, promoted, stats, period))


def main() -> None:
    parser = argparse.ArgumentParser(description="Agente de vagas internacionais")
    parser.add_argument("--dry-run", action="store_true", help="não escreve na planilha nem envia e-mail")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
