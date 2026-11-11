import os
import smtplib
from email.message import EmailMessage
from html import escape

from .models import Evaluation

COLORS = {"Candidatar": "#1a7f37", "Revisar": "#b26a00"}


def _card(ev: Evaluation) -> str:
    color = COLORS.get(ev.classification, "#666")
    j = ev.job
    return f"""
    <div style="border:1px solid #ddd;border-left:5px solid {color};border-radius:6px;padding:12px;margin:10px 0">
      <div style="font-size:16px"><b>{escape(j.title)}</b> – {escape(j.company)}</div>
      <div style="color:{color};margin:4px 0"><b>{ev.score}/100 · {ev.classification}</b></div>
      <div>📍 {escape(j.location or 'não informado')} · {escape(j.source)}</div>
      <div>✅ {escape(', '.join(ev.strengths) or '—')}</div>
      <div>⚠️ {escape(', '.join(ev.gaps) or 'nenhuma lacuna detectada')}</div>
      <div style="color:#555">🔎 {escape(ev.eligibility_reason)}</div>
      <div style="margin-top:8px"><a href="{escape(j.url)}">Abrir vaga</a></div>
    </div>"""


def build_email(evaluations: list[Evaluation], promoted: list[str], stats: dict, period: str) -> tuple[str, str]:
    subject = f"[Vagas {period}] {len(evaluations)} sugestões – {stats['date']}"
    answers = escape(os.environ.get("STANDARD_ANSWERS", "")).strip()
    sources = " · ".join(f"{k}: {v}" for k, v in stats["sources"].items())
    body = f"""<html><body style="font-family:Arial,sans-serif;max-width:680px">
      <h2>Vagas do turno ({period})</h2>
      <p>{stats['collected']} coletadas → {stats['title_ok']} com título compatível →
         {stats['new']} novas → {len(evaluations)} sugeridas.</p>
      {''.join(_card(ev) for ev in evaluations) or '<p>Nenhuma vaga passou nos filtros neste turno.</p>'}
      {f"<h3>Movidas para MONITOR</h3><p>{'<br>'.join(map(escape, promoted))}</p>" if promoted else ''}
      {f'<h3>Respostas padrão</h3><pre style="background:#f6f8fa;padding:10px">{answers}</pre>' if answers else ''}
      <p style="color:#888;font-size:12px">Fontes: {escape(sources)}</p>
    </body></html>"""
    return subject, body


def send_email(subject: str, html_body: str) -> None:
    sender = os.environ["GMAIL_ADDRESS"]
    msg = EmailMessage()
    msg["Subject"], msg["From"] = subject, sender
    msg["To"] = os.environ.get("NOTIFY_TO", sender)
    msg.set_content("Abra este e-mail em um cliente com suporte a HTML.")
    msg.add_alternative(html_body, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender, os.environ["GMAIL_APP_PASSWORD"])
        smtp.send_message(msg)
