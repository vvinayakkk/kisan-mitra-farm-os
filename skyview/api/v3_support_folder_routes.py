"""Farmer-owned preparation flags, separate from official scheme eligibility."""

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import text

from skyview.api.v3_routes import Owner
from skyview.data.v3 import db, repository

router = APIRouter(prefix="/api/support-folder", tags=["Farm support folder"])


class Preparation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    row_version: int = Field(ge=0)
    eligibility_reviewed: StrictBool
    documents_reviewed: StrictBool
    application_reviewed: StrictBool


def _programme(conn, scheme_id):
    if not conn.execute(
        text("SELECT 1 FROM sv3.scheme_versions WHERE id=:id"), {"id": scheme_id}
    ).scalar():
        raise HTTPException(404, "This programme is not in the support catalogue.")


@router.get("/{scheme_id}")
def read_preparation(scheme_id: UUID, owner: Owner):
    with db.connection(owner) as conn:
        _programme(conn, scheme_id)
        result = repository.rows(
            conn,
            "SELECT * FROM sv3.support_folder_preparation WHERE farmer_id=:owner AND scheme_version_id=:id",
            {"owner": owner, "id": scheme_id},
        )
    return (
        result[0]
        if result
        else {
            "scheme_version_id": str(scheme_id),
            "row_version": 0,
            "eligibility_reviewed": False,
            "documents_reviewed": False,
            "application_reviewed": False,
            "updated_at": None,
        }
    )


@router.put("/{scheme_id}")
def save_preparation(scheme_id: UUID, body: Preparation, owner: Owner):
    values = {**body.model_dump(), "owner": owner, "id": scheme_id}
    with db.connection(owner, write=True) as conn:
        _programme(conn, scheme_id)
        if body.row_version == 0:
            query = """INSERT INTO sv3.support_folder_preparation(farmer_id,scheme_version_id,eligibility_reviewed,documents_reviewed,application_reviewed)
                VALUES(:owner,:id,:eligibility_reviewed,:documents_reviewed,:application_reviewed)
                ON CONFLICT(farmer_id,scheme_version_id) DO NOTHING RETURNING *"""
        else:
            query = """UPDATE sv3.support_folder_preparation SET eligibility_reviewed=:eligibility_reviewed,documents_reviewed=:documents_reviewed,
                application_reviewed=:application_reviewed,row_version=row_version+1,updated_at=now()
                WHERE farmer_id=:owner AND scheme_version_id=:id AND row_version=:row_version RETURNING *"""
        saved = repository.rows(conn, query, values)
        if not saved:
            raise HTTPException(
                409, "This checklist changed elsewhere. Reload it before saving again."
            )
        return saved[0]
