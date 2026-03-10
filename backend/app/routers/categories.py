from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_auth
from ..database import get_db
from ..models.category import Category

router = APIRouter(prefix="/api/categories", tags=["categories"], dependencies=[Depends(require_auth)])


class CategoryOut(BaseModel):
    id: int
    name: str
    color: str

    model_config = {"from_attributes": True}


@router.get("", response_model=list[CategoryOut])
async def list_categories(db: AsyncSession = Depends(get_db)) -> list[CategoryOut]:
    result = await db.execute(select(Category).order_by(Category.id))
    return [CategoryOut.model_validate(c) for c in result.scalars()]
