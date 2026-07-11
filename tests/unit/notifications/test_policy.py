from packages.notifications.policy import decide


def test_no_notification_for_unchanged_forecast() -> None:
    result = decide(
        target_id="t", snapshot_id="s", engine_version="v",
        previous=(0.2, 0.4, "medium"), current=(0.21, 0.41, "medium"), local_events={},
    )
    assert result.meaningful is False

def test_notification_for_material_change_without_sensitive_values() -> None:
    result = decide(
        target_id="t", snapshot_id="s", engine_version="v",
        previous=(0.2, 0.4, "medium"), current=(0.4, 0.6, "medium"), local_events={},
    )
    assert result.meaningful is True
    assert "t" not in result.delivery_key
