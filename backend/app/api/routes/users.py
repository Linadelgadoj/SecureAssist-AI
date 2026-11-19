"""Cuenta propia y administración de usuarios (roles)."""
from uuid import UUID

from fastapi import APIRouter, Depends

from app.application.users import UserService
from app.dependencies.auth import get_current_account, get_current_admin
from app.dependencies.services import get_user_service
from app.domain.users import AppUser, Role
from app.schemas.users import AccountResponse, UserUpdate

router = APIRouter(tags=["users"])


def _account(user: AppUser) -> AccountResponse:
    return AccountResponse(id=user.id, email=user.email, full_name=user.full_name,
                           role=user.role.value, is_active=user.is_active)


@router.get("/me", response_model=AccountResponse)
async def me(account: AppUser = Depends(get_current_account)):
    return _account(account)


@router.get("/users", response_model=list[AccountResponse])
async def list_users(
    admin: AppUser = Depends(get_current_admin),
    users: UserService = Depends(get_user_service),
):
    return [_account(user) for user in await users.list_users(admin)]


@router.patch("/users/{user_id}", response_model=AccountResponse)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    admin: AppUser = Depends(get_current_admin),
    users: UserService = Depends(get_user_service),
):
    updated = await users.update_user(
        admin, str(user_id), role=Role(payload.role) if payload.role else None, is_active=payload.is_active
    )
    return _account(updated)
