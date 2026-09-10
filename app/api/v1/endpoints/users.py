from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_superadmin_user
from app.repositories.user import user_repo
from app.schemas.user import UserOut, UserCreateAdmin, UserUpdate
from app.core.security import get_password_hash

router = APIRouter()


@router.get("/", response_model=List[UserOut])
@router.get("/admin-users", response_model=List[UserOut])
def read_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    superadmin_user=Depends(get_current_superadmin_user),
):
    """
    List all dashboard users (Super Admin only).
    """
    return user_repo.get_multi(db, skip=skip, limit=limit)


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@router.post("/admin-users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreateAdmin,
    db: Session = Depends(get_db),
    superadmin_user=Depends(get_current_superadmin_user),
):
    """
    Create a new admin user (Super Admin only).
    """
    existing = user_repo.get_by_username(db, username=user_in.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this username already exists",
        )

    # Only an existing Main Admin can grant Main Admin role
    is_main_admin = user_in.is_main_admin if getattr(superadmin_user, "is_main_admin", False) else False

    hashed_pwd = get_password_hash(user_in.password)
    user_data = {
        "username": user_in.username,
        "hashed_password": hashed_pwd,
        "is_active": True,
        "is_admin": True,
        "is_superadmin": user_in.is_superadmin or is_main_admin,
        "is_main_admin": is_main_admin,
        "created_by_id": superadmin_user.id,
    }
    return user_repo.create(db, obj_in=user_data)


@router.patch("/{user_id}", response_model=UserOut)
@router.patch("/admin-users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    superadmin_user=Depends(get_current_superadmin_user),
):
    """
    Update a user's details (Super Admin only).
    Main Admin account cannot be modified by ordinary Super Admins.
    """
    user = user_repo.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    is_caller_main_admin = getattr(superadmin_user, "is_main_admin", False)
    target_is_main_admin = getattr(user, "is_main_admin", False)

    # Protect Main Admin account from being modified by non-main admins
    if target_is_main_admin and not is_caller_main_admin and user.id != superadmin_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Main Admin can modify a Main Admin account",
        )

    # Prevent superadmin from demoting themselves
    if user.id == superadmin_user.id and user_in.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account",
        )

    update_data = user_in.model_dump(exclude_unset=True)

    # Only Main Admin can promote someone to Main Admin
    if "is_main_admin" in update_data and not is_caller_main_admin:
        update_data.pop("is_main_admin")

    # Hash the new password if provided
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(user, field, value)

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@router.delete("/admin-users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    superadmin_user=Depends(get_current_superadmin_user),
):
    """
    Deactivate/remove a user account (Super Admin only).
    Super Admins CANNOT remove the Main Admin.
    Cannot delete your own account.
    """
    user = user_repo.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == superadmin_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )

    # Main Admin cannot be deleted by anyone (including other super admins)
    if getattr(user, "is_main_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Main Admin account cannot be removed or deleted",
        )

    user_repo.remove(db, id=user_id)

@router.get("/jwt-usage")
def read_jwt_usages(
    page: int = 1,
    limit: int = 20,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_superadmin_user),
):
    """
    List JWT access token usage logs with pagination (Super Admin only).
    """
    from app.models.jwt_usage import JwtTokenUsage
    import math
    total = db.query(JwtTokenUsage).count()
    skip = (page - 1) * limit
    usages = db.query(JwtTokenUsage).order_by(JwtTokenUsage.id.desc()).offset(skip).limit(limit).all()
    pages = math.ceil(total / limit) if limit > 0 else 0
    return {
        "items": [
            {
                "id": u.id,
                "user_id": u.user_id,
                "username": u.username,
                "token_hash": u.token_hash,
                "endpoint": u.endpoint,
                "ip_address": u.ip_address,
                "user_agent": u.user_agent,
                "status_code": u.status_code,
                "duration_ms": u.duration_ms,
                "used_at": u.used_at.isoformat() if u.used_at else None
            }
            for u in usages
        ],
        "total": total,
        "page": page,
        "pages": pages,
        "limit": limit
    }
