"""
Override the global autouse mock_dependencies fixture for database unit tests.

The top-level conftest.py patches sys.modules, which causes SQLAlchemy's
inspection registry to be reset between tests (the 'object' class gets
re-registered via sqlalchemy.orm.base module-level code, raising
AssertionError on second import).  These tests use runpy.run_path to
reload the database module and need a clean sys.modules context.
"""
import pytest


@pytest.fixture(autouse=True)
def mock_dependencies():
    """No-op override: database unit tests must not patch sys.modules."""
    yield
