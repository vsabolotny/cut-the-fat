from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_auth
from ..database import get_db
from ..services.insights import get_insights
from ..schemas.insights import InsightsResponse

router = APIRouter(prefix="/api/insights", tags=["insights"], dependencies=[Depends(require_auth)])


@router.get("", response_model=InsightsResponse)
async def insights_endpoint(
    force: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> InsightsResponse:
    result = await get_insights(db, force=force)
    return InsightsResponse(**result)
