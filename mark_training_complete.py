import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent

STATUS_FILE = (
    ROOT
    / "sync_status.json"
)

STATE_FILE = (
    ROOT
    / "training_state.json"
)


with open(
    STATUS_FILE,
    "r",
    encoding="utf-8"
) as f:
    status = json.load(f)


state = {
    "last_trained_supabase_id":
        status.get(
            "latest_supabase_id",
            0
        ),

    "unique_games":
        status.get(
            "unique_games",
            0
        ),
}


with open(
    STATE_FILE,
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        state,
        f,
        indent=2
    )


print(
    "Training state updated:",
    state
)
