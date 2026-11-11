"""Leitura e escrita na planilha "Monitor de Candidatura".

Fluxo:
  1. O agente escreve as vagas sugeridas na aba TRIAGEM.
  2. Você se candidata e marca a caixa APLICADO.
  3. Na execução seguinte, a linha vai para a MONITOR (colunas C a H),
     no padrão que você já usa. A coluna A (fórmula de SLA) nunca é
     sobrescrita: se a linha não tiver fórmula, ela é copiada da linha 2.
"""
import json
import os

import gspread

from .models import Evaluation, normalize

TRIAGEM_HEADER = [
    "DATA ENCONTRADA", "SCORE", "CLASSIFICAÇÃO", "TÍTULO DE VAGA", "EMPRESA", "LINK DA VAGA",
    "LOCALIZAÇÃO", "FONTE", "PONTOS FORTES", "LACUNAS", "ELEGIBILIDADE", "APLICADO",
    "MOVIDO PARA MONITOR",
]
COL = {name: i for i, name in enumerate(TRIAGEM_HEADER)}


class Sheet:
    def __init__(self, cfg: dict):
        creds = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
        self.book = gspread.service_account_from_dict(creds).open_by_key(os.environ["SHEET_ID"])
        self.monitor = self.book.worksheet(cfg["sheets"]["monitor_tab"])
        self.triagem = self._ensure_triagem(cfg["sheets"]["triagem_tab"])

    def _ensure_triagem(self, name: str) -> gspread.Worksheet:
        try:
            return self.book.worksheet(name)
        except gspread.WorksheetNotFound:
            ws = self.book.add_worksheet(name, rows=2000, cols=len(TRIAGEM_HEADER))
            ws.update([TRIAGEM_HEADER], "A1")
            ws.freeze(rows=1)
            col = COL["APLICADO"]
            self.book.batch_update({"requests": [{"setDataValidation": {
                "range": {"sheetId": ws.id, "startRowIndex": 1, "endRowIndex": 2000,
                          "startColumnIndex": col, "endColumnIndex": col + 1},
                "rule": {"condition": {"type": "BOOLEAN"}, "showCustomUi": True},
            }}]})
            return ws

    # ---------- deduplicação ----------
    def known_keys(self) -> set[str]:
        """Links e empresa|título que já estão em TRIAGEM ou MONITOR."""
        keys = set()
        for row in self.triagem.get_all_values()[1:]:
            keys.add(row[COL["LINK DA VAGA"]].strip())
            keys.add(normalize(f"{row[COL['EMPRESA']]}|{row[COL['TÍTULO DE VAGA']]}"))
        for row in self.monitor.get_all_values()[1:]:
            if len(row) >= 6 and row[2]:
                keys.add(row[5].strip())                      # F: link
                keys.add(normalize(f"{row[4]}|{row[3]}"))     # E: empresa | D: título
        keys.discard("")
        return keys

    # ---------- escrita ----------
    def add_to_triagem(self, evaluations: list[Evaluation], today: str) -> None:
        if not evaluations:
            return
        rows = [[
            today, ev.score, ev.classification, ev.job.title, ev.job.company, ev.job.url,
            ev.job.location, ev.job.source, ", ".join(ev.strengths), ", ".join(ev.gaps),
            ev.eligibility_reason, False, "",
        ] for ev in evaluations]
        self.triagem.append_rows(rows, value_input_option="USER_ENTERED",
                                 table_range="A1")

    def promote_applied(self, today: str) -> list[str]:
        """Move para a MONITOR as vagas marcadas como APLICADO."""
        values = self.triagem.get_all_values()
        promoted = []
        for i, row in enumerate(values[1:], start=2):
            row += [""] * (len(TRIAGEM_HEADER) - len(row))
            if row[COL["APLICADO"]].upper() != "TRUE" or row[COL["MOVIDO PARA MONITOR"]]:
                continue
            target = len(self.monitor.col_values(3)) + 1        # 1ª linha com coluna C vazia
            self.monitor.update(
                [[today, row[COL["TÍTULO DE VAGA"]], row[COL["EMPRESA"]],
                  row[COL["LINK DA VAGA"]], "Aberta", "Candidatado"]],
                f"C{target}:H{target}", value_input_option="USER_ENTERED")
            self._ensure_sla_formula(target)
            self.triagem.update_cell(i, COL["MOVIDO PARA MONITOR"] + 1, today)
            promoted.append(f"{row[COL['TÍTULO DE VAGA']]} – {row[COL['EMPRESA']]}")
        return promoted

    def _ensure_sla_formula(self, row: int) -> None:
        cell = self.monitor.acell(f"A{row}", value_render_option="FORMULA").value
        if cell:
            return
        # Copia a fórmula da linha 2 (o Sheets ajusta as referências sozinho)
        self.book.batch_update({"requests": [{"copyPaste": {
            "source": {"sheetId": self.monitor.id, "startRowIndex": 1, "endRowIndex": 2,
                       "startColumnIndex": 0, "endColumnIndex": 1},
            "destination": {"sheetId": self.monitor.id, "startRowIndex": row - 1, "endRowIndex": row,
                            "startColumnIndex": 0, "endColumnIndex": 1},
            "pasteType": "PASTE_FORMULA",
        }}]})
