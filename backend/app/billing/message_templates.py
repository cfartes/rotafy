"""Shared financial presentation for actual notices and demonstrations."""

import base64
import json
from datetime import timedelta
from html import escape
from io import BytesIO

import qrcode

from app.billing.calendar import SAO_PAULO
from app.billing.pix import key_payload, normalize_key, static_pix_key


def amount(cents):
    whole = f"{cents // 100:,}".replace(",", ".")
    return f"R$ {whole},{cents % 100:02d}"


def encode_notice(invoice, company, kind, demo=False):
    gateway = invoice.get("payment_provider") == "infinitepay"
    titles = {
        "invoice": "Sua mensalidade está disponível",
        "preview": "Seu ciclo está próximo do fechamento",
        "blocked": "Pagamento aguardando confirmação",
        "paid": "Pagamento confirmado",
    }
    title = titles[kind]
    setup_only = invoice.get("invoice_kind") == "setup"
    if setup_only and kind == "invoice":
        title = "Sua taxa de setup está disponível"
    elif setup_only and kind == "preview":
        title = "Seu teste está terminando — cobrança do setup"
    start = invoice["starts_at"].astimezone(SAO_PAULO).strftime("%d/%m/%Y")
    end = (
        (invoice["ends_at"] - timedelta(seconds=1))
        .astimezone(SAO_PAULO)
        .strftime("%d/%m/%Y")
    )
    rows = [
        ("Empresa", company["trade_name"]),
        ("Plano", invoice["plan_name"]),
        ("Período", f"{start} a {end}"),
        ("Mensalidade", amount(invoice["price_cents"])),
        ("Franquia", f"{invoice['included_trips']} viagens"),
        ("Viagens utilizadas", str(invoice["used_trips"])),
        (
            "Excedentes",
            f"{invoice['extra_trips']} × {amount(invoice['extra_trip_cents'])}",
        ),
        (
            "Total parcial" if kind == "preview" else "Total",
            amount(invoice["total_cents"]),
        ),
    ]
    if invoice.get("setup_cents"):
        rows.insert(-1, ("Setup (cobrança única)", amount(invoice["setup_cents"])))
    if setup_only:
        rows = [
            (label, value)
            for label, value in rows
            if label
            not in {
                "Período",
                "Mensalidade",
                "Franquia",
                "Viagens utilizadas",
                "Excedentes",
            }
        ]
        rows.insert(2, ("Data do setup", start))
    if invoice.get("extras_starts_at"):
        rows.insert(
            -1,
            (
                "Período dos excedentes",
                f"{invoice['extras_starts_at'].astimezone(SAO_PAULO):%d/%m/%Y} a {(invoice['extras_ends_at'] - timedelta(seconds=1)).astimezone(SAO_PAULO):%d/%m/%Y}",
            ),
        )
    if kind != "paid":
        rows.append(("Confirmar pagamento até", invoice["due_on"].strftime("%d/%m/%Y")))
    notes = {
        "preview": "Este é um aviso parcial, sujeito a alterações. Aguarde a cobrança definitiva antes de pagar.",
        "invoice": "Após o Pix, a equipe Nexus confere o recebimento e confirma o pagamento.",
        "blocked": "Novas operações estão restritas até a confirmação do Pix. O acesso às viagens já vendidas permanece disponível.",
        "paid": "Recebimento confirmado pela equipe Nexus. A restrição financeira desta cobrança foi removida.",
    }
    if gateway:
        notes.update(
            invoice="Acesse o link para pagar. A confirmação será automática após aprovação do pagamento.",
            blocked="Novas operações estão restritas até a confirmação do pagamento. As viagens já vendidas continuam disponíveis.",
            paid="Pagamento confirmado. A restrição financeira desta cobrança foi removida.",
        )
        if kind in {"invoice", "blocked"} and invoice.get("payment_url"):
            rows.append(("Pagar agora", invoice["payment_url"]))
    pix = ""
    if kind in {"invoice", "blocked"} and not gateway:
        rows.extend(
            [
                ("Favorecido", invoice["receiver_name"]),
                ("Chave Pix", invoice["pix_key"]),
            ]
        )
        try:
            pix = invoice.get("pix_copy_paste") or key_payload(
                invoice["pix_key"], invoice["receiver_name"]
            )
            if normalize_key(static_pix_key(pix)) != normalize_key(invoice["pix_key"]):
                pix = ""
        except ValueError:
            pix = ""
    banner = (
        "TESTE DE COBRANÇA — NÃO PAGAR\nDados ilustrativos para conferência do modelo.\n\n"
        if demo
        else ""
    )
    detail = "\n".join(f"{label}: {value}" for label, value in rows)
    footer = f"\n\n{notes[kind]}\nConsulte Financeiro no painel da empresa.\nReferência: {invoice['id']}"
    text = f"{banner}Nexus Rotafy\n{title}\n\n{detail}{footer}"
    whatsapp_detail = "\n".join(f"*{label}:* {value}" for label, value in rows)
    whatsapp = f"{banner}*Nexus Rotafy*\n*{title}*\n\n{whatsapp_detail}{footer}"
    if pix:
        instruction = f"\n\nPix sem valor definido: informe {amount(invoice['total_cents'])} no banco."
        copy = "\n\nPix Copia e Cola:\n" + pix
        text += instruction + copy
        whatsapp += instruction
        if len(whatsapp + copy) <= 1024:
            whatsapp += copy
    # A single image + caption request prevents partial multi-message retries.
    if pix and len(whatsapp) > 1024:
        whatsapp = f"{banner}*Nexus Rotafy — {title}*\nTotal: {amount(invoice['total_cents'])}\nConfirme até {invoice['due_on']:%d/%m/%Y}.\nLeia o QR Code e informe o total no banco.\n{notes[kind]}\nConsulte o demonstrativo no painel."
    table = "".join(
        f'<tr><td style="padding:10px;border-bottom:1px solid #e2e8f0;color:#526579">{escape(str(label))}</td><td style="padding:10px;border-bottom:1px solid #e2e8f0;text-align:right;font-weight:600">{escape(str(value))}</td></tr>'
        for label, value in rows
    )
    warning = (
        '<p style="padding:16px;background:#fff0e6;color:#9b3514;font-weight:bold">TESTE DE COBRANÇA — NÃO PAGAR<br>Dados ilustrativos para conferência do modelo.</p>'
        if demo
        else ""
    )
    payment = (
        (
            f'<h2 style="color:#0d7773">Pague com Pix</h2><img src="cid:pix-rotafy" width="300" height="300" alt="QR Code Pix" style="display:block;max-width:100%;height:auto;margin:auto"><p>QR Code sem valor definido. Informe <strong>{escape(amount(invoice["total_cents"]))}</strong> no banco.</p><p><strong>Pix Copia e Cola</strong></p><p style="word-break:break-all;background:#f1f5f9;padding:16px;font-family:monospace">{escape(pix)}</p>'
        )
        if pix
        else ""
    )
    if gateway and kind in {"invoice", "blocked"} and invoice.get("payment_url"):
        payment = (
            f'<p style="text-align:center;margin:28px 0"><a href="{escape(invoice["payment_url"], quote=True)}" style="display:inline-block;background:#0d7773;color:white;text-decoration:none;padding:16px 28px;border-radius:8px;font-weight:bold">Pagar setup e mensalidade</a></p>'
            if invoice.get("setup_cents") and not setup_only
            else f'<p style="text-align:center;margin:28px 0"><a href="{escape(invoice["payment_url"], quote=True)}" style="display:inline-block;background:#0d7773;color:white;text-decoration:none;padding:16px 28px;border-radius:8px;font-weight:bold">Pagar mensalidade</a></p>'
        )
        if setup_only:
            payment = payment.replace("Pagar mensalidade", "Pagar setup")
    html = f'<!doctype html><html lang="pt-BR"><body style="margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#15324b"><div style="max-width:620px;margin:auto;background:white;padding:28px"><div style="background:#0d7773;color:white;padding:20px;font-size:22px;font-weight:bold">Nexus Rotafy</div>{warning}<h1 style="font-size:24px">{escape(title)}</h1><table style="width:100%;border-collapse:collapse;font-size:15px">{table}</table>{payment}<p style="line-height:1.6">{escape(notes[kind])}</p><p>Consulte Financeiro no painel da empresa.</p><p style="font-size:12px;color:#526579">Referência: {escape(str(invoice["id"]))}</p></div></body></html>'
    return json.dumps(
        {
            "format": "billing-v1",
            "text": text,
            "whatsapp": whatsapp,
            "html": html,
            "pix": pix,
        },
        ensure_ascii=False,
    )


def decode_notice(body):
    try:
        message = json.loads(body)
        if isinstance(message, dict) and message.get("format") == "billing-v1":
            return message
    except (ValueError, TypeError):
        pass
    return {"text": body, "whatsapp": body, "pix": ""}


def qr_image(payload):
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=4
    )
    qr.add_data(payload)
    qr.make(fit=True)
    stream = BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(stream, format="PNG")
    return base64.b64encode(stream.getvalue()).decode("ascii")
