from ..tashtiot_apis_library.validation import ip_validator
import pytest

def test_ip_validator_valid_ip():
    assert ip_validator("192.168.1.1") == "192.168.1.1"
    assert ip_validator("10.0.0.1") == "10.0.0.1"
    assert ip_validator("255.255.255.255") == "255.255.255.255"

def test_ip_validator_invalid_ip():
    with pytest.raises(ValueError):
        ip_validator("256.1.1.1")
    with pytest.raises(ValueError):
        ip_validator("abc.def.ghi.jkl")
    with pytest.raises(ValueError):
        ip_validator("192.168.1")

def test_ip_validator_empty_ip():
    with pytest.raises(ValueError):
        ip_validator("")

def test_ip_validator_none_ip():
    with pytest.raises(TypeError):
        ip_validator(None)