import os
import pytest
import requests

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:3000")
PYTHON_URL = os.getenv("PYTHON_URL", "http://localhost:8000")


@pytest.fixture
def gateway():
    return requests.Session()


@pytest.fixture
def python_worker():
    return requests.Session()


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: marks tests as end-to-end")
