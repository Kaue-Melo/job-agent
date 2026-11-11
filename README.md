# Job Agent – vagas remotas internacionais de dados

Agente que roda duas vezes por dia (12h e 19h, horário de São Paulo), coleta vagas remotas de BI e análise de dados, filtra as que aceitam candidatos do Brasil, calcula um score de compatibilidade com o meu perfil e envia as melhores por e-mail. A candidatura é feita por mim, e o acompanhamento fica no Google Sheets.

```
Fontes (Remotive, RemoteOK, We Work Remotely, Himalayas)
  → filtro de título e recência
  → deduplicação contra a planilha
  → elegibilidade (localização, autorização de trabalho, idioma)
  → score 0–100 por regras
  → aba TRIAGEM + e-mail
  → eu me candidato e marco APLICADO → linha vai para a aba MONITOR
```

## Estrutura

| Arquivo | Função |
|---|---|
| `config.yaml` | Perfil, filtros, skills, pesos e limites. Toda personalização é feita aqui. |
| `agent/sources.py` | Coletores das fontes gratuitas |
| `agent/eligibility.py` | Regras eliminatórias e de revisão |
| `agent/scoring.py` | Score de compatibilidade |
| `agent/sheets.py` | Abas TRIAGEM e MONITOR |
| `agent/notify.py` | E-mail do turno |
| `agent/main.py` | Orquestração |
| `tests/` | Testes do filtro e do score |

## Como o score funciona

| Componente | Peso | Regra |
|---|---|---|
| Hard skills | 40 | Skills obrigatórias citadas na vaga, ponderadas por importância (tenho = 1, parcial = 0,5, não tenho = 0) |
| Senioridade | 20 | Anos exigidos ≤ meus anos = 1; até 2 a mais = 0,5; acima disso = 0; não informado = 0,8 |
| Responsabilidades | 15 | Dashboards, stakeholders, ETL, modelagem, KPIs, automação, qualidade, storytelling |
| Desejáveis | 10 | Skills em linhas/seções "nice to have", "preferred", "a plus" |
| Contexto | 15 | Aceita Brasil/LATAM/mundo explicitamente; contrato PJ/contractor |

**Candidatar** ≥ 75 e elegível · **Revisar** ≥ 55 ou elegibilidade incerta · **Descartar** o resto ou inelegível.

## Configuração (uma vez)

### 1. Google Sheets (service account)
1. Acesse o Google Cloud Console, crie um projeto e ative a **Google Sheets API** e a **Google Drive API**.
2. Em *IAM e administrador → Contas de serviço*, crie uma conta e gere uma chave **JSON**.
3. Compartilhe a planilha com o e-mail da conta de serviço (termina em `iam.gserviceaccount.com`) como **Editor**.
4. O ID da planilha é o trecho entre `/d/` e `/edit` no link.

### 2. Gmail (envio do e-mail)
1. Ative a verificação em duas etapas na conta Google.
2. Gere uma **senha de app** e guarde os 16 caracteres.

### 3. Secrets do GitHub
Em *Settings → Secrets and variables → Actions*, crie:

| Secret | Conteúdo |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Conteúdo inteiro do arquivo JSON da chave |
| `SHEET_ID` | ID da planilha |
| `GMAIL_ADDRESS` | Seu Gmail |
| `GMAIL_APP_PASSWORD` | Senha de app |
| `STANDARD_ANSWERS` | Respostas padrão de formulário (texto livre) |

Nunca coloque credenciais ou dados pessoais no código: o repositório é público.

### 4. Teste local
```bash
pip install -r requirements.txt
python -m pytest -q
python -m agent.main --dry-run     # coleta e pontua sem escrever nada
```

### 5. Primeira execução real
Em *Actions → job-agent → Run workflow*. A aba TRIAGEM é criada automaticamente.

## Observações
- O cron do GitHub Actions pode atrasar alguns minutos.
- O GitHub desativa agendamentos em repositórios públicos sem commits por 60 dias; um commit qualquer reativa.
- Se uma fonte mudar o formato, ela aparece como `ERRO` no rodapé do e-mail e as demais continuam funcionando.

## Próximas fases
- Leitura de alertas do LinkedIn, Glassdoor e Jobright pelo Gmail
- CV ajustado por vaga e cover letter
- Dashboard de acompanhamento das candidaturas
