"""Live replay: create a session, then drive it bar-by-bar over a WebSocket.

Two things changed when the multi-timeframe grid was added:

  * A session is now a MultiReplaySession -- one ReplayEngine per selected
    timeframe, all advanced off one shared market clock (see
    src/backtesting/multi_replay.py for why the clock is measured in market
    time rather than in bars). A single-timeframe session is a grid of one, so
    the original behaviour is the degenerate case of the new one rather than a
    separate path.

  * Bars are fetched at a resolution that DIVIDES every selected timeframe,
    not simply at the finest one. With 1m/5m/15m/30m/1h that was the same
    number, because those form a divisibility chain. Timeframes like 25m and
    35m do not: building a 25m bar out of 15m bars would group 15 or 30
    minutes of trade into it. See _source_timeframe below.

  * Data no longer has to be synthetic. `data_source` accepts the same values
    the backtest endpoint does and is resolved through the same
    _build_provider(), so CSV and Schwab work here too. Bars are fetched once
    at the FINEST selected timeframe and resampled upward by the session --
    fetching each timeframe separately would risk the panes disagreeing about
    the same minute of the market.
"""

import asyncio
from datetime import datetime, time as time_type, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from src.data.sample_data import generate_sample_data
from src.backtesting.multi_replay import (
    MultiReplaySession, TF_MINUTES, trim_to_closed_bars,
)

from api.deps import get_contract_spec, BASE_PRICES
from api.strategy_registry import build_strategy
from api.routers.backtests import _build_provider
from api import auth, replay_store, serializers
from api.schemas.replay import ReplayCreateRequest, ReplayCreateResponse

router = APIRouter(prefix="/replay", tags=["replay"])

#: The websocket lives on its own router because include_router's
#: `dependencies=` applies to websocket routes as well, and an HTTP dependency
#: expecting a Request cannot be resolved for a socket handshake. This one is
#: mounted WITHOUT that dependency and authenticates itself in replay_ws,
#: before accept().
ws_router = APIRouter(prefix="/replay", tags=["replay"])

_TF_MINUTES = TF_MINUTES

#: Resolutions we are willing to ASK a provider for. Deliberately a short list
#: of round intervals: Schwab only serves 1/5/10/15/30-minute bars, and the CSV
#: provider stores 1m and resamples, so requesting "35m" from either is either
#: an error or a silent client-side resample we would rather do ourselves.
_FETCHABLE = ("1m", "5m", "10m", "15m", "30m", "1h")


def _source_timeframe(timeframes: list[str]) -> str:
    """
    Always 1-minute. Every pane is built from it.

    This used to pick the COARSEST resolution that still divides every selected
    timeframe -- the cheapest fetch that can build the panes faithfully. That
    reasoning is sound for OHLCV and wrong for VWAP, because VWAP needs
    something OHLCV does not: the price distribution INSIDE each bar.

    A broker platform accumulates each bar's own volume-weighted price. We
    approximate that from the minutes inside the bar (see
    resample_ohlcv(with_vwap_price=True)). If the source IS the pane's own
    resolution there are no minutes inside it, the approximation collapses to
    (H+L+C)/3, and the value silently changes:

        selected            source    VWAP of the 30m bar opening 13:00 CT
        30m alone           30m       7810.2336     <- reference showed 7809.89
        1m + 30m            1m        7809.9279

    Same closed bar, two answers, decided by a UI toggle -- the same class of
    non-determinism that the shared aggregator was introduced to kill, resurfacing
    one layer up. The cheap fetch is not worth it: one day of ES is ~1,380 1-minute
    bars against 46 at 30m, which is nothing next to a number on screen that moves
    when you tick a checkbox.

    It also makes every timeframe addable mid-session without a refetch, since
    1m divides all of them.
    """
    return "1m"


def _is_overnight(session_start, session_end) -> bool:
    """A session whose end clock-time precedes its start spans midnight."""
    return (session_start is not None and session_end is not None
            and session_end < session_start)


def _fetch_start(req: ReplayCreateRequest):
    """
    First calendar day to FETCH, which is not always the first day to show.

    An overnight session beginning at 18:00 starts the previous calendar day, so
    the session containing 09:40 on the 13th began at 18:00 on the 12th. Fetching
    only the 13th silently truncates it: the bars are still filtered correctly,
    but the VWAP anchor falls on the first bar present -- midnight -- instead of
    the session open, and every VWAP and band for that morning comes out wrong
    with nothing to indicate it. Measured on ES 5m at 2026-08-13 09:40:

        18:00-17:00, fetched 08-13 only   VWAP 7791.19  sigma 9.717
        18:00-17:00, fetched 08-12..13    VWAP 7788.38  sigma 11.572  <- correct

    So an overnight session pulls one extra day of history. It costs one day of
    bars and removes an entire class of silently-wrong numbers.
    """
    if _is_overnight(req.session_start, req.session_end):
        return req.start_date - timedelta(days=1)
    return req.start_date


def _load_bars(req: ReplayCreateRequest, source_tf: str, spec: dict):
    """Bars at the session's source resolution, from whichever provider was picked."""
    base_tf = source_tf
    tf_min = _TF_MINUTES[source_tf]
    fetch_start = _fetch_start(req)

    if req.data_source == "synthetic":
        total_minutes = max((req.end_date - req.start_date).days, 1) * 6.5 * 60
        bars = max(int(total_minutes / tf_min), 200)
        return generate_sample_data(
            symbol=req.symbol,
            start=datetime.combine(req.start_date, datetime.min.time()).replace(hour=9, minute=30),
            bars=bars,
            timeframe_minutes=tf_min,
            base_price=BASE_PRICES.get(req.symbol, 4500.0),
            tick_size=spec["tick_size"],
            save_dir="data/historical",
            tf_label=base_tf,
        )

    provider = _build_provider(req.data_source, req.symbol, base_tf,
                               fetch_start, req.end_date, spec,
                               session_start=req.session_start)
    try:
        df = provider.load(
            req.symbol,
            datetime.combine(fetch_start, time_type(0, 0)),
            datetime.combine(req.end_date, time_type(23, 59)),
            base_tf,
        )
    except FileNotFoundError as exc:
        # The CSV corpus only holds the symbols someone has actually exported.
        # This used to escape as a bare 500 "Internal Server Error", which said
        # nothing about the one thing the user had to change.
        raise HTTPException(
            400,
            f"No '{req.data_source}' data for {req.symbol}. {exc} "
            f"Pick a symbol that has been exported, or switch the data source "
            f"to Synthetic or Live (Schwab).",
        )
    except HTTPException:
        raise
    except Exception as exc:                                  # noqa: BLE001
        # Any other provider failure (unreadable file, malformed columns, a
        # broker API refusing the request) is a bad-request condition from the
        # caller's point of view, not a server defect, and the message is the
        # only thing that tells them which input to change.
        raise HTTPException(
            400, f"Could not load {req.symbol} {base_tf} from '{req.data_source}': {exc}")
    if df is None or df.empty:
        raise HTTPException(
            400,
            f"No {req.symbol} {base_tf} data from '{req.data_source}' between "
            f"{req.start_date} and {req.end_date}.",
        )
    return df


def _apply_session(df, session_start, session_end):
    """Keep only in-session bars, mirroring BacktestEngine's filter.

    A window whose end is BEFORE its start (18:00-17:00) is an overnight
    session, so the mask is a union rather than an intersection -- the same
    reading the backtest engine uses.

    A bar is IN the session when its whole span is: the comparison against
    session_end is strict, because a bar whose open sits exactly on the end
    closes one interval AFTER it. With an inclusive end, a 09:30-17:00 request
    kept a 1-minute bar opening 17:00 and running to 17:01, so the session ran a
    minute long and RTH came out at 391 bars instead of the conventional 390.
    """
    if df is None or df.empty or (session_start is None and session_end is None):
        return df
    t = df.index.time
    if session_start and session_end:
        if session_start <= session_end:
            mask = (t >= session_start) & (t < session_end)
        else:
            mask = (t >= session_start) | (t < session_end)
    elif session_start:
        mask = t >= session_start
    else:
        mask = t < session_end
    return df[mask]


def _market_now() -> datetime:
    """
    Now, as a naive Eastern datetime -- the frame every bar timestamp is in.

    SchwabProvider converts each candle to America/New_York and drops the
    tzinfo, so the whole system compares naive Eastern values. Using the
    server's own clock instead would break the comparison on any box that is
    not Eastern, and the deployment box is UTC: bars would look four hours
    older than they are and every one of them would be treated as closed,
    which is the exact mistake the completeness check exists to prevent.
    """
    return datetime.now(ZoneInfo("America/New_York")).replace(tzinfo=None)


def _extend_session(stored) -> dict:
    """
    Pull whatever has printed since this session loaded, and grow it.

    Polls the provider rather than streaming. SchwabProvider.stream() raises
    NotImplementedError, but following the live market does not actually need a
    stream: re-requesting the same window returns the bars that have closed
    since, and one request per minute is all a one-minute chart can use.

    The refetch deliberately reuses _load_bars and _apply_session with the
    ORIGINAL request. A narrower "just the new bars" fetch would be cheaper and
    would be a second implementation of the fetch window, the session filter and
    the overnight-history rule -- three things that are already subtle enough
    once. Cost is one day of one-minute bars per poll, which is nothing next to
    a pane whose VWAP anchor silently disagrees with the one beside it.

    Never raises: this runs inside the WebSocket loop, where an exception would
    drop a socket the user is watching. Every failure comes back as `reason`.
    """
    session = stored.session
    req = stored.request

    if req is None:
        return session.no_extension(
            "this session was created before live follow existed -- start a new "
            "one to use it")
    if req.data_source == "synthetic":
        return session.no_extension(
            "synthetic data does not grow. Switch the data source to Live (Schwab) "
            "to follow the real market.")

    now = _market_now()
    if req.end_date < now.date():
        return session.no_extension(
            f"this session ends {req.end_date}, which is in the past -- no new bars "
            f"will print for it")

    try:
        source_tf = _source_timeframe(req.timeframes or [req.timeframe])
        df = _load_bars(req, source_tf, get_contract_spec(req.symbol))
        df = _apply_session(df, req.session_start, req.session_end)
    except HTTPException as exc:
        return session.no_extension(f"could not reach the data source: {exc.detail}")
    except Exception as exc:                                  # noqa: BLE001
        return session.no_extension(f"could not reach the data source: {exc}")

    return session.extend(df, now=now)


@router.post("", response_model=ReplayCreateResponse)
def create_replay(req: ReplayCreateRequest):
    timeframes = req.timeframes or [req.timeframe]
    unknown = [t for t in timeframes if t not in _TF_MINUTES]
    if unknown:
        raise HTTPException(400, f"Unsupported timeframe(s): {unknown}. "
                                 f"Expected any of {list(_TF_MINUTES)}.")

    spec = get_contract_spec(req.symbol)
    base_tf = min(timeframes, key=lambda t: _TF_MINUTES[t])
    # Fetch fine enough to build every pane faithfully; the CLOCK still ticks
    # once per base_tf bar, so tick counts and playback speed are unaffected.
    source_tf = _source_timeframe(timeframes)
    df = _load_bars(req, source_tf, spec)
    df = _apply_session(df, req.session_start, req.session_end)
    waiting = False
    if df.empty:
        now_et = _market_now()
        # Asking for TODAY before the chosen session has opened is not an error.
        not_open_yet = (
            req.end_date >= now_et.date()
            and req.session_start is not None
            and now_et.time() < req.session_start
        )
        if not_open_yet:
            # WAIT, do not refuse.
            #
            # The window is legitimately empty right now, and it is the caller's
            # window: 09:30-16:00, 18:00-17:00 or anything else is a deliberate
            # choice about which session they trade, not a mistake to be
            # corrected by telling them to switch to 24 hours. Refusing meant the
            # app only worked if they abandoned the setting they had chosen.
            #
            # An empty session reports done immediately, which is exactly what
            # makes the client turn Follow live on by itself. From there each
            # poll calls extend(), and the first bar of their session reaches the
            # tape the moment it closes.
            waiting = True
        else:
            # Genuinely nothing in this range -- a weekend, a holiday, or a
            # window this instrument never trades in. Naming the filter alone is
            # accurate and unhelpful, so say which it is.
            raise HTTPException(400, (
                f"No {req.symbol} bars in the {req.session_start}-{req.session_end} "
                f"session between {req.start_date} and {req.end_date}. Try another "
                f"date range, or 24-hour session hours if this instrument trades "
                f"outside regular hours."
            ))

    # Synthetic data is generated, not observed, so nothing about it is "still
    # forming" -- and its bars can legitimately run past the wall clock. Every
    # real source is trimmed to the last CLOSED bar.
    if req.data_source != "synthetic":
        # base_tf, not just source_tf: the clock ticks once per BASE bar and
        # emits every one of them, so a partially-covered trailing base bin would
        # reach the tape as a closed bar and then change on the next poll. See
        # trim_to_closed_bars.
        df = trim_to_closed_bars(df, source_tf, base_tf, req.symbol, _market_now())
        if df.empty and not waiting:
            raise HTTPException(
                400,
                f"No {req.symbol} bar has closed yet in the "
                f"{req.session_start}-{req.session_end} session today. Wait for the "
                f"first {base_tf} bar to complete, or pick an earlier date.",
            )

    try:
        session = MultiReplaySession(
            df=df,
            timeframes=timeframes,
            # A factory, not an instance: each pane needs its own strategy
            # state or a coarse bar would corrupt a finer pane's setup.
            strategy_factory=lambda: build_strategy(req.strategy_id, req.params),
            symbol=req.symbol,
            initial_capital=req.initial_capital,
            contracts_per_trade=req.contracts_per_trade,
            commission_per_contract=req.commission_per_contract,
            # Anchors each pane's VWAP reset to the session open, not midnight.
            session_start=req.session_start,
            source_timeframe=source_tf,
            tick_size=spec["tick_size"],
            tick_value=spec["tick_value"],
            point_value=spec["point_value"],
            allow_empty=waiting,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    fetch_start = _fetch_start(req)
    strategy_name = session.panes[base_tf].engine.strategy.name
    replay_id = replay_store.save(session, df, req.symbol, strategy_name,
                                  req.initial_capital, req.data_source,
                                  request=req)

    return ReplayCreateResponse(
        replay_id=replay_id,
        total_bars=session.total_ticks,
        symbol=req.symbol,
        strategy_name=strategy_name,
        initial_capital=req.initial_capital,
        timeframes=session.timeframes,
        base_timeframe=session.base_timeframe,
        data_timeframe=session.data_timeframe,
        bar_counts=session.bar_counts(),
        data_source=req.data_source,
        # Non-null only when an overnight session pulled the previous day in.
        # The UI says so rather than leaving an unexplained extra evening of
        # bars at the front of the replay.
        fetch_start_date=fetch_start if fetch_start != req.start_date else None,
    )


@ws_router.websocket("/ws/{replay_id}")
async def replay_ws(websocket: WebSocket, replay_id: str):
    # A websocket upgrade does NOT run the router's HTTP dependencies, so the
    # dependencies=[PROTECTED] on this router protects every route in it
    # EXCEPT this one. The check has to be here, and it has to happen before
    # accept() -- accepting first and closing after would still have opened
    # the socket to an anonymous caller.
    user = await auth.user_for_websocket(websocket)
    if user is None:
        # 1008 = policy violation. No message body: an unauthenticated caller
        # learns only that it was refused.
        await websocket.close(code=1008)
        return

    await websocket.accept()
    stored = replay_store.get(replay_id)
    if stored is None:
        await websocket.send_json({"type": "error", "message": f"Replay {replay_id!r} not found."})
        await websocket.close()
        return

    session = stored.session
    running = False
    speed = 0.1  # seconds between clock ticks while playing

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
                    session.reset()
                    running = False
                    await websocket.send_json({"type": "reset"})
                elif action == "seek":
                    # Fast-forward without narrating every tick.
                    #
                    # Exists so a session rebuilt after the server went away can
                    # be put back where the tape was. Sessions live in this
                    # process's memory, so a deploy, a crash or an OOM kill takes
                    # every running replay with it; the client re-creates the
                    # session from the same configuration and seeks to the tick
                    # it had reached.
                    #
                    # The per-tick frames are deliberately NOT sent -- thousands
                    # of messages would be pure noise and would take longer to
                    # render than the seek takes to run. One frame at the end
                    # carries the state that matters.
                    target = int(msg.get("ticks") or 0)
                    running = False
                    stepped = {}
                    while session.progress()[0] < target and not session.is_done:
                        stepped = session.tick()
                    processed, total = session.progress()
                    await websocket.send_json({
                        "type": "frames",
                        "market_time": (session.market_time.isoformat()
                                        if session.market_time else None),
                        "ticks_processed": processed,
                        "total_ticks": total,
                        "frames": {
                            tf: serializers.frame_to_dict(frame)
                            for tf, frame in stepped.items()
                        },
                    })
                    await websocket.send_json({
                        "type": "seeked", "ticks_processed": processed,
                    })
                elif action == "extend":
                    # Following the live market: pull anything that has printed
                    # since the snapshot was loaded and grow the session.
                    #
                    # Off-loop for the same reason add_timeframes is -- a provider
                    # request plus a resample plus the catch-up replay is far too
                    # much to do between socket reads.
                    #
                    # `playing` is reported back so the client does not have to
                    # guess whether it should resume: a session that had finished
                    # is no longer finished once bars arrive.
                    result = await asyncio.to_thread(_extend_session, stored)
                    await websocket.send_json({
                        "type": "extended",
                        "added": result["added"],
                        "reason": result["reason"],
                        "total_ticks": result["total_ticks"],
                        "bar_counts": result["bar_counts"],
                        "market_time": session.market_time.isoformat()
                        if session.market_time else None,
                        "data_time": session.last_source_time.isoformat()
                        if session.last_source_time is not None else None,
                        "is_done": session.is_done,
                    })
                elif action == "add_timeframes":
                    # Bringing a timeframe in mid-session. Only ADDING needs the
                    # backend: removal is a client-side render filter, so a pane
                    # is never torn down and the clock is never disturbed.
                    # Off-loop because resampling plus the catch-up replay is
                    # CPU work, and blocking here would stall the socket.
                    result = await asyncio.to_thread(
                        session.add_timeframes, msg.get("timeframes") or [],
                    )
                    await websocket.send_json({
                        "type": "timeframes",
                        "timeframes": session.timeframes,
                        "base_timeframe": session.base_timeframe,
                        # The resolution the frame was loaded at. Anything finer
                        # is unreachable without a refetch, so the client greys
                        # those out instead of letting them fail silently.
                        "data_timeframe": session.data_timeframe,
                        "bar_counts": session.bar_counts(),
                        "added": result["added"],
                        "rejected": result["rejected"],
                        "backfill": {
                            tf: {
                                "bars": bf["bars"],
                                "bars_closed": bf["bars_closed"],
                                "truncated": bf["truncated"],
                                # One frame settles every scalar -- FrameState
                                # carries position/portfolio/trades cumulatively.
                                "state": serializers.frame_to_dict(bf["frame"])
                                if bf["frame"] is not None else None,
                            }
                            for tf, bf in result["backfill"].items()
                        },
                    })
            except asyncio.TimeoutError:
                pass  # no control message this tick -- fall through to stepping

            if running:
                if session.is_done:
                    running = False
                    await websocket.send_json({"type": "done"})
                else:
                    advanced = session.tick()
                    processed, total = session.progress()
                    # ONE message per clock tick carrying every pane that moved.
                    # Sending a separate message per pane would let the client
                    # paint a half-updated grid between them, which is exactly
                    # the desync the shared clock exists to prevent.
                    await websocket.send_json({
                        "type": "frames",
                        "market_time": session.market_time.isoformat() if session.market_time else None,
                        "ticks_processed": processed,
                        "total_ticks": total,
                        "frames": {
                            tf: serializers.frame_to_dict(frame)
                            for tf, frame in advanced.items()
                        },
                    })
    except WebSocketDisconnect:
        pass


@router.get("/{replay_id}")
def get_replay(replay_id: str):
    stored = replay_store.get(replay_id)
    if stored is None:
        raise HTTPException(404, f"Replay {replay_id!r} not found.")
    processed, total = stored.session.progress()
    return {
        "replay_id": replay_id,
        "symbol": stored.symbol,
        "strategy_name": stored.strategy_name,
        "initial_capital": stored.initial_capital,
        "data_source": stored.data_source,
        "timeframes": stored.session.timeframes,
        "base_timeframe": stored.session.base_timeframe,
        "data_timeframe": stored.session.data_timeframe,
        "bar_counts": stored.session.bar_counts(),
        "ticks_processed": processed,
        "total_ticks": total,
        "is_done": stored.session.is_done,
    }
