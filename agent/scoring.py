"""Score de compatibilidade (0-100) baseado em regras, sem LLM.

Componentes (pesos no config.yaml):
  hard_skills       skills obrigatórias da vaga que você tem
  seniority         anos de experiência exigidos vs. os seus
  responsibilities  responsabilidades típicas do seu perfil
  nice_to_have      skills desejáveis que você tem
  context           aceita Brasil explicitamente / contrato PJ
"""
import re
from datetime import date

from .eligibility import EligibilityChecker
from .models import Evaluation, Job, compile_any

LEVEL_VALUE = {"have": 1.0, "partial": 0.5, "missing": 0.0}
YEARS_RE = re.compile(
    r"(\d{1,2})\s*(?:\+|plus)?\s*(?:(?:-|–|to)\s*\d{1,2}\s*)?\+?\s*years?(?:'s)?\b[^.\n]{0,60}?experience",
    re.IGNORECASE,
)
LINE_SPLIT = re.compile(r"\n+|(?<=[.;])\s+|•")


class Scorer:
    def __init__(self, cfg: dict, today: date | None = None):
        self.cfg = cfg
        sc = cfg["scoring"]
        self.weights = sc["weights"]
        self.thresholds = sc["thresholds"]
        self.resp_full = sc["responsibilities_for_full_score"]
        self.nice_marker = compile_any(sc["nice_to_have_markers"])
        self.required_marker = compile_any(sc["required_section_markers"])
        self.skills = [
            (s["name"], s["level"], s["weight"], compile_any(s["patterns"])) for s in cfg["skills"]
        ]
        self.responsibilities = {k: compile_any(v) for k, v in cfg["responsibilities"].items()}
        self.contractor = compile_any(cfg["eligibility"]["contractor_signals"])
        self.eligibility = EligibilityChecker(cfg["eligibility"])

        start = date.fromisoformat(cfg["profile"]["career_start"])
        self.my_years = ((today or date.today()) - start).days / 365.25

    # ---------- partes do texto ----------
    def split_sections(self, text: str) -> tuple[str, str]:
        """Separa o texto em (obrigatório, desejável), linha a linha."""
        required, optional, in_optional = [], [], False
        for line in LINE_SPLIT.split(text):
            if not line.strip():
                continue
            is_heading = len(line.split()) <= 6
            if self.required_marker.search(line) and not self.nice_marker.search(line):
                in_optional = False
            if self.nice_marker.search(line):
                optional.append(line)
                if is_heading:
                    in_optional = True
            elif in_optional:
                optional.append(line)
            else:
                required.append(line)
        return "\n".join(required), "\n".join(optional)

    def skills_in(self, text: str) -> list[tuple[str, str, int]]:
        return [(n, lvl, w) for n, lvl, w, rx in self.skills if text and rx.search(text)]

    @staticmethod
    def coverage(found: list, default: float) -> float:
        if not found:
            return default
        total = sum(w for _, _, w in found)
        return sum(w * LEVEL_VALUE[lvl] for _, lvl, w in found) / total

    @staticmethod
    def required_years(text: str) -> int | None:
        values = [int(m.group(1)) for m in YEARS_RE.finditer(text)]
        values = [v for v in values if 0 < v <= 15]
        return max(values) if values else None

    # ---------- avaliação ----------
    def evaluate(self, job: Job) -> Evaluation:
        text = f"{job.title}\n{job.description}"
        elig = self.eligibility.check(job)

        req_text, opt_text = self.split_sections(text)
        req_skills = self.skills_in(req_text)
        req_names = {n for n, _, _ in req_skills}
        opt_skills = [s for s in self.skills_in(opt_text) if s[0] not in req_names]

        hard = self.coverage(req_skills, default=0.5)
        nice = self.coverage(opt_skills, default=0.7)

        years = self.required_years(text)
        if years is None:
            seniority = 0.8
        elif years <= self.my_years:
            seniority = 1.0
        elif years <= self.my_years + 2:
            seniority = 0.5
        else:
            seniority = 0.0

        resp_hits = [k for k, rx in self.responsibilities.items() if rx.search(text)]
        responsibilities = min(1.0, len(resp_hits) / self.resp_full)

        context = 0.6 + (0.3 if elig.location_ok else 0) + (0.1 if self.contractor.search(text) else 0)

        parts = {
            "hard_skills": hard,
            "seniority": seniority,
            "responsibilities": responsibilities,
            "nice_to_have": nice,
            "context": min(1.0, context),
        }
        score = round(sum(self.weights[k] * v for k, v in parts.items()))

        if elig.status == "inelegivel":
            classification = "Descartar"
        elif score >= self.thresholds["apply"] and elig.status == "elegivel":
            classification = "Candidatar"
        elif score >= self.thresholds["review"]:
            classification = "Revisar"
        else:
            classification = "Descartar"

        strengths = [n for n, lvl, _ in req_skills + opt_skills if lvl == "have"]
        gaps = [n for n, lvl, _ in req_skills if lvl != "have"]
        gaps += [f"{n} (desejável)" for n, lvl, _ in opt_skills if lvl != "have"]
        if years and years > self.my_years:
            gaps.append(f"Pede {years}+ anos de experiência")

        return Evaluation(
            job=job,
            score=score,
            classification=classification,
            eligibility=elig.status,
            eligibility_reason=elig.reason,
            strengths=strengths,
            gaps=gaps,
            required_years=years,
            breakdown={k: round(v, 2) for k, v in parts.items()},
        )
