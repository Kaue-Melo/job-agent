from datetime import date
from pathlib import Path

import pytest
import yaml

from agent.models import Job
from agent.scoring import Scorer

CFG = yaml.safe_load((Path(__file__).parents[1] / "config.yaml").read_text(encoding="utf-8"))


@pytest.fixture
def scorer():
    return Scorer(CFG, today=date(2026, 11, 10))


def job(description, title="Data Analyst", location="", company="Acme"):
    return Job(title=title, company=company, url="https://x", description=description, location=location)


IDEAL = """
We are a fully remote company hiring across LATAM. This is an independent contractor role.
What you'll do
Build Power BI dashboards and data models (star schema) for our commercial team.
Write SQL queries and maintain ETL pipelines. Partner with stakeholders to define KPIs.
Requirements
3+ years of experience with Power BI, DAX and SQL. Python is a plus.
Nice to have
dbt
Snowflake
"""


def test_vaga_ideal_vai_para_candidatar(scorer):
    ev = scorer.evaluate(job(IDEAL, title="BI Analyst", location="LATAM"))
    assert ev.eligibility == "elegivel"
    assert ev.classification == "Candidatar", ev
    assert "dbt (desejável)" in ev.gaps
    assert ev.required_years == 3


def test_localizacao_restrita_e_descartada(scorer):
    ev = scorer.evaluate(job(IDEAL, location="USA Only"))
    assert ev.eligibility == "inelegivel"
    assert ev.classification == "Descartar"


def test_autorizacao_de_trabalho_e_descartada(scorer):
    desc = "Power BI and SQL role. Candidates must be authorized to work in the United States."
    assert scorer.evaluate(job(desc, location="Remote")).eligibility == "inelegivel"


def test_idioma_exigido_e_descartado(scorer):
    desc = "Power BI analyst. Fluent German is required for client meetings."
    ev = scorer.evaluate(job(desc, location="Worldwide"))
    assert ev.eligibility == "inelegivel"
    assert "idioma" in ev.eligibility_reason


def test_localizacao_generica_vai_para_revisao(scorer):
    ev = scorer.evaluate(job("Power BI dashboards, SQL, DAX, stakeholders, KPIs, ETL.", location="Remote"))
    assert ev.eligibility == "revisar"
    assert ev.classification in ("Revisar", "Descartar")


def test_stack_diferente_e_muitos_anos_tem_score_baixo(scorer):
    desc = """Requirements
    8+ years of experience in analytics engineering.
    Strong dbt, Airflow, BigQuery and Looker skills. Spark experience."""
    ev = scorer.evaluate(job(desc, title="Analytics Engineer", location="Worldwide"))
    assert ev.score < 55
    assert ev.classification == "Descartar"


def test_skill_desejavel_na_mesma_linha_nao_conta_como_obrigatoria(scorer):
    req, opt = scorer.split_sections("Requirements\nStrong SQL.\nExperience with dbt is a plus.")
    assert "dbt" in opt and "dbt" not in req
    assert "SQL" in req
