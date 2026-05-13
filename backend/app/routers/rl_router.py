from fastapi import APIRouter

router = APIRouter()


@router.get("/rl/state")
async def get_rl_state():
    """Return RL ensemble state stub. Phase 5 will populate agents and regime weights."""
    return {
        "agents": [],
        "regime_weights": {},
        "note": "RL ensemble not yet initialised — populated in Phase 5",
    }
