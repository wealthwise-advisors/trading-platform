"""Live replay: create a session (synthetic data, same as ui/live_app.py),
then drive it bar-by-bar over a WebSocket. Mirrors ReplayEngine.step() one
frame per message — the same "one bar per interaction" contract the
Streamlit live dashboard already uses.
"""

import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from src.data.sample_data import generate_sample_data
from src.backtesting.replay_engine import ReplayEngine

from api.deps import get_contract_spec, BASE_PRICES
from api.strategy_registry import build_strategy
from api import replay_store, serializers
from api.schemas.replay import ReplayCreateRequest, ReplayCreateResponse

router = APIRouter(prefix="/replay", tags=["replay"])

_TF_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60}


@router.post("", response_model=ReplayCreateResponse)
def create_replay(req: ReplayCreateRequest):
    spec = get_contract_spec(req.symbol)
    tf_min = _TF_MINUTES.get(req.timeframe, 5)
    total_minutes = (req.end_date - req.start_date).days * 6.5 * 60
    bars = max(int(total_minutes / tf_min), 200)

    df = generate_sample_data(
        symbol=req.symbol,
        start=datetime.combine(req.start_date, datetime.min.time()).replace(hour=9, minute=30),
        bars=bars,
        timeframe_minutes=tf_min,
        base_price=BASE_PRICES.get(req.symbol, 4500.0),
        tick_size=spec["tick_size"],
        save_dir="data/historical",
        tf_label=req.timeframe,
    )

    strategy = build_strategy(req.strategy_id, req.params)
    engine = ReplayEngine(
        strategy=strategy,
        symbol=req.symbol,
        timeframe=req.timeframe,
        initial_capital=req.initial_capital,
        contracts_per_trade=req.contracts_per_trade,
        tick_size=spec["tick_size"],
        tick_value=spec["tick_value"],
        point_value=spec["point_value"],
    )
    engine.load(df)

    replay_id = replay_store.save(engine, df, req.symbol, strategy.name, req.initial_capital)
    _, total = engine.progress
    return ReplayCreateResponse(
        replay_id=replay_id, total_bars=total, symbol=req.symbol,
        strategy_name=strategy.name, initial_capital=req.initial_capital,
    )


@router.websocket("/ws/{replay_id}")
async def replay_ws(websocket: WebSocket, replay_id: str):
    await websocket.accept()
    session = replay_store.get(replay_id)
    if session is None:
        await websocket.send_json({"type": "error", "message": f"Replay {replay_id!r} not found."})
        await websocket.close()
        return

    engine = session.engine
    running = False
    speed = 0.1  # seconds between bars while playing

    try:
        while True:
            try:
                msg = await asyncio.wait_for(
                    websocket.receive_json(), timeout=speed if running else None,
                )
                action = msg.get("action")
                if action == "play":
                    running = True
                elif action == "pause":
                    running = False
                elif action == "set_speed":
                    speed = max(0.01, float(msg.get("speed", speed)))
                elif action == "reset":
                    engine.reset()
                    engine.load(session.df)
                    running = False
                    await websocket.send_json({"type": "reset"})
            except asyncio.TimeoutError:
                pass  # no control message this tick — fall through to stepping

            if running:
                if engine.is_done:
                    running = False
                    await websocket.send_json({"type": "done"})
                else:
                    frame = engine.step()
                    await websocket.send_json({"type": "frame", **serializers.frame_to_dict(frame)})
    except WebSocketDisconnect:
        pass


@router.get("/{replay_id}")
def get_replay_meta(replay_id: str):
    session = replay_store.get(replay_id)
    if session is None:
        raise HTTPException(404, f"Replay {replay_id!r} not found.")
    _, total = session.engine.progress
    return {
        "replay_id": replay_id, "total_bars": total, "symbol": session.symbol,
        "strategy_name": session.strategy_name, "initial_capital": session.initial_capital,
    }
