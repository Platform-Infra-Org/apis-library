# test_platform_logger.py

import pytest
import logging
from ..tashtiot_apis_library.logger import PlatformLogger  # Replace 'your_module' with the actual module name

@pytest.fixture
def platform_logger():
    return PlatformLogger("resource", "endpoint", "method")

def test_info(platform_logger, caplog):
    platform_logger.info("Info message")

    assert "Info message" in caplog.text
    assert "resource" in caplog.text
    assert "endpoint" in caplog.text
    assert "method" in caplog.text

def test_warning(platform_logger, caplog):
    platform_logger.warning("Warning message")
    assert "Warning message" in caplog.text
    assert "resource" in caplog.text
    assert "endpoint" in caplog.text
    assert "method" in caplog.text

def test_error(platform_logger, caplog):
    platform_logger.error("Error message")
    print(caplog.text)
 
    assert "Error message" in caplog.text
    assert "resource" in caplog.text
    assert "endpoint" in caplog.text
    assert "method" in caplog.text

def test_critical(platform_logger, caplog):
    platform_logger.critical("Critical message")
    print(caplog.text)

    assert "Critical message" in caplog.text
    assert "resource" in caplog.text
    assert "endpoint" in caplog.text
    assert "method" in caplog.text