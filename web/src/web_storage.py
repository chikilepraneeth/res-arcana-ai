import json
import sys


SUPABASE_URL = "https://agmvxdpfstbmwxxyyikk.supabase.co"

SUPABASE_PUBLISHABLE_KEY = (
    "sb_publishable_G7A4VVSekV0TD7gAQiLaUQ_A_UxfIVn"
)


async def save_game_online(game_record):
    """
    Save one completed game permanently to Supabase.

    Returns True when Supabase accepts the record.
    Returns False if the upload fails.
    """

    # This uploader is only needed in the browser.
    if sys.platform != "emscripten":
        return False

    try:
        from pyodide.http import pyfetch
    except Exception as error:
        print(
            "SUPABASE: pyfetch unavailable:",
            error,
        )
        return False

    winner = game_record.get(
        "winner"
    )

    player_name = (
        game_record.get(
            "player_name"
        )
        or "Player"
    )

    # Keep the original/internal winner in game_record so
    # neural training still recognizes Chikile vs AI Companion.
    if winner == "Chikile":
        database_winner = player_name
    else:
        database_winner = winner

    payload = {
        "winner": database_winner,
        "game_record": game_record,
    }

    url = (
        SUPABASE_URL
        + "/rest/v1/games"
    )

    try:
        response = await pyfetch(
            url,
            method="POST",
            headers={
                "apikey": SUPABASE_PUBLISHABLE_KEY,
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            body=json.dumps(
                payload,
                ensure_ascii=False,
            ),
        )

        if response.ok:
            print(
                "SUPABASE: game saved successfully."
            )
            return True

        error_text = await response.text()

        print(
            "SUPABASE SAVE FAILED:",
            response.status,
            error_text,
        )

        return False

    except Exception as error:
        print(
            "SUPABASE SAVE ERROR:",
            error,
        )

        return False
