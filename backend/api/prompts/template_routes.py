from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from repositories import prompt_repo
from schemas.prompt import (
    PromptBindingResponse,
    PromptListResponse,
    PromptTemplateCopyRequest,
    PromptTemplateCreateRequest,
    PromptTemplateNameUpdateRequest,
    PromptTemplateResponse,
    PromptTemplateUpdateRequest,
)

from .dependencies import get_db

router = APIRouter()


# Support both /api/prompts and /api/prompts/
@router.get("", response_model=PromptListResponse, response_model_exclude_none=True)
@router.get("/", response_model=PromptListResponse, response_model_exclude_none=True)
def list_prompt_templates(db: Session = Depends(get_db)) -> PromptListResponse:
    templates = prompt_repo.get_all_templates(db)
    bindings = prompt_repo.list_bindings(db)

    template_responses = [PromptTemplateResponse.from_orm(template) for template in templates]

    binding_responses = []
    for binding, account, template in bindings:
        binding_responses.append(
            PromptBindingResponse(
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
        )

    return PromptListResponse(templates=template_responses, bindings=binding_responses)


@router.put("/{key}", response_model=PromptTemplateResponse, response_model_exclude_none=True)
def update_prompt_template(
    key: str,
    payload: PromptTemplateUpdateRequest,
    db: Session = Depends(get_db),
) -> PromptTemplateResponse:
    try:
        template = prompt_repo.update_template(
            db,
            key=key,
            template_text=payload.template_text,
            description=payload.description,
            updated_by=payload.updated_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return PromptTemplateResponse.from_orm(template)


# Restore endpoint removed - dangerous operation that overwrites user customizations


@router.post("", response_model=PromptTemplateResponse, response_model_exclude_none=True)
@router.post("/", response_model=PromptTemplateResponse, response_model_exclude_none=True)
def create_prompt_template(
    payload: PromptTemplateCreateRequest,
    db: Session = Depends(get_db),
) -> PromptTemplateResponse:
    """Create a new user-defined prompt template"""
    try:
        template = prompt_repo.create_user_template(
            db,
            name=payload.name,
            description=payload.description,
            template_text=payload.template_text,
            created_by=payload.created_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PromptTemplateResponse.from_orm(template)


@router.post(
    "/{template_id}/copy",
    response_model=PromptTemplateResponse,
    response_model_exclude_none=True,
)
def copy_prompt_template(
    template_id: int,
    payload: PromptTemplateCopyRequest,
    db: Session = Depends(get_db),
) -> PromptTemplateResponse:
    """Copy an existing template to create a new one"""
    try:
        template = prompt_repo.copy_template(
            db,
            template_id=template_id,
            new_name=payload.new_name,
            created_by=payload.created_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return PromptTemplateResponse.from_orm(template)


@router.delete("/{template_id}")
def delete_prompt_template_endpoint(template_id: int, db: Session = Depends(get_db)) -> dict:
    """Soft delete a prompt template with dependency checking."""
    from services.entity_deletion_service import delete_prompt_template

    result = delete_prompt_template(db, template_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Template not found"))
    return result


@router.patch(
    "/{template_id}/name",
    response_model=PromptTemplateResponse,
    response_model_exclude_none=True,
)
def update_prompt_template_name(
    template_id: int,
    payload: PromptTemplateNameUpdateRequest,
    db: Session = Depends(get_db),
) -> PromptTemplateResponse:
    """Update template name and description"""
    try:
        template = prompt_repo.update_template_name(
            db,
            template_id=template_id,
            name=payload.name,
            description=payload.description,
            updated_by=payload.updated_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return PromptTemplateResponse.from_orm(template)
