"""Generate local fictitious customer artifacts without database access or sending mail."""

import ast
import base64
import hashlib
import html
import json
import sys
from datetime import date, datetime, timezone
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.contracts import canonical, pdf_document


def expression(path, function, variable, values):
    """Use the application's actual PDF header and email template, read-only."""
    module = ast.parse(path.read_text(encoding="utf-8"))
    node = next(
        n
        for n in module.body
        if isinstance(n, ast.AsyncFunctionDef) and n.name == function
    )
    assignment = next(
        n
        for n in ast.walk(node)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == variable for t in n.targets)
        and (variable != "message" or isinstance(n.value, ast.Dict))
    )
    return eval(
        compile(ast.Expression(assignment.value), str(path), "eval"),
        {"__builtins__": {}},
        values,
    )


def main():
    directory = ROOT / "docs" / "exemplos" / "contrato-cliente"
    directory.mkdir(parents=True, exist_ok=True)
    identifier = uuid4()
    now = datetime.now(timezone.utc)
    representative = {
        "representative_name": "Maria Exemplo — pessoa fictícia",
        "representative_cpf": "00000000000",
        "representative_role": "Administradora",
        "authority": True,
    }
    snapshot = {
        "corporate_name": "Agência Horizonte Exemplo LTDA — DADOS FICTÍCIOS",
        "trade_name": "Horizonte Turismo — EXEMPLO SEM VALOR CONTRATUAL",
        "cnpj": "00000000000000",
        "address": "Rua de Exemplo",
        "address_number": "100",
        "address_complement": "Sala 2",
        "neighborhood": "Centro",
        "city": "Blumenau",
        "state": "SC",
        "postal_code": "00000000",
        "email": "cliente@example.com",
        "terms": {
            "plan_name": "Basic — valores ilustrativos",
            "price_cents": 25990,
            "included_trips": 30,
            "extra_trip_cents": 1000,
            "trial_days": 7,
            "starts_on": date(2026, 10, 28),
            "setup_cents": 38000,
        },
    }
    version = {
        "code": "2026-10-21-r2",
        "body": (ROOT / "backend/app/contract_terms_r2.txt").read_text(
            encoding="utf-8"
        ),
    }
    header = expression(
        ROOT / "backend/app/contracts.py",
        "prepare",
        "header",
        {
            "identifier": identifier,
            "now": now,
            "snapshot": snapshot,
            "data": SimpleNamespace(**representative),
            "version": version,
            "t": snapshot["terms"],
            "money": lambda cents: f"R$ {cents / 100:.2f}".replace(".", ","),
        },
    )
    pdf = pdf_document(
        "Contrato de utilização Nexus Rotafy — EXEMPLO FICTÍCIO",
        header + "\n\n" + version["body"],
    )
    digest = hashlib.sha256(pdf).hexdigest()
    evidence = canonical(
        {
            "example_only": True,
            "notice": "SIMULAÇÃO. Nenhum aceite real foi registrado ou e-mail enviado.",
            "acceptance_id": uuid4(),
            "company_id": uuid4(),
            "document_id": identifier,
            "document_sha256": digest,
            "version_id": "35000000-0000-4000-8000-000000000001",
            "version_code": version["code"],
            "accepted_at_utc": now,
            "user_id": uuid4(),
            "session_id": uuid4(),
            "email_confirmed": snapshot["email"],
            "representative": representative,
            "ip": "192.0.2.10",
            "user_agent": "Navegador demonstrativo",
            "affirmation": "Li e aceito o contrato integral apresentado e declaro poderes para representar a empresa.",
            "viewed_at_utc": now,
        }
    )
    receipt = pdf_document(
        "Comprovante de aceite eletrônico — EXEMPLO FICTÍCIO",
        "SIMULAÇÃO SEM ACEITE REAL.\n\nEste comprovante acompanha o PDF original aceito. O SHA-256 abaixo refere-se ao arquivo do contrato, sem modificações após o aceite.\n\n"
        + evidence,
    )
    message = expression(
        ROOT / "backend/app/contract_mail.py",
        "process_contract_mail",
        "message",
        {
            "label": "contrato",
            "item": {"document_id": identifier},
            "doc": {"sha256": digest, "pdf": pdf, "receipt_pdf": receipt},
            "base64": base64,
            "bytes": bytes,
        },
    )
    (directory / "contrato-rotafy.pdf").write_bytes(pdf)
    (directory / "comprovante-aceite.pdf").write_bytes(receipt)
    email = EmailMessage(policy=SMTP)
    email["From"] = "Nexus Rotafy <nexus@example.com>"
    email["To"] = snapshot["email"]
    email["Subject"] = message["subject"]
    email.set_content(message["body"])
    for attachment in message["attachments"]:
        email.add_attachment(
            base64.b64decode(attachment["content"]),
            maintype="application",
            subtype="pdf",
            filename=attachment["filename"],
        )
    (directory / "email-exemplo.eml").write_bytes(email.as_bytes())
    preview = f"""<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Exemplo do e-mail de contrato — Rotafy</title>
    <style>body{{font:16px/1.6 system-ui;background:#f2f6f8;color:#12344c;margin:0;padding:32px}}main{{max-width:900px;margin:auto;background:white;padding:32px;border-radius:16px}}aside{{background:#fff4db;border:1px solid #e1bc65;padding:16px}}h1{{font-size:25px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}}a{{color:#087b76}}.attachments{{display:flex;gap:20px;flex-wrap:wrap;border-top:1px solid #ddd;padding-top:20px}}</style>
    <main><aside><strong>Exemplo fictício para revisão.</strong> Não houve aceite real nem envio de e-mail. Plano, valores e dados do cliente são ilustrativos. A minuta r2 ainda depende de aprovação.</aside>
    <h1>{html.escape(message["subject"])}</h1><p>De: Nexus Rotafy &lt;nexus@example.com&gt;<br>Para: cliente@example.com</p>
    <pre>{html.escape(message["body"])}</pre><div class="attachments"><a href="contrato-rotafy.pdf">📎 contrato-rotafy.pdf</a><a href="comprovante-aceite.pdf">📎 comprovante-aceite.pdf</a><a href="email-exemplo.eml">Abrir e-mail de exemplo (.eml)</a></div>
    <h2>Dados utilizados na demonstração</h2><p>Plano Basic: R$ 259,90 por ciclo, franquia de 30 viagens e excedente de R$ 10,00 por viagem. Setup ilustrativo: R$ 380,00. Teste: 21/10 a 28/10/2026. Primeiro ciclo pago: 28/10 a 27/11/2026. A cobrança da mensalidade ocorre no fechamento do ciclo; o prazo de pagamento é contado conforme o contrato.</p>
    <p>O conteúdo da mensagem e o quadro do PDF foram extraídos dos mesmos modelos usados pelo aplicativo. A apresentação desta página é apenas uma prévia; a aparência na caixa de entrada depende do programa de e-mail.</p></main></html>"""
    (directory / "email-exemplo.html").write_text(preview, encoding="utf-8")
    assert (
        digest
        == hashlib.sha256(
            base64.b64decode(message["attachments"][0]["content"])
        ).hexdigest()
    )
    assert digest in message["body"]
    (directory / "verificacao.json").write_text(
        json.dumps(
            {
                "example_only": True,
                "document_id": str(identifier),
                "sha256": digest,
                "files": [
                    "contrato-rotafy.pdf",
                    "comprovante-aceite.pdf",
                    "email-exemplo.eml",
                    "email-exemplo.html",
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Generated and verified: {directory}")


if __name__ == "__main__":
    main()
