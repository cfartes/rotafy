from datetime import timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from app.billing.calendar import utc_now
from app.nps import metrics
from app.nps_worker import process_nps, schedule_surveys
from app.whatsapp_automation import process_automation
from conftest import login
from sqlalchemy import text
from test_boarding import command, prepare
from test_messaging import protected_key  # noqa: F401
from test_reservations import family, reserve
from test_whatsapp_automation import BASE, provider, receive, run
from test_whatsapp_automation import automation as automation_fixture

automation = automation_fixture
pytestmark = pytest.mark.usefixtures("protected_key")
CHAT = "5511999999999@c.us"


@pytest.fixture
def nps(client, seeded, owner, automation):
    result = client.put(
        "/api/v1/nps/settings", json={"service_enabled": True, "trip_enabled": True}
    )
    assert result.status_code == 200, result.text
    with owner.begin() as db:
        db.execute(text("UPDATE nps_dispatch SET next_send_at=now()"))
    return automation


def handoff(client, seeded, owner, automation, chat=CHAT):
    with owner.begin() as db:
        db.execute(
            text("""INSERT INTO whatsapp_command_states(company_id,session_id,chat_id,phone,handoff_at)
          VALUES(:company,:session,:chat,:phone,clock_timestamp()) ON CONFLICT(company_id,session_id,chat_id)
          DO UPDATE SET handoff_at=clock_timestamp(),phone=EXCLUDED.phone"""),
            {
                "company": seeded["a"],
                "session": automation["session"],
                "chat": chat,
                "phone": "+" + chat.split("@")[0],
            },
        )
    response = client.post(
        "/api/v1/whatsapp/chat/handoffs/close", json={"chat_id": chat}
    )
    assert response.status_code == 204, response.text


def survey(owner):
    with owner.connect() as db:
        return dict(
            db.execute(
                text("SELECT * FROM nps_surveys ORDER BY created_at DESC LIMIT 1")
            )
            .mappings()
            .one()
        )


def test_service_questions_score_zero_comment_dedupe_and_bot_isolation(
    client, seeded, owner, nps
):
    handoff(client, seeded, owner, nps)
    sent = []
    assert run(process_nps, seeded["a"], transport=provider(sent))
    assert "Em uma escala de 0 a 10" in sent[-1]["text"]
    assert (
        "Sua opinião é fundamental para continuarmos evoluindo! 🚀" in sent[-1]["text"]
    )
    assert survey(owner)["expires_at"] - survey(owner)["dispatched_at"] == timedelta(
        hours=24
    )
    identifier = str(uuid4())
    for _ in range(2):
        assert (
            receive(client, seeded, nps, body="0", identifier=identifier).status_code
            == 200
        )
    assert survey(owner)["score"] == 0
    assert survey(owner)["stage"] == "comment"
    assert run(process_nps, seeded["a"], transport=provider(sent))
    assert "o que poderíamos ter feito de diferente hoje?" in sent[-1]["text"]
    assert not run(process_automation, seeded["a"], BASE, transport=provider(sent))
    receive(client, seeded, nps, body="Mais agilidade, por favor.")
    assert survey(owner)["comment"] == "Mais agilidade, por favor."
    assert survey(owner)["status"] == "answered"
    assert run(process_nps, seeded["a"], transport=provider(sent))
    assert "Obrigado pela avaliação" in sent[-1]["text"]
    # New text returns to the normal menu, rather than overwriting the evaluation.
    receive(client, seeded, nps, body="Olá")
    assert run(process_automation, seeded["a"], BASE, transport=provider(sent))
    assert "1. Bilhete" in sent[-1]["text"]


@pytest.mark.parametrize("exit_word", ["PULAR", "Encerrar", "menu"])
def test_opt_out_does_not_create_zero_score(client, seeded, owner, nps, exit_word):
    handoff(client, seeded, owner, nps)
    run(process_nps, seeded["a"], transport=provider([]))
    receive(client, seeded, nps, body=exit_word)
    assert survey(owner)["score"] is None
    assert survey(owner)["status"] == "skipped"
    assert survey(owner)["stage"] == "closed"


def test_score_validation_expiry_optional_comment_and_service_cooldown(
    client, seeded, owner, nps
):
    handoff(client, seeded, owner, nps)
    sent = []
    run(process_nps, seeded["a"], transport=provider(sent))
    receive(client, seeded, nps, body="11")
    run(process_nps, seeded["a"], transport=provider(sent))
    assert survey(owner)["score"] is None
    assert "nota de 0 a 10" in sent[-1]["text"]
    receive(client, seeded, nps, body="10")
    with owner.begin() as db:
        db.execute(text("UPDATE nps_surveys SET expires_at=now()-interval '1 second'"))
    run(schedule_surveys, seeded["a"])
    assert survey(owner)["score"] == 10
    assert survey(owner)["status"] == "answered"
    handoff(client, seeded, owner, nps)
    with owner.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM nps_surveys")) == 1


def test_nps_works_without_command_menu_and_uses_signed_webhook(
    client, seeded, owner, nps
):
    handoff(client, seeded, owner, nps)
    with owner.begin() as db:
        db.execute(text("UPDATE whatsapp_automation SET commands_enabled=false"))
    run(process_nps, seeded["a"], transport=provider([]))
    assert (
        client.post(f"/api/v1/webhooks/openwa/{seeded['a']}", json={}).status_code
        == 403
    )
    assert receive(client, seeded, nps, body="9").status_code == 200
    assert survey(owner)["score"] == 9
    receive(client, seeded, nps, body="PULAR")
    assert survey(owner)["score"] == 9
    assert survey(owner)["status"] == "answered"


def test_ambiguous_send_is_not_repeated_and_can_still_be_answered(
    client, seeded, owner, nps
):
    handoff(client, seeded, owner, nps)
    sent = []
    run(process_nps, seeded["a"], transport=provider(sent, fail=True))
    assert survey(owner)["status"] == "uncertain"
    assert not run(process_nps, seeded["a"], transport=provider(sent))
    assert len(sent) == 1
    receive(client, seeded, nps, body="8")
    assert survey(owner)["score"] == 8


def test_new_human_reply_cancels_active_survey(client, seeded, owner, nps):
    handoff(client, seeded, owner, nps)
    run(process_nps, seeded["a"], transport=provider([]))
    response = client.post(
        "/api/v1/whatsapp/chat/send",
        json={
            "operation_key": str(uuid4()),
            "chat_id": CHAT,
            "text": "Nossa equipe retomou o atendimento.",
        },
    )
    assert response.status_code == 202, response.text
    assert survey(owner)["stage"] == "closed"
    receive(client, seeded, nps, body="10")
    assert survey(owner)["score"] is None


def test_trip_only_after_full_completion_two_hours_and_boarding(
    client, seeded, owner, nps
):
    trip, reservation, prefix = prepare(client, seeded, size=1)
    reserve(client, trip, family(name="Sem embarque", size=1, phone="(11) 98888-8888"))
    login(client, email="driver0@example.com")
    assert (
        client.patch(prefix + "/journey", json={"status": "in_progress"}).status_code
        == 200
    )
    assert (
        command(client, prefix, reservation["passengers"][0]["id"]).status_code == 201
    )
    login(client)
    with owner.begin() as db:
        db.execute(text("UPDATE nps_settings SET trip_since=now()-interval '3 hours'"))
        db.execute(
            text("""INSERT INTO audit_events(id,company_id,actor_id,action,target_id,created_at)
          VALUES(:id,:company,:actor,'trip.completed',:trip,now()-interval '119 minutes')"""),
            {
                "id": uuid4(),
                "company": seeded["a"],
                "actor": seeded["admin_a"],
                "trip": trip["id"],
            },
        )
        db.execute(
            text("UPDATE trips SET status='completed' WHERE id=:id"), {"id": trip["id"]}
        )
    run(schedule_surveys, seeded["a"])
    with owner.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM nps_surveys")) == 0
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE audit_events SET created_at=now()-interval '121 minutes' WHERE action='trip.completed'"
            )
        )
    run(schedule_surveys, seeded["a"])
    run(schedule_surveys, seeded["a"])
    assert survey(owner)["kind"] == "trip"
    assert str(survey(owner)["reservation_id"]) == reservation["id"]
    with owner.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM nps_surveys")) == 1
    sent = []
    run(process_nps, seeded["a"], transport=provider(sent))
    assert "recomendaria viajar com" in sent[-1]["text"]
    receive(client, seeded, nps, body="7")
    run(process_nps, seeded["a"], transport=provider(sent))
    assert "Queremos que cada viagem seja especial" in sent[-1]["text"]


@pytest.mark.parametrize("change", ["module", "settings", "company"])
def test_pending_invite_revalidates_access(client, seeded, owner, nps, change):
    handoff(client, seeded, owner, nps)
    with owner.begin() as db:
        if change == "module":
            db.execute(
                text(
                    "UPDATE companies SET enabled_modules=array_remove(enabled_modules,'whatsapp') WHERE id=:id"
                ),
                {"id": seeded["a"]},
            )
        elif change == "settings":
            db.execute(text("UPDATE nps_settings SET service_enabled=false"))
        else:
            db.execute(
                text("UPDATE companies SET is_active=false WHERE id=:id"),
                {"id": seeded["a"]},
            )
    sent = []
    run(process_nps, seeded["a"], transport=provider(sent))
    assert not sent
    assert survey(owner)["status"] == "discarded"


def test_reports_filters_tenant_scope_exports_and_permissions(
    client, seeded, owner, nps
):
    with owner.begin() as db:
        for i, score in enumerate([10, 9, 8, 6, 0, None]):
            db.execute(
                text("""INSERT INTO nps_surveys(id,company_id,kind,source_key,phone,question_score,question_comment,scheduled_at,score,status,stage,sent_at,comment)
              VALUES(:id,:company,'service',:key,'+5511999999999','Nota?','Comentário?',now(),:score,'answered','closed',now(),:comment)"""),
                {
                    "id": uuid4(),
                    "company": seeded["a"],
                    "key": str(i),
                    "score": score,
                    "comment": '=HYPERLINK("bad")'
                    if i == 0
                    else "Bom <script>texto</script>",
                },
            )
        db.execute(
            text("""INSERT INTO nps_surveys(id,company_id,kind,source_key,phone,question_score,question_comment,scheduled_at,score)
          VALUES(:id,:company,'service','other','+5511888888888','Nota?','Comentário?',now(),0)"""),
            {"id": uuid4(), "company": seeded["b"]},
        )
    date = utc_now().astimezone(ZoneInfo("America/Sao_Paulo")).date().isoformat()
    path = f"/api/v1/nps/report?start={date}&end={date}"
    response = client.get(path)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 6
    assert data["summary"]["nps"] == 0
    assert data["summary"]["responses"] == 5
    assert data["summary"]["average"] == 6.6
    assert data["summary"]["response_rate"] == 83.3
    assert client.get(path + "&classification=detractor").json()["total"] == 2
    assert client.get(path + "&kind=trip").json()["summary"]["nps"] is None
    exported = client.get(path + "&output=csv")
    assert "'=HYPERLINK" in exported.text
    pdf = client.get(path + "&output=pdf")
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF")
    assert (
        client.get("/api/v1/nps/report?start=2025-01-01&end=2026-10-22").status_code
        == 422
    )
    with owner.begin() as db:
        db.execute(
            text("UPDATE users SET role='attendant' WHERE id=:id"),
            {"id": seeded["admin_a"]},
        )
    assert client.get(path).status_code == 200
    assert (
        client.put(
            "/api/v1/nps/settings",
            json={"service_enabled": False, "trip_enabled": False},
        ).status_code
        == 403
    )
    login(client, email="guide@example.com")
    assert client.get(path).status_code == 403
    login(client, company="empresa-b")
    assert client.get(path).json()["total"] == 1
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE companies SET enabled_modules=array_remove(enabled_modules,'whatsapp') WHERE id=:id"
            ),
            {"id": seeded["b"]},
        )
    assert client.get(path).status_code == 403


def test_empty_kpis_are_not_zero_scores():
    assert metrics([])["nps"] is None
    assert metrics([{"score": None, "sent_at": None}])["response_rate"] is None


def test_invites_are_paced_and_conversations_never_overlap(client, seeded, owner, nps):
    handoff(client, seeded, owner, nps)
    handoff(client, seeded, owner, nps, chat="5511888888888@c.us")
    sent = []
    assert run(process_nps, seeded["a"], transport=provider(sent))
    assert not run(process_nps, seeded["a"], transport=provider(sent))
    assert len(sent) == 1
    with owner.begin() as db:
        db.execute(
            text("UPDATE nps_dispatch SET next_send_at=now()-interval '1 second'")
        )
    assert run(process_nps, seeded["a"], transport=provider(sent))
    assert len(sent) == 2
    assert sent[0]["chatId"] != sent[1]["chatId"]


def test_another_phone_cannot_answer_and_disabled_settings_close_pending_prompts(
    client, seeded, owner, nps
):
    handoff(client, seeded, owner, nps)
    run(process_nps, seeded["a"], transport=provider([]))
    receive(client, seeded, nps, body="10", sender="5511888888888@c.us")
    assert survey(owner)["score"] is None
    response = client.put(
        "/api/v1/nps/settings", json={"service_enabled": False, "trip_enabled": False}
    )
    assert response.status_code == 200
    assert survey(owner)["stage"] == "closed"


def test_expired_survey_does_not_consume_a_late_rating(client, seeded, owner, nps):
    handoff(client, seeded, owner, nps)
    run(process_nps, seeded["a"], transport=provider([]))
    with owner.begin() as db:
        db.execute(text("UPDATE nps_surveys SET expires_at=now()-interval '1 second'"))
    receive(client, seeded, nps, body="9")
    assert survey(owner)["score"] is None
    run(schedule_surveys, seeded["a"])
    assert survey(owner)["status"] == "expired"


def test_undecryptable_queue_does_not_crash_the_shared_worker(
    client, seeded, owner, nps
):
    handoff(client, seeded, owner, nps)
    with owner.begin() as db:
        db.execute(text("UPDATE nps_messages SET body='invalid-ciphertext'"))
    sent = []
    assert run(process_nps, seeded["a"], transport=provider(sent))
    assert not sent
    with owner.connect() as db:
        assert (
            db.scalar(text("SELECT error_code FROM nps_messages"))
            == "preparation_unavailable"
        )


def test_answer_arriving_before_provider_ack_is_preserved(client, seeded, owner, nps):
    handoff(client, seeded, owner, nps)
    fallback = provider([])

    def transport(key, path, body=None):
        if path.endswith("/messages/send-text"):
            response = receive(client, seeded, nps, body="10")
            assert response.status_code == 200
        return fallback(key, path, body)

    assert run(process_nps, seeded["a"], transport=transport)
    assert survey(owner)["score"] == 10
    assert survey(owner)["stage"] == "closed"
    assert survey(owner)["status"] == "answered"


@pytest.mark.parametrize("sender", ["123456789012345@lid", "551199999999@c.us"])
def test_private_identifiers_and_brazil_phone_aliases_require_provider_proof(
    client, seeded, owner, nps, monkeypatch, sender
):
    handoff(client, seeded, owner, nps)
    run(process_nps, seeded["a"], transport=provider([]))
    calls = []

    def lookup(key, path, body=None):
        assert body is None
        calls.append(path)
        if path.endswith("/phone"):
            return {"phone": "5511999999999"}
        return {"exists": True, "whatsappId": "551199999999@c.us"}

    monkeypatch.setattr("app.nps_worker.openwa_request", lookup)
    response = receive(client, seeded, nps, body="9", sender=sender)
    assert response.status_code == 200, response.text
    assert survey(owner)["score"] == 9
    assert calls


def test_unproven_alias_cannot_submit_a_rating(client, seeded, owner, nps, monkeypatch):
    handoff(client, seeded, owner, nps)
    run(process_nps, seeded["a"], transport=provider([]))
    monkeypatch.setattr(
        "app.nps_worker.openwa_request",
        lambda key, path: {
            "exists": True,
            "whatsappId": path.rsplit("/", 1)[1] + "@c.us",
        },
    )
    response = receive(client, seeded, nps, body="9", sender="551199999999@c.us")
    assert response.status_code == 200
    assert survey(owner)["score"] is None


def test_private_id_human_chat_defers_survey_invitation(client, seeded, owner, nps):
    handoff(client, seeded, owner, nps)
    private_chat = "123456789012345@lid"
    with owner.begin() as db:
        db.execute(
            text(
                "INSERT INTO whatsapp_command_states(company_id,session_id,chat_id,handoff_at) VALUES(:company,:session,:chat,now())"
            ),
            {"company": seeded["a"], "session": nps["session"], "chat": private_chat},
        )
    sent = []
    fallback = provider(sent)

    def transport(key, path, body=None):
        if "/contacts/check/" in path:
            return {"exists": True, "whatsappId": private_chat}
        return fallback(key, path, body)

    assert not run(process_nps, seeded["a"], transport=transport)
    assert not sent
    assert survey(owner)["status"] == "pending"


@pytest.mark.parametrize("score", [0, 6, 7, 8, 9, 10])
def test_humanized_service_response_matches_nps_category(
    client, seeded, owner, nps, score
):
    from app.nps_copy import DETRACTOR, PASSIVE, PROMOTER

    handoff(client, seeded, owner, nps)
    sent = []
    run(process_nps, seeded["a"], transport=provider(sent))
    assert sent[-1]["text"].startswith(
        "Sua opinião é fundamental para continuarmos evoluindo! 🚀"
    )
    assert (
        "não recomendaria" in sent[-1]["text"]
        and "com certeza recomendaria" in sent[-1]["text"]
    )
    receive(client, seeded, nps, body=str(score))
    run(process_nps, seeded["a"], transport=provider(sent))
    expected = (
        PROMOTER["service"]
        if score >= 9
        else PASSIVE["service"]
        if score >= 7
        else DETRACTOR["service"]
    )
    assert sent[-1]["text"].startswith(expected)
    assert survey(owner)["question_comment"] == expected
    assert survey(owner)["stage"] == ("closed" if score >= 9 else "comment")
    assert survey(owner)["score"] == score


def test_negative_feedback_reaches_quality_inbox_and_review_is_tenant_scoped(
    client, seeded, owner, nps
):
    handoff(client, seeded, owner, nps)
    run(process_nps, seeded["a"], transport=provider([]))
    receive(client, seeded, nps, body="4")
    data = client.get("/api/v1/nps/quality").json()
    assert data["total"] == 1 and data["rows"][0]["score"] == 4
    id = data["rows"][0]["id"]
    login(client, company="empresa-b")
    assert client.get("/api/v1/nps/quality").json()["total"] == 0
    assert client.post(f"/api/v1/nps/quality/{id}/review", json={}).status_code == 404
    login(client)
    assert client.post(f"/api/v1/nps/quality/{id}/review", json={}).status_code == 204
    assert client.get("/api/v1/nps/quality").json()["total"] == 0
    receive(client, seeded, nps, body="A resposta demorou muito.")
    assert (
        client.get("/api/v1/nps/quality").json()["rows"][0]["comment"]
        == "A resposta demorou muito."
    )
    assert survey(owner)["score"] == 4
    assert client.post(f"/api/v1/nps/quality/{id}/review", json={}).status_code == 409
    payload = {"comment": "A resposta demorou muito."}
    assert (
        client.post(f"/api/v1/nps/quality/{id}/review", json=payload).status_code == 204
    )
    reviewed = survey(owner)["quality_reviewed_at"]
    assert (
        client.post(f"/api/v1/nps/quality/{id}/review", json=payload).status_code == 204
    )
    assert survey(owner)["quality_reviewed_at"] == reviewed


def test_surveys_already_sent_keep_the_legacy_comment_flow(client, seeded, owner, nps):
    handoff(client, seeded, owner, nps)
    run(process_nps, seeded["a"], transport=provider([]))
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE nps_surveys SET template_version=1,question_comment='Pergunta anterior preservada?'"
            )
        )
    receive(client, seeded, nps, body="10")
    sent = []
    run(process_nps, seeded["a"], transport=provider(sent))
    assert sent[-1]["text"].startswith("Pergunta anterior preservada?")
    assert survey(owner)["stage"] == "comment"


def test_unattempted_old_invite_receives_the_new_text_before_sending(
    client, seeded, owner, nps
):
    from app.integration_secrets import encrypt

    handoff(client, seeded, owner, nps)
    with owner.begin() as db:
        db.execute(
            text(
                "UPDATE nps_surveys SET template_version=1,question_score='Texto anterior'"
            )
        )
        db.execute(
            text("UPDATE nps_messages SET body=:body"),
            {"body": encrypt("Texto anterior")},
        )
    sent = []
    run(process_nps, seeded["a"], transport=provider(sent))
    assert sent[-1]["text"].startswith("Sua opinião é fundamental")
    assert survey(owner)["template_version"] == 2
    assert "Sua opinião é fundamental" in survey(owner)["question_score"]
