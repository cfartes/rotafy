"""Capacidades operacionais independentes dos planos e perfis de usuário."""

from fastapi import HTTPException
from sqlalchemy import text


def capabilities(profile):
    return {
        "packages": profile == "tourism",
        "multi_destination": profile == "tourism",
        "single_trips": True,
        "routes": True,
        "boarding": True,
        "recurring_lines": False,
        "independent_segments": False,
    }


async def require_tourism(db, company_id=None):
    profile = await db.scalar(
        text(
            "SELECT operational_profile FROM companies WHERE id=COALESCE(:company, nullif(current_setting('app.company_id',true),'')::uuid)"
        ),
        {"company": company_id},
    )
    if profile != "tourism":
        raise HTTPException(
            403, "Pacotes estão disponíveis somente para Turismo e transfers."
        )


async def change_profile(db, company_id, previous, desired, expected, actor_id):
    from app.identity import audit, scope

    if desired is None:
        return
    if expected != previous:
        raise HTTPException(
            409, "O perfil da empresa mudou. Atualize o cadastro antes de salvar."
        )
    if desired == previous:
        return
    await scope(db, company_id)
    if desired == "regular" and await db.scalar(
        text(
            "SELECT EXISTS(SELECT 1 FROM trips WHERE company_id=:company AND (package_id IS NOT NULL OR mode='multi_destination') AND status IN ('scheduled','in_progress'))"
        ),
        {"company": company_id},
    ):
        raise HTTPException(
            409,
            "Conclua ou cancele as viagens vinculadas a pacotes antes de mudar para Transporte regular.",
        )
    await db.execute(
        text("UPDATE companies SET operational_profile=:profile WHERE id=:company"),
        {"company": company_id, "profile": desired},
    )
    await audit(
        db,
        company_id,
        actor_id,
        f"company.profile_changed.{previous}.{desired}",
        company_id,
    )
