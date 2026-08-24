from backend.core.redact import content_fingerprint, redact


def test_phone_masked_keeps_last_three():
    out = redact("Call me on 9876543210 urgently")
    assert "9876543210" not in out
    assert "210" in out


def test_phone_with_country_code_masked():
    out = redact("+91 98765 43210")
    assert "9876" not in out


def test_email_masked_preserves_domain():
    out = redact("contact victim.anand@gmail.com now")
    assert "victim.anand" not in out
    assert "gmail.com" in out


def test_otp_value_masked():
    out = redact("Your OTP is 482913, do not share")
    assert "482913" not in out


def test_card_number_masked():
    out = redact("card 4111 1111 1111 1111 charged")
    assert "4111 1111" not in out


def test_clean_text_untouched():
    text = "Meeting tomorrow at the office about quarterly planning"
    assert redact(text) == text


def test_fingerprint_stable_and_short():
    assert content_fingerprint("abc") == content_fingerprint("abc")
    assert len(content_fingerprint("abc")) == 16
