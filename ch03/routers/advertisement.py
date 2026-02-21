import json
import logging
from datetime import datetime
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ch03.dependencies.auth import get_current_user
from ch03.dependencies.mysql import get_session
from ch03.dependencies.valkey import get_client as get_valkey_client
from ch03.models.advertisement import Advertisement
from ch03.models.user import User, UserRole

logger = logging.getLogger(__name__)

_AD_CACHE_KEY = "ad:{ad_id}"

router = APIRouter(prefix="/ads", tags=["Advertisements"])


class WriteAdRequest(BaseModel):
    title: str
    content: str = ""
    is_visible: bool = True
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    view_count: int = 0
    click_count: int = 0


class AdResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    is_visible: bool
    is_deleted: bool
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    view_count: int
    click_count: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


def _ad_to_dict(ad: Advertisement) -> dict:
    return {
        "id": ad.id,
        "title": ad.title,
        "content": ad.content,
        "is_visible": ad.is_visible,
        "is_deleted": ad.is_deleted,
        "start_date": ad.start_date.isoformat() if ad.start_date else None,
        "end_date": ad.end_date.isoformat() if ad.end_date else None,
        "view_count": ad.view_count,
        "click_count": ad.click_count,
        "created_at": ad.created_at.isoformat() if ad.created_at else None,
        "updated_at": ad.updated_at.isoformat() if ad.updated_at else None,
    }


@router.post("", response_model=AdResponse, status_code=201)
async def write_ad(
    body: WriteAdRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    valkey: aioredis.Redis = Depends(get_valkey_client),
) -> Advertisement:
    """광고 등록 (admin 전용). 등록 후 Valkey에 캐싱합니다."""
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=403, detail="관리자만 광고를 등록할 수 있습니다."
        )

    ad = Advertisement(
        title=body.title,
        content=body.content,
        is_visible=body.is_visible,
        start_date=body.start_date,
        end_date=body.end_date,
        view_count=body.view_count,
        click_count=body.click_count,
    )
    session.add(ad)
    await session.commit()
    await session.refresh(ad)

    await valkey.set(_AD_CACHE_KEY.format(ad_id=ad.id), json.dumps(_ad_to_dict(ad)))

    return ad


@router.get("", response_model=list[AdResponse])
async def get_ads(
    session: AsyncSession = Depends(get_session),
) -> list[Advertisement]:
    """광고 목록 조회"""
    result = await session.scalars(
        select(Advertisement).where(Advertisement.is_deleted == False)
    )
    return list(result.all())


@router.get("/{ad_id}", response_model=AdResponse)
async def get_ad(
    ad_id: int,
    session: AsyncSession = Depends(get_session),
    valkey: aioredis.Redis = Depends(get_valkey_client),
) -> AdResponse:
    """광고 단건 조회. Valkey 캐시를 먼저 확인하고 없으면 DB에서 조회합니다."""
    key = _AD_CACHE_KEY.format(ad_id=ad_id)
    cached = await valkey.get(key)
    if cached:
        logger.debug("광고 캐시 히트: ad_id=%d", ad_id)
        data = json.loads(cached)
        return AdResponse(**data)

    ad = await session.scalar(
        select(Advertisement).where(
            Advertisement.id == ad_id,
            Advertisement.is_deleted == False,
        )
    )
    if ad is None:
        raise HTTPException(status_code=404, detail="Advertisement not found")

    await valkey.set(key, json.dumps(_ad_to_dict(ad)))
    return ad
