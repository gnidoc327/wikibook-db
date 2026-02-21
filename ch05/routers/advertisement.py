import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ch05.dependencies.auth import get_current_user, get_optional_user
from ch05.dependencies.mongodb import get_database
from ch05.dependencies.mysql import get_session
from ch05.dependencies.valkey import get_client as get_valkey_client
from ch05.models.advertisement import Advertisement
from ch05.models.user import User, UserRole

logger = logging.getLogger(__name__)

_AD_CACHE_KEY = "ad:{ad_id}"
_AD_CACHE_TTL = 3600  # 1시간
_VIEW_HISTORY = "adViewHistory"
_CLICK_HISTORY = "adClickHistory"

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


class AdHistoryResult(BaseModel):
    ad_id: int
    count: int


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


def _yesterday_range() -> tuple[datetime, datetime]:
    """어제 00:00 ~ 오늘 00:00 범위를 반환합니다 (UTC 기준)."""
    today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )
    return today - timedelta(days=1), today


async def _get_history_stats(
    db: AsyncIOMotorDatabase, collection: str
) -> list[AdHistoryResult]:
    """MongoDB Aggregation으로 어제 기준 유니크 사용자/IP 수를 집계합니다."""
    start, end = _yesterday_range()

    # 로그인 사용자(username 있음) 집계
    pipeline_user = [
        {
            "$match": {
                "created_date": {"$gte": start, "$lt": end},
                "username": {"$exists": True, "$ne": None},
            }
        },
        {"$group": {"_id": "$ad_id", "unique_vals": {"$addToSet": "$username"}}},
        {
            "$project": {
                "ad_id": "$_id",
                "count": {"$size": "$unique_vals"},
                "_id": 0,
            }
        },
    ]
    # 익명 사용자(username 없음) 집계 — client_ip로 중복 제거
    pipeline_anon = [
        {
            "$match": {
                "created_date": {"$gte": start, "$lt": end},
                "$or": [
                    {"username": {"$exists": False}},
                    {"username": None},
                ],
            }
        },
        {"$group": {"_id": "$ad_id", "unique_vals": {"$addToSet": "$client_ip"}}},
        {
            "$project": {
                "ad_id": "$_id",
                "count": {"$size": "$unique_vals"},
                "_id": 0,
            }
        },
    ]

    results_user = await db[collection].aggregate(pipeline_user).to_list(None)
    results_anon = await db[collection].aggregate(pipeline_anon).to_list(None)

    total: dict[int, int] = {}
    for r in results_user:
        total[r["ad_id"]] = r["count"]
    for r in results_anon:
        total[r["ad_id"]] = total.get(r["ad_id"], 0) + r["count"]

    return [AdHistoryResult(ad_id=ad_id, count=count) for ad_id, count in total.items()]


# ─── 히스토리 라우트 (/{ad_id} 보다 먼저 등록) ───────────────────────────────


@router.get("/history/view", response_model=list[AdHistoryResult])
async def get_view_history(
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> list[AdHistoryResult]:
    """어제 광고별 고유 조회자 수를 집계합니다 (MongoDB Aggregation)."""
    return await _get_history_stats(db, _VIEW_HISTORY)


@router.get("/history/click", response_model=list[AdHistoryResult])
async def get_click_history(
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> list[AdHistoryResult]:
    """어제 광고별 고유 클릭자 수를 집계합니다 (MongoDB Aggregation)."""
    return await _get_history_stats(db, _CLICK_HISTORY)


# ─── 광고 CRUD ────────────────────────────────────────────────────────────────


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

    await valkey.setex(
        _AD_CACHE_KEY.format(ad_id=ad.id), _AD_CACHE_TTL, json.dumps(_ad_to_dict(ad))
    )

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
    request: Request,
    is_true_view: bool = Query(default=False),
    current_user: User | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
    valkey: aioredis.Redis = Depends(get_valkey_client),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> AdResponse:
    """광고 단건 조회. 광고 존재 확인 후 Valkey 캐시 조회 + MongoDB에 조회 히스토리 기록."""
    key = _AD_CACHE_KEY.format(ad_id=ad_id)
    cached = await valkey.get(key)
    if cached:
        logger.debug("광고 캐시 히트: ad_id=%d", ad_id)
        ad_response = AdResponse(**json.loads(cached))
    else:
        ad = await session.scalar(
            select(Advertisement).where(
                Advertisement.id == ad_id,
                Advertisement.is_deleted == False,
            )
        )
        if ad is None:
            raise HTTPException(status_code=404, detail="Advertisement not found")

        await valkey.setex(key, _AD_CACHE_TTL, json.dumps(_ad_to_dict(ad)))
        ad_response = AdResponse.model_validate(ad)

    username = current_user.username if current_user else None
    await db[_VIEW_HISTORY].insert_one(
        {
            "ad_id": ad_id,
            "username": username,
            "client_ip": request.client.host,
            "is_true_view": is_true_view,
            "created_date": datetime.now(timezone.utc).replace(tzinfo=None),
        }
    )
    return ad_response


@router.post("/{ad_id}/click")
async def click_ad(
    ad_id: int,
    request: Request,
    current_user: User | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> str:
    """광고 클릭 기록. MongoDB에 클릭 히스토리를 저장합니다."""
    ad = await session.scalar(
        select(Advertisement).where(
            Advertisement.id == ad_id,
            Advertisement.is_deleted == False,
        )
    )
    if ad is None:
        raise HTTPException(status_code=404, detail="Advertisement not found")

    username = current_user.username if current_user else None
    await db[_CLICK_HISTORY].insert_one(
        {
            "ad_id": ad_id,
            "username": username,
            "client_ip": request.client.host,
            "created_date": datetime.now(timezone.utc).replace(tzinfo=None),
        }
    )
    return "click"
