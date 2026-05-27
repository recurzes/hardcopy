from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

DB_DIR = Path.home() / ".local/share/hardcopy"
DB_PATH = DB_DIR / "hardcopy.db"
STREAK_PATH = DB_DIR / "focus_streaks.json"
STREAK_MIGRATED_MARKER = DB_DIR / "focus_streaks.json.migrated"

DEFAULT_STREAK = {
    "current_streak": 0,
    "last_session_date": None,
    "total_sessions": 0,
    "total_minutes": 0,
}

TIER_TASK_XP = {
    "common": 75,
    "rare": 150,
    "epic": 300,
    "legendary": 500,
}

RECORD_TYPES = (
    "max_tasks_day",
    "max_xp_day",
    "longest_focus",
    "max_weekly_tasks",
    "longest_daily_streak",
)

_connection: sqlite3.Connection | None = None
_initialized = False


def _now_local() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today_str() -> str:
    return date.today().isoformat()


def get_connection() -> sqlite3.Connection:
    global _connection, _initialized

    if _connection is None:
        DB_DIR.mkdir(parents=True, exist_ok=True)
        _connection = sqlite3.connect(DB_PATH, check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA journal_mode=WAL")
        _connection.execute("PRAGMA foreign_keys=ON")

    if not _initialized:
        init_db(_connection)
        _initialized = True

    return _connection


def init_db(conn: sqlite3.Connection | None = None) -> None:
    conn = conn or get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            data TEXT
        );

        CREATE TABLE IF NOT EXISTS xp_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER REFERENCES events(id),
            amount INTEGER NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS player_stats (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            total_xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            current_daily_streak INTEGER DEFAULT 0,
            longest_daily_streak INTEGER DEFAULT 0,
            current_focus_streak INTEGER DEFAULT 0,
            last_focus_date TEXT,
            best_day_tasks INTEGER DEFAULT 0,
            best_day_xp INTEGER DEFAULT 0,
            last_active_date TEXT,
            total_tasks_completed INTEGER DEFAULT 0,
            total_focus_sessions INTEGER DEFAULT 0,
            total_focus_minutes INTEGER DEFAULT 0,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_type TEXT UNIQUE NOT NULL,
            value INTEGER NOT NULL,
            achieved_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        """
    )

    conn.execute(
        """
        INSERT OR IGNORE INTO player_stats (id, updated_at)
        VALUES (1, ?)
        """,
        (_now_local(),),
    )
    conn.commit()
    migrate_focus_streaks(conn)


def migrate_focus_streaks(conn: sqlite3.Connection | None = None) -> None:
    conn = conn or get_connection()
    if STREAK_MIGRATED_MARKER.exists():
        return

    if not STREAK_PATH.exists():
        STREAK_MIGRATED_MARKER.touch()
        return

    try:
        with STREAK_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        STREAK_MIGRATED_MARKER.touch()
        return

    state = dict(DEFAULT_STREAK)
    state.update(data)

    conn.execute(
        """
        UPDATE player_stats
        SET current_focus_streak = ?,
            last_focus_date = ?,
            total_focus_sessions = ?,
            total_focus_minutes = ?,
            updated_at = ?
        WHERE id = 1
        """,
        (
            int(state.get("current_streak", 0)),
            state.get("last_session_date"),
            int(state.get("total_sessions", 0)),
            int(state.get("total_minutes", 0)),
            _now_local(),
        ),
    )
    conn.commit()
    STREAK_MIGRATED_MARKER.touch()


def _ensure_player_stats(conn: sqlite3.Connection) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM player_stats WHERE id = 1").fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO player_stats (id, updated_at) VALUES (1, ?)",
            (_now_local(),),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM player_stats WHERE id = 1").fetchone()
    return row


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    return dict(row)


def xp_for_level(level: int) -> int:
    if level <= 1:
        return 0
    return 100 * level * (level - 1)


def level_from_xp(total_xp: int) -> int:
    level = 1
    while total_xp >= xp_for_level(level + 1):
        level += 1
    return level


def xp_to_next_level(total_xp: int) -> int:
    level = level_from_xp(total_xp)
    next_threshold = xp_for_level(level + 1)
    return max(0, next_threshold - total_xp)


def log_event(event_type: str, data: dict | None = None) -> int:
    conn = get_connection()
    payload = json.dumps(data or {})
    cursor = conn.execute(
        "INSERT INTO events (event_type, data, created_at) VALUES (?, ?, ?)",
        (event_type, payload, _now_local()),
    )
    conn.commit()
    return int(cursor.lastrowid)


def check_record(record_type: str, value: int) -> bool:
    if record_type not in RECORD_TYPES:
        return False

    conn = get_connection()
    row = conn.execute(
        "SELECT value FROM records WHERE record_type = ?",
        (record_type,),
    ).fetchone()

    if row is None or value > int(row["value"]):
        conn.execute(
            """
            INSERT INTO records (record_type, value, achieved_at)
            VALUES (?, ?, ?)
            ON CONFLICT(record_type) DO UPDATE SET
                value = excluded.value,
                achieved_at = excluded.achieved_at
            """,
            (record_type, value, _now_local()),
        )
        conn.commit()
        return True

    return False


def update_daily_streak() -> tuple[int, bool]:
    conn = get_connection()
    stats = _ensure_player_stats(conn)
    today = _today_str()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    last_active = stats["last_active_date"]
    streak_increased = False

    if last_active == today:
        current = int(stats["current_daily_streak"])
    elif last_active == yesterday:
        current = int(stats["current_daily_streak"]) + 1
        streak_increased = True
    else:
        current = 1
        streak_increased = last_active is None

    longest = max(int(stats["longest_daily_streak"]), current)
    new_record = check_record("longest_daily_streak", longest)

    conn.execute(
        """
        UPDATE player_stats
        SET current_daily_streak = ?,
            longest_daily_streak = ?,
            last_active_date = ?,
            updated_at = ?
        WHERE id = 1
        """,
        (current, longest, today, _now_local()),
    )
    conn.commit()
    return current, streak_increased or new_record


def update_focus_streak(minutes: int) -> tuple[dict[str, int], bool]:
    conn = get_connection()
    stats = _ensure_player_stats(conn)
    today = _today_str()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    last_focus = stats["last_focus_date"]
    streak_increased = False

    if last_focus == today:
        current_focus = int(stats["current_focus_streak"])
    elif last_focus == yesterday:
        current_focus = int(stats["current_focus_streak"]) + 1
        streak_increased = True
    else:
        current_focus = 1
        streak_increased = last_focus is None

    total_sessions = int(stats["total_focus_sessions"]) + 1
    total_minutes = int(stats["total_focus_minutes"]) + minutes

    conn.execute(
        """
        UPDATE player_stats
        SET current_focus_streak = ?,
            last_focus_date = ?,
            total_focus_sessions = ?,
            total_focus_minutes = ?,
            updated_at = ?
        WHERE id = 1
        """,
        (current_focus, today, total_sessions, total_minutes, _now_local()),
    )
    conn.commit()

    update_daily_streak()
    check_record("longest_focus", minutes)

    return {
        "current_focus_streak": current_focus,
        "total_focus_sessions": total_sessions,
        "total_focus_minutes": total_minutes,
    }, streak_increased


def get_focus_streak_state() -> dict[str, Any]:
    stats = get_stats()
    return {
        "current_streak": int(stats.get("current_focus_streak", 0)),
        "last_session_date": stats.get("last_focus_date"),
        "total_sessions": int(stats.get("total_focus_sessions", 0)),
        "total_minutes": int(stats.get("total_focus_minutes", 0)),
    }


def _update_day_totals(conn: sqlite3.Connection) -> tuple[int, int, list[str]]:
    today = _today_str()
    tasks_today = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM events
        WHERE event_type = 'task_complete'
          AND date(created_at) = date(?)
        """,
        (today,),
    ).fetchone()["count"]

    xp_today = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM xp_ledger
        WHERE date(created_at) = date(?)
        """,
        (today,),
    ).fetchone()["total"]

    new_records: list[str] = []
    if check_record("max_tasks_day", int(tasks_today)):
        new_records.append("max_tasks_day")
    if check_record("max_xp_day", int(xp_today)):
        new_records.append("max_xp_day")

    stats = _ensure_player_stats(conn)
    conn.execute(
        """
        UPDATE player_stats
        SET best_day_tasks = CASE WHEN ? > best_day_tasks THEN ? ELSE best_day_tasks END,
            best_day_xp = CASE WHEN ? > best_day_xp THEN ? ELSE best_day_xp END,
            updated_at = ?
        WHERE id = 1
        """,
        (int(tasks_today), int(tasks_today), int(xp_today), int(xp_today), _now_local()),
    )
    return int(tasks_today), int(xp_today), new_records


def award_xp(
    event_id: int,
    amount: int,
    source: str,
    *,
    count_task: bool = False,
) -> dict[str, Any]:
    conn = get_connection()
    stats = _ensure_player_stats(conn)
    old_level = int(stats["level"])
    old_xp = int(stats["total_xp"])
    new_xp = old_xp + amount
    new_level = level_from_xp(new_xp)
    leveled_up = new_level > old_level

    conn.execute(
        "INSERT INTO xp_ledger (event_id, amount, source, created_at) VALUES (?, ?, ?, ?)",
        (event_id, amount, source, _now_local()),
    )

    updates = {
        "total_xp": new_xp,
        "level": new_level,
        "updated_at": _now_local(),
    }
    if count_task:
        updates["total_tasks_completed"] = int(stats["total_tasks_completed"]) + 1

    set_clause = ", ".join(f"{key} = ?" for key in updates)
    conn.execute(
        f"UPDATE player_stats SET {set_clause} WHERE id = 1",
        tuple(updates.values()),
    )
    conn.commit()

    _, _, day_records = _update_day_totals(conn)
    conn.commit()

    daily_streak, streak_increased = update_daily_streak()

    return {
        "amount": amount,
        "total_xp": new_xp,
        "level": new_level,
        "old_level": old_level,
        "leveled_up": leveled_up,
        "xp_to_next": xp_to_next_level(new_xp),
        "daily_streak": daily_streak,
        "daily_streak_increased": streak_increased,
        "new_records": day_records,
    }


def log_task_complete(task_name: str, tier: str) -> dict[str, Any]:
    xp_amount = TIER_TASK_XP.get(tier, TIER_TASK_XP["common"])
    event_id = log_event(
        "task_complete",
        {"task_name": task_name, "tier": tier, "xp": xp_amount},
    )
    result = award_xp(event_id, xp_amount, "task", count_task=True)
    result["tier"] = tier
    result["task_name"] = task_name
    return result


def log_focus_session(
    *,
    event_type: str,
    task: str,
    duration_minutes: int,
    elapsed_minutes: int,
    xp: int,
    tier: str,
) -> dict[str, Any]:
    event_id = log_event(
        event_type,
        {
            "task": task,
            "duration_minutes": duration_minutes,
            "elapsed_minutes": elapsed_minutes,
            "xp": xp,
            "tier": tier,
        },
    )

    result: dict[str, Any] = {
        "event_id": event_id,
        "xp": xp,
        "new_records": [],
    }

    if event_type == "focus_complete":
        focus_stats, streak_increased = update_focus_streak(duration_minutes)
        result.update(focus_stats)
        result["focus_streak_increased"] = streak_increased
        if xp > 0:
            xp_result = award_xp(event_id, xp, "focus")
            result.update(xp_result)
        else:
            result.update(get_stats())
    elif event_type == "focus_partial" and xp > 0:
        xp_result = award_xp(event_id, xp, "focus")
        result.update(xp_result)
        update_daily_streak()
    elif event_type == "focus_abandoned":
        result.update(get_stats())

    return result


def log_boss_fight(
    *,
    rank: str,
    tasks_completed: int,
    defeated: bool,
    total_xp: int,
) -> None:
    log_event(
        "boss_fight",
        {
            "rank": rank,
            "tasks_completed": tasks_completed,
            "defeated": defeated,
            "total_xp": total_xp,
        },
    )
    check_record("max_weekly_tasks", tasks_completed)


def log_brain_dump(task_count: int) -> None:
    log_event("brain_dump", {"task_count": task_count})


def log_quick_capture(task_count: int) -> None:
    log_event("quick_capture", {"task_count": task_count})


def log_plan_generated(task_count: int, total_minutes: int | None) -> None:
    log_event(
        "plan_generated",
        {"task_count": task_count, "total_estimated_minutes": total_minutes},
    )


def get_stats() -> dict[str, Any]:
    conn = get_connection()
    stats = row_to_dict(_ensure_player_stats(conn))
    total_xp = int(stats.get("total_xp", 0))
    stats["level"] = level_from_xp(total_xp)
    stats["xp_to_next"] = xp_to_next_level(total_xp)
    stats["xp_for_current_level"] = xp_for_level(stats["level"])
    stats["xp_for_next_level"] = xp_for_level(stats["level"] + 1)
    return stats


def get_today_summary() -> dict[str, int]:
    conn = get_connection()
    today = _today_str()

    tasks = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM events
        WHERE event_type = 'task_complete'
          AND date(created_at) = date(?)
        """,
        (today,),
    ).fetchone()["count"]

    focus_sessions = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM events
        WHERE event_type = 'focus_complete'
          AND date(created_at) = date(?)
        """,
        (today,),
    ).fetchone()["count"]

    focus_minutes = conn.execute(
        """
        SELECT COALESCE(SUM(json_extract(data, '$.duration_minutes')), 0) AS total
        FROM events
        WHERE event_type = 'focus_complete'
          AND date(created_at) = date(?)
        """,
        (today,),
    ).fetchone()["total"]

    xp_today = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM xp_ledger
        WHERE date(created_at) = date(?)
        """,
        (today,),
    ).fetchone()["total"]

    return {
        "tasks_completed": int(tasks),
        "focus_sessions": int(focus_sessions),
        "focus_minutes": int(focus_minutes),
        "xp_earned": int(xp_today),
    }


def get_weekly_history(weeks: int = 4) -> list[dict[str, Any]]:
    conn = get_connection()
    history: list[dict[str, Any]] = []
    today = date.today()

    for offset in range(weeks - 1, -1, -1):
        week_end = today - timedelta(days=offset * 7)
        week_start = week_end - timedelta(days=6)

        tasks = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM events
            WHERE event_type = 'task_complete'
              AND date(created_at) BETWEEN date(?) AND date(?)
            """,
            (week_start.isoformat(), week_end.isoformat()),
        ).fetchone()["count"]

        boss = conn.execute(
            """
            SELECT data
            FROM events
            WHERE event_type = 'boss_fight'
              AND date(created_at) BETWEEN date(?) AND date(?)
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (week_start.isoformat(), week_end.isoformat()),
        ).fetchone()

        rank = None
        defeated = None
        if boss and boss["data"]:
            payload = json.loads(boss["data"])
            rank = payload.get("rank")
            defeated = payload.get("defeated")

        history.append(
            {
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "tasks_completed": int(tasks),
                "rank": rank,
                "defeated": defeated,
            }
        )

    return history


def get_hourly_pattern() -> dict[int, int]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT CAST(strftime('%H', created_at) AS INTEGER) AS hour,
               COUNT(*) AS count
        FROM events
        WHERE event_type = 'task_complete'
        GROUP BY hour
        ORDER BY hour
        """
    ).fetchall()
    return {int(row["hour"]): int(row["count"]) for row in rows}


def get_weekday_pattern() -> dict[int, float]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT CAST(strftime('%w', created_at) AS INTEGER) AS weekday,
               COUNT(*) AS count
        FROM events
        WHERE event_type = 'task_complete'
        GROUP BY weekday
        """
    ).fetchall()

    counts = {int(row["weekday"]): int(row["count"]) for row in rows}
    if not counts:
        return {}

    weeks_of_data = conn.execute(
        """
        SELECT COUNT(DISTINCT strftime('%Y-%W', created_at)) AS weeks
        FROM events
        WHERE event_type = 'task_complete'
        """
    ).fetchone()["weeks"]
    weeks_of_data = max(int(weeks_of_data), 1)

    return {day: count / weeks_of_data for day, count in counts.items()}


def get_records() -> dict[str, dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT record_type, value, achieved_at FROM records ORDER BY record_type"
    ).fetchall()
    return {
        row["record_type"]: {"value": row["value"], "achieved_at": row["achieved_at"]}
        for row in rows
    }


def get_capacity_insights(today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    weekday_pattern = get_weekday_pattern()
    hourly_pattern = get_hourly_pattern()
    stats = get_stats()

    weekday_avg = weekday_pattern.get(today.weekday())
    overall_avg = (
        sum(weekday_pattern.values()) / len(weekday_pattern)
        if weekday_pattern
        else None
    )

    peak_hour = None
    if hourly_pattern:
        peak_hour = max(hourly_pattern, key=hourly_pattern.get)

    return {
        "weekday_average": weekday_avg,
        "overall_average": overall_avg,
        "peak_hour": peak_hour,
        "hourly_pattern": hourly_pattern,
        "weekday_pattern": weekday_pattern,
        "daily_streak": int(stats.get("current_daily_streak", 0)),
        "last_active_date": stats.get("last_active_date"),
    }


def compute_boss_rank(tasks_completed: int, weekly_goal: int = 20) -> str:
    total_xp = tasks_completed * 100
    boss_health = weekly_goal * 100
    boss_defeated = tasks_completed >= weekly_goal

    if total_xp >= boss_health * 1.5:
        return "S+"
    if boss_defeated:
        return "A"
    if total_xp >= boss_health * 0.5:
        return "C"
    return "F"


def format_record_label(record_type: str) -> str:
    labels = {
        "max_tasks_day": "Most tasks in a day",
        "max_xp_day": "Most XP in a day",
        "longest_focus": "Longest focus session",
        "max_weekly_tasks": "Most weekly tasks",
        "longest_daily_streak": "Longest daily streak",
    }
    return labels.get(record_type, record_type)


def print_level_up_receipt(old_level: int, new_level: int, total_xp: int) -> None:
    from src.printer import get_printer, print_centered

    p = get_printer()
    if not p:
        return

    p.text("\n")
    print_centered(p, "================================")
    print_centered(p, "       *** LEVEL UP! ***")
    print_centered(p, f"       LEVEL {old_level} -> {new_level}")
    print_centered(p, "================================")
    p.text("\n")
    p.set(align="center", font="a", bold=True)
    p.text(f"TOTAL XP: {total_xp}\n")
    p.set(bold=False)
    p.text("\nNew powers unlocked:\n")
    p.text("Keep stacking wins.\n")
    p.text("\n\n")
    p.cut()
    p.close()


def print_new_record_lines(p, new_records: list[str]) -> None:
    from src.printer import print_centered

    if not new_records:
        return

    p.text("\n")
    print_centered(p, "================================")
    for record_type in new_records:
        label = format_record_label(record_type)
        print_centered(p, f"*** NEW RECORD: {label} ***")
    print_centered(p, "================================")
