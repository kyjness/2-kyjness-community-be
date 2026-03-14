# 강아지 프로필 API. Router → Service. 예외는 전역 handler 처리.
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUser, get_current_user, get_master_db
from app.common import ApiCode, ApiResponse
from app.dogs.schema import SetRepresentativeDogRequest
from app.dogs.service import DogService
from app.users.schema import UserProfileResponse

router = APIRouter(prefix="/users/me/dogs", tags=["dogs"])


@router.patch("/representative", status_code=200, response_model=ApiResponse[UserProfileResponse])
async def set_representative_dog(
    body: SetRepresentativeDogRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    data = await DogService.set_representative_dog(user.id, body.dog_id, db=db)
    return ApiResponse(code=ApiCode.USER_UPDATED, data=data)
