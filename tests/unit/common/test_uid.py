from packages.common.uid import hash_uid, normalize_uid

TEST_SECRET = "test-only-secret-not-for-production"


def test_hash_is_deterministic_and_does_not_return_raw_uid() -> None:
    uid = "0001234"
    result = hash_uid(secret=TEST_SECRET, identity_namespace="test:2025", uid=uid)
    assert result == hash_uid(secret=TEST_SECRET, identity_namespace="test:2025", uid=uid)
    assert uid not in result
    assert len(result) == 64


def test_namespace_and_secret_change_hash() -> None:
    first = hash_uid(secret=TEST_SECRET, identity_namespace="test:a", uid="1234")
    other_namespace = hash_uid(secret=TEST_SECRET, identity_namespace="test:b", uid="1234")
    other_secret = hash_uid(secret="another-test-secret", identity_namespace="test:a", uid="1234")
    assert first != other_namespace
    assert first != other_secret


def test_uid_stays_a_string_and_preserves_leading_zero() -> None:
    assert normalize_uid("  0001234  ") == "0001234"
    assert hash_uid(secret=TEST_SECRET, identity_namespace="test:2025", uid="0001234") != hash_uid(
        secret=TEST_SECRET, identity_namespace="test:2025", uid="1234"
    )
