"""
Pytest configuration and shared fixtures for all tests.
"""
import pytest
import sys
from pathlib import Path
import logging

# Configure logging for tests
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Add project paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "Backend_CLI"))
sys.path.insert(0, str(project_root / "src"))


@pytest.fixture(scope="session")
def test_config():
    """Session-level test configuration."""
    return {
        "backend_url": "http://localhost:8000",
        "test_email": "test@example.com",
        "test_password": "TestPass123!",
        "timeout": 5,
    }


@pytest.fixture(scope="function")
def cleanup():
    """Cleanup fixture for test teardown."""
    yield
    # Cleanup code here if needed


@pytest.fixture(autouse=True)
def reset_modules():
    """Reset module caches between tests."""
    yield
    # Reset any cached modules or singletons


@pytest.fixture(scope="session")
def event_loop():
    """Session-scope event loop for async tests."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Markers for test categorization
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit"
    )
