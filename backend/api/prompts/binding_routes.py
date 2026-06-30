from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.models import Account, PromptTemplate
from repositories import prompt_repo
from schemas.prompt import PromptBindingResponse, PromptBindingUpsertRequest

from .dependencies import get_db

router = APIRouter()


@router.post(
    "/bindings",
    response_model=PromptBindingResponse,
    response_model_exclude_none=True,
)
def upsert_prompt_binding(
    payload: PromptBindingUpsertRequest,
    db: Session = Depends(get_db),
) -> PromptBindingResponse:
    if not payload.account_id:
        raise HTTPException(status_code=400, detail="accountId is required")
    if not payload.prompt_template_id:
        raise HTTPException(status_code=400, detail="promptTemplateId is required")

    account = db.get(Account, payload.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    template = db.get(PromptTemplate, payload.prompt_template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Prompt template not found")

    try:
        binding = prompt_repo.upsert_binding(
            db,
            account_id=payload.account_id,
            prompt_template_id=payload.prompt_template_id,
            updated_by=payload.updated_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return PromptBindingResponse(
        id=binding.id,
        account_id=account.id,
        account_name=account.name,
        account_model=account.model,
        prompt_template_id=binding.prompt_template_id,
        prompt_key=template.key,
        prompt_name=template.name,
        updated_by=binding.updated_by,
        updated_at=binding.updated_at,
    )


@router.delete("/bindings/{binding_id}")
def delete_prompt_binding_endpoint(binding_id: int, db: Session = Depends(get_db)) -> dict:
    """Soft delete a prompt binding."""
    from services.entity_deletion_service import delete_prompt_binding

    result = delete_prompt_binding(db, binding_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Binding not found"))
    return result
