"""RL router."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import RLCheckpoint, RLEpisode, get_db
from api.models.schemas import RLEpisodeOut, RLMetrics, TaskSubmitted
from api.services.auth import get_current_user

router = APIRouter(prefix="/rl", tags=["rl"])


@router.get("/episodes", response_model=list[RLEpisodeOut])
async def list_rl_episodes(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> list[RLEpisodeOut]:
    """Return last 200 RL episodes for reward curve plotting."""
    result = await db.execute(
        select(RLEpisode).order_by(RLEpisode.created_at.desc()).limit(200)
    )
    episodes = result.scalars().all()
    # Return in ascending order for chart
    episodes = list(reversed(episodes))
    return [
        RLEpisodeOut(
            id=ep.id,
            position_id=ep.position_id,
            action=float(ep.action),
            reward=float(ep.reward),
            done=bool(ep.done),
            created_at=ep.created_at,
        )
        for ep in episodes
    ]


@router.get("/factors", response_model=RLMetrics)
async def get_rl_factors(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> RLMetrics:
    """Return FF5 betas and metrics from the most recent active RL checkpoint."""
    # Get active checkpoint
    ckpt_result = await db.execute(
        select(RLCheckpoint)
        .where(RLCheckpoint.is_active == True)
        .order_by(RLCheckpoint.created_at.desc())
        .limit(1)
    )
    checkpoint = ckpt_result.scalar_one_or_none()

    # Total episode count
    from sqlalchemy import func
    count_result = await db.execute(select(func.count(RLEpisode.id)))
    episode_count: int = count_result.scalar_one_or_none() or 0

    if checkpoint is None:
        return RLMetrics(
            episode_count=episode_count,
            mean_reward_20=None,
            last_trained_at=None,
            factor_betas=None,
        )

    factor_betas: dict | None = checkpoint.factor_betas
    if factor_betas and not isinstance(factor_betas, dict):
        factor_betas = dict(factor_betas)

    return RLMetrics(
        episode_count=episode_count,
        mean_reward_20=float(checkpoint.mean_reward_20) if checkpoint.mean_reward_20 else None,
        last_trained_at=checkpoint.created_at,
        factor_betas=factor_betas,
    )


@router.post("/train", response_model=TaskSubmitted)
async def trigger_rl_training(
    _user: str = Depends(get_current_user),
) -> TaskSubmitted:
    """Enqueue the train_rl_model Celery task and return the task ID."""
    from worker.celery_app import celery_app

    task = celery_app.send_task("worker.tasks.rl_tasks.train_rl_model")
    return TaskSubmitted(task_id=str(task.id), status="queued")
