from uuid import uuid4

from apps.bot.keyboards import BotCallback, tracks_keyboard
from apps.bot.presenters import TrackView, empty_tracks_text, track_detail_text, tracks_text


def _view() -> TrackView:
    return TrackView(
        target_id="opaque-target-token",
        university_name="Synthetic University",
        external_group_id="2199",
        campaign_year=2025,
        title="Synthetic Program",
        snapshot_status="valid",
        probability_low=0.25,
        probability_high=0.75,
        confidence="medium",
        event_counts={"rank_changed": 2},
        explanation={
            "signals": {"rank_vs_seat_count": 0.5},
            "assumptions": ["heuristic_no_training"],
            "limitations": ["not_a_guarantee"],
        },
    )


def test_empty_tracks_is_safe() -> None:
    assert empty_tracks_text() == "Сохранённых направлений пока нет."


def test_presenters_show_forecast_without_sensitive_data() -> None:
    text = tracks_text([_view()]) + track_detail_text(_view())
    assert "25%–75%" in text
    assert "opaque-target-token" not in text
    assert "raw_payload" not in text
    assert "HMAC" not in text


def test_callback_contains_only_opaque_uuid_token() -> None:
    token = str(uuid4())
    markup = tracks_keyboard([token])
    callback = markup.inline_keyboard[0][0].callback_data
    assert callback is not None
    assert token in callback
    assert "sspvo_id" not in callback
    assert "http" not in callback
    parsed = BotCallback.unpack(callback)
    assert parsed.action == "target"
