from diarist.languages import SUPPORTED_LANGUAGES, is_supported, normalize


def test_auto_and_none_both_normalize_to_none() -> None:
    assert normalize(None) is None
    assert normalize("auto") is None


def test_known_code_passes_through() -> None:
    assert normalize("en") == "en"


def test_is_supported() -> None:
    assert is_supported(None)
    assert is_supported("auto")
    assert is_supported("en")
    assert not is_supported("not-a-real-code")


def test_supported_languages_cover_common_codes() -> None:
    for code in ("en", "fr", "es", "de", "ja", "zh"):
        assert code in SUPPORTED_LANGUAGES
