# 강아지 프로필 API. Router → Service. 예외는 전역 handler 처리.
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUser, get_current_user, get_master_db
from app.common import ApiCode, ApiResponse, api_response
from app.dogs.schema import SetRepresentativeDogRequest
from app.dogs.service import DogService
from app.users.schema import UserProfileResponse

router = APIRouter(prefix="/users/me/dogs", tags=["dogs"])


@router.patch("/representative", status_code=200, response_model=ApiResponse[UserProfileResponse])
async def set_representative_dog(
    request: Request,
    body: SetRepresentativeDogRequest,  # JSON: dogId → dog_id (BaseSchema alias)
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    data = await DogService.set_representative_dog(user.id, body.dog_id, db=db)
    return api_response(request, code=ApiCode.DOG_UPDATED, data=data)
