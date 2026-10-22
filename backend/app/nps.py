"""Tenant-scoped NPS configuration, cohort metrics and bounded exports."""

import asyncio
import csv
import io
import secrets
from datetime import date
from html import escape
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import Field
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy import text

from app.identity import Auth, admin, audit, scope
from app.integration_secrets import encrypt
from app.nps_copy import SCORE
from app.reports import boundaries
from app.schemas import Input
from app.whatsapp_chat import chat_access

router = APIRouter(prefix="/api/v1/nps", tags=["NPS"])
COMMENT = {
    "service": "O que podemos melhorar no nosso atendimento?",
    "trip": "O que mais marcou sua experiência e o que podemos melhorar?",
}


class Configuration(Input):
    service_enabled: bool = Field(strict=True)
    trip_enabled: bool = Field(strict=True)


@router.get("/settings")
async def read_settings(actor: Auth):
    chat_access(actor)
    row = (
        (
            await actor.db.execute(
                text(
                    "SELECT service_enabled,trip_enabled FROM nps_settings WHERE company_id=:id"
                ),
                {"id": actor.company_id},
            )
        )
        .mappings()
        .first()
    )
    return dict(row) if row else {"service_enabled": False, "trip_enabled": False}


@router.put("/settings")
async def save_settings(data: Configuration, request: Request, actor: Auth):
    chat_access(actor)
    admin(actor)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        await db.execute(
            text("SELECT id FROM companies WHERE id=:id FOR UPDATE"),
            {"id": actor.company_id},
        )
        await db.execute(
            text("""INSERT INTO nps_settings(company_id,service_enabled,trip_enabled)
          VALUES(:company,:service_enabled,:trip_enabled) ON CONFLICT(company_id) DO UPDATE SET
          service_since=CASE WHEN NOT nps_settings.service_enabled AND EXCLUDED.service_enabled THEN now() ELSE nps_settings.service_since END,
          trip_since=CASE WHEN NOT nps_settings.trip_enabled AND EXCLUDED.trip_enabled THEN now() ELSE nps_settings.trip_since END,
          service_enabled=EXCLUDED.service_enabled,trip_enabled=EXCLUDED.trip_enabled"""),
            data.model_dump() | {"company": actor.company_id},
        )
        if data.service_enabled or data.trip_enabled:
            await db.execute(
                text("""INSERT INTO whatsapp_automation(company_id,secret) VALUES(:company,:secret)
              ON CONFLICT(company_id) DO UPDATE SET next_sync_at=now()"""),
                {
                    "company": actor.company_id,
                    "secret": encrypt(secrets.token_urlsafe(32)),
                },
            )
        await db.execute(
            text("""UPDATE nps_surveys SET stage='closed',status=CASE WHEN score IS NULL THEN 'discarded' ELSE 'answered' END
          WHERE company_id=:company AND stage<>'closed' AND ((kind='service' AND NOT :service_enabled) OR (kind='trip' AND NOT :trip_enabled))"""),
            data.model_dump() | {"company": actor.company_id},
        )
        await audit(
            db,
            actor.company_id,
            actor.user["id"],
            "nps.settings_updated",
            actor.company_id,
        )
    return data.model_dump()


def metrics(rows):
    scores = [r["score"] for r in rows if r["score"] is not None]
    sent = sum(bool(r["sent_at"] or r["score"] is not None) for r in rows)
    promoters = sum(s >= 9 for s in scores)
    detractors = sum(s <= 6 for s in scores)
    return {
        "surveys": len(rows),
        "sent": sent,
        "responses": len(scores),
        "response_rate": round(100 * len(scores) / sent, 1) if sent else None,
        "nps": round(100 * (promoters - detractors) / len(scores), 1)
        if scores
        else None,
        "average": round(sum(scores) / len(scores), 2) if scores else None,
        "promoters": promoters,
        "passives": sum(7 <= s <= 8 for s in scores),
        "detractors": detractors,
    }


async def report_rows(actor, start, end, kind, trip_id, classification, status):
    chat_access(actor)
    lower, upper = boundaries(start, end)
    params = {"company": actor.company_id, "lower": lower, "upper": upper}
    filters = ["s.company_id=:company", "s.created_at>=:lower", "s.created_at<:upper"]
    for name, value, column in [
        ("kind", kind, "s.kind"),
        ("trip", trip_id, "s.trip_id"),
        ("status", status, "s.status"),
    ]:
        if value:
            filters.append(f"{column}=:{name}")
            params[name] = value
    if classification:
        filters.append(
            {
                "promoter": "s.score>=9",
                "passive": "s.score BETWEEN 7 AND 8",
                "detractor": "s.score<=6",
                "unanswered": "s.score IS NULL",
            }[classification]
        )
    rows = [
        dict(r)
        for r in (
            await actor.db.execute(
                text(
                    """SELECT s.id,s.kind,s.contact_name,s.phone,s.trip_id,t.name AS trip_name,
      s.reservation_id,s.operator_id,u.full_name AS operator_name,s.status,s.score,s.comment,
      s.question_score,s.question_comment,s.created_at,s.scheduled_at,s.sent_at,s.expires_at,s.answered_at,s.error_code,
      to_char(s.created_at AT TIME ZONE 'America/Sao_Paulo','YYYY-MM') AS month
      FROM nps_surveys s LEFT JOIN trips t ON t.id=s.trip_id AND t.company_id=s.company_id
      LEFT JOIN users u ON u.id=s.operator_id AND u.company_id=s.company_id WHERE """
                    + " AND ".join(filters)
                    + " ORDER BY s.created_at DESC,s.id LIMIT 5001"
                ),
                params,
            )
        ).mappings()
    ]
    if len(rows) > 5000:
        raise HTTPException(
            422,
            "O período contém mais de 5.000 pesquisas. Reduza o período ou aplique filtros.",
        )
    return rows


@router.get("/report")
async def report(
    actor: Auth,
    start: date,
    end: date,
    kind: Literal["service", "trip"] | None = None,
    trip_id: UUID | None = None,
    classification: Literal["promoter", "passive", "detractor", "unanswered"]
    | None = None,
    status: Literal[
        "pending",
        "sending",
        "sent",
        "uncertain",
        "failed",
        "discarded",
        "answered",
        "skipped",
        "expired",
    ]
    | None = None,
    page: int = Query(1, ge=1, le=100),
    output: Literal["json", "csv", "pdf"] = "json",
):
    rows = await report_rows(actor, start, end, kind, trip_id, classification, status)
    summary = metrics(rows)
    if output == "json":
        months = sorted({r["month"] for r in rows})
        return {
            "summary": summary,
            "by_kind": {k: metrics([r for r in rows if r["kind"] == k]) for k in SCORE},
            "evolution": [
                {"month": m, **metrics([r for r in rows if r["month"] == m])}
                for m in months
            ],
            "rows": rows[(page - 1) * 50 : page * 50],
            "total": len(rows),
            "page": page,
        }
    filename = f"nps-{start}-{end}.{output}"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
    }
    labels = {"service": "Atendimento", "trip": "Viagem"}
    if output == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(
            [
                "Tipo",
                "Viagem",
                "Responsável",
                "Telefone",
                "Situação",
                "Nota",
                "Comentário",
                "Criada em (Brasília)",
                "Respondida em (Brasília)",
            ]
        )
        for r in rows:
            values = [
                labels[r["kind"]],
                r["trip_name"],
                r["contact_name"],
                r["phone"],
                r["status"],
                r["score"],
                r["comment"],
                r["created_at"].astimezone(ZoneInfo("America/Sao_Paulo")).isoformat(),
                r["answered_at"].astimezone(ZoneInfo("America/Sao_Paulo")).isoformat()
                if r["answered_at"]
                else None,
            ]
            writer.writerow(
                [
                    "'" + str(v)
                    if str(v or "").lstrip().startswith(("=", "+", "-", "@"))
                    else (v if v is not None else "")
                    for v in values
                ]
            )
        return Response(
            "\ufeff" + stream.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers=headers,
        )
    stream = io.BytesIO()
    styles = getSampleStyleSheet()
    story = [
        Paragraph("NPS e satisfação", styles["Title"]),
        Paragraph(
            f"Período de criação: {start:%d/%m/%Y} a {end:%d/%m/%Y} (Brasília).",
            styles["Normal"],
        ),
        Paragraph(
            escape(
                f"Filtros: tipo={kind or 'todos'}; viagem={trip_id or 'todas'}; classificação={classification or 'todas'}; situação={status or 'todas'}."
            ),
            styles["Normal"],
        ),
        Paragraph(
            f"NPS: {summary['nps'] if summary['nps'] is not None else 'Sem respostas'} | Respostas: {summary['responses']} | Enviadas: {summary['sent']} | Taxa de resposta: {str(summary['response_rate']) + '%' if summary['response_rate'] is not None else 'Sem envios'}",
            styles["Normal"],
        ),
        Paragraph(
            f"Nota média: {summary['average'] if summary['average'] is not None else 'Sem respostas'} | Promotores: {summary['promoters']} | Neutros: {summary['passives']} | Detratores: {summary['detractors']}",
            styles["Normal"],
        ),
        Spacer(1, 15),
    ]
    for r in rows:
        story.extend(
            [
                Paragraph(
                    escape(
                        f"{labels[r['kind']]} — {r['trip_name'] or 'Atendimento humano'} — {r['contact_name']}"
                    ),
                    styles["Heading3"],
                ),
                Paragraph(
                    escape(
                        f"Nota: {r['score'] if r['score'] is not None else 'Sem resposta'} | Situação: {r['status']} | Telefone: {r['phone']}"
                    ),
                    styles["Normal"],
                ),
                Paragraph(escape(r["comment"] or "Sem comentário."), styles["Normal"]),
                Spacer(1, 8),
            ]
        )
    document = SimpleDocTemplate(
        stream, title="NPS e satisfação", author="Nexus Rotafy"
    )
    await asyncio.to_thread(document.build, story)
    return Response(stream.getvalue(), media_type="application/pdf", headers=headers)


@router.get("/trips")
async def trip_options(actor: Auth):
    chat_access(actor)
    return [
        dict(r)
        for r in (
            await actor.db.execute(
                text(
                    "SELECT DISTINCT t.id,t.name FROM trips t JOIN nps_surveys s ON s.trip_id=t.id AND s.company_id=t.company_id WHERE t.company_id=:company ORDER BY t.name LIMIT 1000"
                ),
                {"company": actor.company_id},
            )
        ).mappings()
    ]


@router.get("/quality")
async def quality(actor: Auth):
    chat_access(actor)
    rows = [
        dict(r)
        for r in (
            await actor.db.execute(
                text("""SELECT s.id,s.contact_name,s.phone,s.kind,s.score,s.comment,s.answered_at,
      t.name AS trip_name,count(*) OVER() AS total FROM nps_surveys s LEFT JOIN trips t ON t.id=s.trip_id AND t.company_id=s.company_id
      WHERE s.company_id=:company AND s.template_version=2 AND s.score<=6 AND s.quality_reviewed_at IS NULL
      ORDER BY s.answered_at,s.id LIMIT 50"""),
                {"company": actor.company_id},
            )
        ).mappings()
    ]
    return {"rows": rows, "total": rows[0]["total"] if rows else 0}


class QualityReview(Input):
    comment: str | None = Field(default=None, max_length=2000)


@router.post("/quality/{survey_id}/review", status_code=204)
async def review_quality(
    survey_id: UUID, data: QualityReview, request: Request, actor: Auth
):
    chat_access(actor)
    async with request.app.state.platform_engine.begin() as db:
        await scope(db, actor.company_id)
        found = await db.scalar(
            text("""UPDATE nps_surveys SET quality_reviewed_at=now(),quality_reviewed_by=:user
          WHERE company_id=:company AND id=:id AND score<=6 AND template_version=2
          AND quality_reviewed_at IS NULL AND comment IS NOT DISTINCT FROM :comment RETURNING id"""),
            {
                "company": actor.company_id,
                "id": survey_id,
                "user": actor.user["id"],
                "comment": data.comment,
            },
        )
        if not found:
            existing = (
                (
                    await db.execute(
                        text(
                            "SELECT comment FROM nps_surveys WHERE company_id=:company AND id=:id AND score<=6 AND template_version=2"
                        ),
                        {"company": actor.company_id, "id": survey_id},
                    )
                )
                .mappings()
                .first()
            )
            if not existing:
                raise HTTPException(404, "Avaliação não encontrada.")
            if existing["comment"] != data.comment:
                raise HTTPException(
                    409,
                    "A avaliação recebeu outro comentário. Confira a versão atual antes de concluir a análise.",
                )
            return
        await audit(
            db, actor.company_id, actor.user["id"], "nps.quality_reviewed", survey_id
        )
