import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_current_user, rate_limit_user_action
from app.services.account_deletion import AccountDeletionError, account_deletion_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["account"])


@router.delete(
    "/account",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_user_action("account-delete", limit=3, window_seconds=86400))],
)
async def delete_account(request: Request, user: dict = Depends(get_current_user)):
    user_id = user.get("uid")
    scheme, _, access_token = request.headers.get("Authorization", "").partition(" ")
    if not user_id or scheme.lower() != "bearer" or not access_token.strip():
        raise HTTPException(status_code=401, detail="A valid Supabase access token is required.")

    try:
        await run_in_threadpool(account_deletion_service.delete_account, str(user_id), access_token.strip())
    except AccountDeletionError as error:
        logger.warning("Account deletion failed (%s)", type(error.__cause__ or error).__name__)
        raise HTTPException(
            status_code=503,
            detail="Account deletion could not be completed. Please try again later.",
        ) from error
    return {"status": "deleted"}
