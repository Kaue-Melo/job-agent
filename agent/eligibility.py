import re
from dataclasses import dataclass

from .models import Job, compile_any


@dataclass
class EligibilityResult:
    status: str          # elegivel | revisar | inelegivel
    reason: str
    location_ok: bool    # vaga sinaliza explicitamente que aceita o Brasil


def _snippet(text: str, match: re.Match, width: int = 50) -> str:
    start, end = max(0, match.start() - 15), min(len(text), match.end() + width)
    return " ".join(text[start:end].split())


class EligibilityChecker:
    def __init__(self, cfg: dict):
        self.location_ok = compile_any(cfg["location_ok"])
        self.location_generic = compile_any(cfg["location_generic"])
        self.green = compile_any(cfg["green_flags"])
        self.red = [(r["reason"], re.compile(r["pattern"], re.I)) for r in cfg["red_flags"]]
        self.review = [(r["reason"], re.compile(r["pattern"], re.I)) for r in cfg["review_flags"]]
        self.language = [re.compile(p, re.I) for p in cfg["language_block"]]

    def check(self, job: Job) -> EligibilityResult:
        location = (job.location or "").strip()
        text = f"{job.title}\n{job.description}"

        loc_explicit_ok = bool(location and self.location_ok.search(location))
        loc_generic = bool(self.location_generic.search(location.lower().strip(" -,")))

        # 1) Localização estruturada que não inclui o Brasil
        if location and not loc_explicit_ok and not loc_generic:
            return EligibilityResult("inelegivel", f"Localização restrita: {location}", False)

        # 2) Frases eliminatórias na descrição
        for reason, rx in self.red:
            if m := rx.search(text):
                return EligibilityResult("inelegivel", f'{reason}: "{_snippet(text, m)}"', False)

        # 3) Idioma que você não domina
        for rx in self.language:
            if m := rx.search(text):
                return EligibilityResult("inelegivel", f'Exige idioma: "{_snippet(text, m, 20)}"', False)

        location_ok = loc_explicit_ok or bool(self.green.search(text))

        # 4) Sinais que pedem revisão humana
        for reason, rx in self.review:
            if m := rx.search(text):
                return EligibilityResult("revisar", f'{reason}: "{_snippet(text, m)}"', location_ok)

        if location_ok:
            return EligibilityResult("elegivel", "Aceita candidatos do Brasil/LATAM/mundo", True)
        return EligibilityResult("revisar", "Localização não especificada", False)
