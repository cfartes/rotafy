import base64
import json
from datetime import date, datetime, timezone
from io import BytesIO
from types import SimpleNamespace

import pytest
from app.billing.message_templates import decode_notice, encode_notice, qr_image
from app.billing.pix import static_pix_key
from app.email_worker import send_email
from PIL import Image


def sample():
    return {
        "id": "reference",
        "starts_at": datetime(2026, 9, 15, 3, tzinfo=timezone.utc),
        "ends_at": datetime(2026, 10, 15, 3, tzinfo=timezone.utc),
        "plan_name": "Professional",
        "price_cents": 9990,
        "included_trips": 30,
        "used_trips": 32,
        "extra_trips": 2,
        "extra_trip_cents": 3000,
        "total_cents": 15990,
        "due_on": date(2026, 10, 19),
        "receiver_name": "Nexus",
        "pix_key": "financeiro@example.com",
        "pix_copy_paste": "",
    }


@pytest.mark.parametrize("kind", ["invoice", "blocked", "preview", "paid"])
def test_shared_presentation_and_qr_only_when_payment_is_due(kind):
    message = decode_notice(
        encode_notice(sample(), {"trade_name": "Empresa <script>teste</script>"}, kind)
    )
    assert "<script>" not in message["html"]
    assert "&lt;script&gt;" in message["html"]
    assert "R$ 159,90" in message["text"]
    assert "15/09/2026 a 14/10/2026" in message["text"]
    if kind in {"invoice", "blocked"}:
        assert static_pix_key(message["pix"]) == "financeiro@example.com"
        assert "cid:pix-rotafy" in message["html"]
        with Image.open(BytesIO(base64.b64decode(qr_image(message["pix"])))) as image:
            assert image.format == "PNG" and image.width == image.height
            image.verify()
        assert len(message["whatsapp"]) <= 1024
    else:
        assert not message["pix"] and "cid:pix-rotafy" not in message["html"]


def test_demo_uses_real_presentation_with_clear_warning_and_legacy_messages_still_work():
    demo = decode_notice(
        encode_notice(sample(), {"trade_name": "Empresa"}, "invoice", demo=True)
    )
    real = decode_notice(encode_notice(sample(), {"trade_name": "Empresa"}, "invoice"))
    for field in ["text", "whatsapp", "html"]:
        assert "NÃO PAGAR" in demo[field] and "NÃO PAGAR" not in real[field]
    assert demo["pix"] == real["pix"]
    assert decode_notice("mensagem anterior")["text"] == "mensagem anterior"


def test_email_transport_passes_inline_qr_and_html(monkeypatch):
    captured = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return b'{"id":"accepted"}'

    def request(req, timeout):
        captured.append(json.loads(req.data))
        return Response()

    monkeypatch.setattr("app.email_worker.urlopen", request)
    item = {
        "id": "test",
        "recipient": "test@example.com",
        "subject": "Teste",
        "body": "texto",
        "html": '<img src="cid:pix-rotafy">',
        "attachments": [
            {"content_id": "pix-rotafy", "content": "base64", "filename": "pix.png"}
        ],
    }
    assert (
        send_email(
            SimpleNamespace(email_from="nexus@example.com", resend_api_key="fake"), item
        )
        == "accepted"
    )
    assert (
        captured[0]["html"] == item["html"]
        and captured[0]["attachments"] == item["attachments"]
    )
