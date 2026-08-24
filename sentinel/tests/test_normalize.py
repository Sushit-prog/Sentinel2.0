import pytest

from backend.core.normalize import normalize_entity, normalize_phone


def test_plain_ten_digit_phone():
    assert normalize_phone("9876543210") == "9876543210"


def test_country_code_stripped():
    assert normalize_phone("+91 98765 43210") == "9876543210"
    assert normalize_phone("919876543210") == "9876543210"


def test_leading_zero_stripped():
    assert normalize_phone("09876543210") == "9876543210"


def test_invalid_prefix_kept_as_digits():
    assert normalize_phone("1234567890") == "1234567890"


def test_same_number_different_formats_collide():
    assert normalize_phone("+919876543210") == normalize_phone("(+91)-98765-43210")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("HDFC0000123456", "HDFC0000123456"),
        ("hdfc-0000-123456", "HDFC0000123456"),
        ("  ab12 ", "AB12"),
    ],
)
def test_account_normalization(raw, expected):
    assert normalize_entity("account", raw) == ("account", expected)


def test_device_normalization_uppercases():
    assert normalize_entity("device", "imei:abc-123") == ("device", "IMEIABC-123")


def test_unknown_type_rejected():
    assert normalize_entity("banana", "x") is None


def test_empty_value_rejected():
    assert normalize_entity("phone", "no-digits-here") is None
