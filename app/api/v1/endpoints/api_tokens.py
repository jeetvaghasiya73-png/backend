import secrets
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_superadmin_user
from app.repositories.api_token import api_token_repo, api_token_usage_repo
from app.schemas.api_token import ApiTokenCreate, ApiTokenOut, ApiTokenUsageOut

router = APIRouter()


class ApiTokenToggle(BaseModel):
    is_active: bool


@router.get("/", response_model=List[ApiTokenOut])
def read_api_tokens(
    skip: int = 0,
    limit: int = 100,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    superadmin_user=Depends(get_current_superadmin_user),
):
    """
    List API tokens (Superadmin only).
    """
    if user_id:
        return api_token_repo.get_multi_by_user(db, user_id=user_id, skip=skip, limit=limit)
    return api_token_repo.get_multi(db, skip=skip, limit=limit)


from app.repositories.user import user_repo

@router.post("/", response_model=ApiTokenOut, status_code=status.HTTP_201_CREATED)
def create_api_token(
    token_in: ApiTokenCreate,
    db: Session = Depends(get_db),
    superadmin_user=Depends(get_current_superadmin_user),
):
    """
    Create a new API token (Superadmin only).
    """
    target_user_id = superadmin_user.id
    if token_in.user_id:
        target_user = user_repo.get(db, id=token_in.user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="Target user not found")
        if target_user.id != superadmin_user.id and target_user.created_by_id != superadmin_user.id:
            raise HTTPException(status_code=403, detail="You can only assign tokens to yourself or users you created")
        target_user_id = target_user.id

    raw_token = secrets.token_urlsafe(32)
    token_data = {
        "token": raw_token,
        "user_id": target_user_id,
        "description": token_in.description,
        "is_active": token_in.is_active,
        "expires_at": token_in.expires_at,
    }
    return api_token_repo.create(db, obj_in=token_data)


@router.patch("/{token_id}", response_model=ApiTokenOut)
def toggle_api_token(
    token_id: int,
    body: ApiTokenToggle,
    db: Session = Depends(get_db),
    superadmin_user=Depends(get_current_superadmin_user),
):
    """
    Enable or disable an API token (Superadmin only).
    """
    token = api_token_repo.get(db, id=token_id)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")

    token.is_active = body.is_active
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_api_token(
    token_id: int,
    db: Session = Depends(get_db),
    superadmin_user=Depends(get_current_superadmin_user),
):
    """
    Revoke/Delete an API token (Superadmin only).
    """
    token = api_token_repo.get(db, id=token_id)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")

    api_token_repo.remove(db, id=token_id)


@router.get("/{token_id}/usage", response_model=List[ApiTokenUsageOut])
def read_token_usage(
    token_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    superadmin_user=Depends(get_current_superadmin_user),
):
    """
    View usage logs for a specific API token (Superadmin only).
    """
    token = api_token_repo.get(db, id=token_id)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")

    return api_token_usage_repo.get_multi_by_token(
        db, token_id=token_id, skip=skip, limit=limit
    )
