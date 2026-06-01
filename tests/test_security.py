from alertpilot.security import AuthError, create_token, hash_password, verify_password, verify_token


def test_password_hash_roundtrip():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong", hashed)


def test_token_signature_validation():
    token = create_token({"sub": "admin@example.com", "role": "admin"}, "secret", 60)
    claims = verify_token(token, "secret")
    assert claims["sub"] == "admin@example.com"
    try:
        verify_token(token, "different")
    except AuthError:
        pass
    else:
        raise AssertionError("tampered token should fail")
