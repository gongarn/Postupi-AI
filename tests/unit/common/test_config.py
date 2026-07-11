from packages.common.config import Settings


def test_feature_flags_are_disabled_by_default() -> None:
    settings = Settings()
    assert settings.cross_university_matching_enabled is False
    assert settings.forecasting_enabled is False


def test_environment_is_validated() -> None:
    settings = Settings(environment="test")
    assert settings.environment == "test"
