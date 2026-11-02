"""One independent APK welcome per newly registered driver or guide."""

from uuid import uuid4

from sqlalchemy import text

from app.integration_secrets import encrypt
from app.modules import enabled


async def queue_crew_apk(db, settings, company_id, user):
    if user["role"] not in {"driver", "guide"}:
        return None
    if not user.get("contact_phone"):
        return "missing_phone"
    if not await enabled(db, company_id, "whatsapp"):
        return "module_disabled"
    session = await db.scalar(
        text("""SELECT session_id FROM company_whatsapp
        WHERE company_id=:company AND enabled"""),
        {"company": company_id},
    )
    if not session or not await db.scalar(
        text("SELECT 1 FROM integration_settings WHERE id AND openwa_key<>''")
    ):
        return "not_configured"
    company = await db.scalar(
        text("SELECT trade_name FROM companies WHERE id=:id"), {"id": company_id}
    )
    link = (
        settings.public_base_url.rstrip("/") + "/api/v1/public/mobile/latest/download"
    )
    body = (
        f"Olá, {user['full_name']}!\n\nSeu acesso à equipe de {company} foi cadastrado. "
        f"Baixe o aplicativo Android para consultar suas viagens e registrar embarques e desembarques:\n\n{link}\n\n"
        "Após instalar, entre com o identificador da empresa, seu e-mail e sua senha. "
        "Se ainda não definiu a senha, utilize o convite de acesso recebido. O aplicativo é para Android."
    )
    await db.execute(
        text("""INSERT INTO whatsapp_outbox
        (id,company_id,session_id,kind,dedupe_key,phone,body,user_id,expires_at)
        VALUES(:id,:company,:session,'crew_apk',:key,:phone,:body,:user,now()+interval '7 days')
        ON CONFLICT(company_id,dedupe_key) DO NOTHING"""),
        {
            "id": uuid4(),
            "company": company_id,
            "session": session,
            "key": f"crew-apk:{user['id']}",
            "phone": user["contact_phone"],
            "body": encrypt(body),
            "user": user["id"],
        },
    )
    return "pending"
