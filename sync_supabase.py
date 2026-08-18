import hashlib
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent

MEMORY_DIR = ROOT / "memory"
MEMORY_FILE = MEMORY_DIR / "game_memory.json"

STATE_FILE = ROOT / "training_state.json"
STATUS_FILE = ROOT / "sync_status.json"


SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]

MIN_NEW_GAMES = int(
    os.environ.get(
        "MIN_NEW_GAMES",
        "5"
    )
)

FORCE_TRAIN = (
    os.environ.get(
        "FORCE_TRAIN",
        "false"
    ).lower()
    == "true"
)


def load_state():
    if not STATE_FILE.exists():
        return {
            "last_trained_supabase_id": 0
        }

    try:
        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)

    except Exception:
        return {
            "last_trained_supabase_id": 0
        }


def fetch_page(start, end):
    url = (
        SUPABASE_URL
        + "/rest/v1/games"
        + "?select=id,created_at,winner,game_record"
        + "&order=id.asc"
    )

    request = Request(
        url,
        headers={
            "apikey":
                SUPABASE_SECRET_KEY,

            "Authorization":
                "Bearer "
                + SUPABASE_SECRET_KEY,

            "Range":
                f"{start}-{end}",

            "Range-Unit":
                "items",
        },
    )

    with urlopen(
        request,
        timeout=120
    ) as response:

        return json.loads(
            response.read().decode(
                "utf-8"
            )
        )


def fetch_all_games():
    rows = []

    page_size = 500
    start = 0

    while True:
        page = fetch_page(
            start,
            start + page_size - 1
        )

        if not page:
            break

        rows.extend(page)

        print(
            f"Downloaded {len(rows)} rows..."
        )

        if len(page) < page_size:
            break

        start += page_size

    return rows


def game_hash(record):
    raw = json.dumps(
        record,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":")
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def main():
    print("=" * 70)
    print("RES ARCANA SUPABASE SYNC")
    print("=" * 70)

    rows = fetch_all_games()

    print(
        "Supabase rows:",
        len(rows)
    )

    state = load_state()

    last_trained_id = int(
        state.get(
            "last_trained_supabase_id",
            0
        )
    )

    valid_rows = [
        row
        for row in rows
        if isinstance(
            row.get("game_record"),
            dict
        )
    ]

    max_id = max(
        (
            int(row.get("id", 0))
            for row in valid_rows
        ),
        default=0
    )

    new_rows = [
        row
        for row in valid_rows
        if int(
            row.get("id", 0)
        ) > last_trained_id
    ]

    print(
        "Last trained Supabase ID:",
        last_trained_id
    )

    print(
        "Latest Supabase ID:",
        max_id
    )

    print(
        "New rows since training:",
        len(new_rows)
    )

    # --------------------------------------------------------
    # DEDUPLICATE GAME RECORDS
    # --------------------------------------------------------

    seen = set()
    games = []

    for row in valid_rows:
        game = row["game_record"]

        signature = game_hash(
            game
        )

        if signature in seen:
            continue

        seen.add(signature)

        game = dict(game)

        game[
            "_supabase_game_id"
        ] = row.get("id")

        game[
            "_supabase_created_at"
        ] = row.get(
            "created_at"
        )

        games.append(game)

    MEMORY_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        MEMORY_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            games,
            f,
            ensure_ascii=False
        )

    print(
        "Unique games:",
        len(games)
    )

    should_train = (
        FORCE_TRAIN
        or len(new_rows)
        >= MIN_NEW_GAMES
    )

    status = {
        "should_train":
            should_train,

        "new_games":
            len(new_rows),

        "latest_supabase_id":
            max_id,

        "unique_games":
            len(games),
    }

    with open(
        STATUS_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            status,
            f,
            indent=2
        )

    print()
    print(
        "TRAIN REQUIRED:",
        should_train
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
