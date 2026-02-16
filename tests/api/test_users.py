import os
import unittest.mock

# Mock slowapi.Limiter class globally before any imports that use it
with unittest.mock.patch("slowapi.Limiter") as MockLimiter:
    # Ensure that MockLimiter.limit acts as a no-op decorator
    MockLimiter.return_value.limit.return_value = lambda f: f

    import pytest
    import pytest_asyncio
    from fastapi import APIRouter, FastAPI  # Import FastAPI and APIRouter
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.pool import StaticPool

    from src.api.users import \
        router as users_router  # Import users_router and users_db
    from src.api.users import users_db
    from src.database import Base
    from src.database import \
        Session as DB_Session  # Import User and DB_Session models
    from src.database import User, get_db

    # Create a minimal FastAPI app for testing purposes
    test_app = FastAPI()
    test_app.include_router(users_router)

# Setup for isolated in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables in the test database
# This ensures that each test run starts with a clean database schema
Base.metadata.create_all(bind=engine)


@pytest.fixture(name="db_session")
def db_session_fixture():
    """Create a test database session for each test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()

    # Clear the in-memory users_db for consistent tests
    users_db.clear()

    try:
        yield session
    finally:
        session.close()


@pytest_asyncio.fixture(name="client")
async def client_fixture(db_session: Session, mocker):
    """Create an asynchronous test client for the FastAPI app."""

    async def override_get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = override_get_db

    os.environ["ADMIN_TOKEN"] = "test_admin_token"

    # Mock the limiter instance in src.api.users directly
    mocker.patch("src.api.users.limiter.limit", return_value=lambda f: f)

    # Correct way to use AsyncClient in an async fixture
    client = AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")
    try:
        yield client
    finally:
        await client.aclose()  # Ensure the client is closed properly
        test_app.dependency_overrides.clear()
        del os.environ["ADMIN_TOKEN"]  # Clean up environment variable


# Placeholder for user registration test
@pytest.mark.asyncio
async def test_register_user_success(client: AsyncClient):
    """Test successful user registration."""
    response = await client.post(
        "/api/v1/users/register",
        json={
            "email": "test@example.com",
            "password": "securepassword",
            "full_name": "Test User",
        },
    )
    assert response.status_code == 201
    user_data = response.json()
    assert user_data["email"] == "test@example.com"
    assert "id" in user_data
    assert "plan" in user_data and user_data["plan"] == "free"


@pytest.mark.asyncio
async def test_register_existing_user(client: AsyncClient):
    """Test registration with an email that already exists."""
    # Register first user
    await client.post(
        "/api/v1/users/register",
        json={"email": "duplicate@example.com", "password": "securepassword"},
    )
    # Attempt to register again with the same email
    response = await client.post(
        "/api/v1/users/register",
        json={"email": "duplicate@example.com", "password": "anotherpassword"},
    )
    assert response.status_code == 400
    assert "User with this email already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_invalid_email(client: AsyncClient):
    """Test registration with an invalid email format."""
    response = await client.post(
        "/api/v1/users/register",
        json={"email": "invalid-email", "password": "securepassword"},
    )
    assert response.status_code == 422  # Unprocessable Entity for validation errors
    assert (
        "String should match pattern '^[^@]+@[^@]+\\.[^@]+$'"
        in response.json()["detail"][0]["msg"]
    )


@pytest.mark.asyncio
async def test_login_user_success(client: AsyncClient):
    """Test successful user login."""
    # Register a user first
    await client.post(
        "/api/v1/users/register",
        json={"email": "login_test@example.com", "password": "securepassword"},
    )

    # Attempt to log in
    response = await client.post(
        "/api/v1/users/login",
        json={"email": "login_test@example.com", "password": "securepassword"},
    )
    assert response.status_code == 200
    session_data = response.json()
    assert "token" in session_data
    assert "user" in session_data
    assert session_data["user"]["email"] == "login_test@example.com"
    assert "expires_at" in session_data


@pytest.mark.asyncio
async def test_login_user_incorrect_password(client: AsyncClient):
    """Test login with an incorrect password."""
    # Register a user first
    await client.post(
        "/api/v1/users/register",
        json={"email": "wrong_pass@example.com", "password": "correctpassword"},
    )

    # Attempt to log in with wrong password
    response = await client.post(
        "/api/v1/users/login",
        json={"email": "wrong_pass@example.com", "password": "incorrectpassword"},
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_current_user_exists(client: AsyncClient):
    """Test fetching the current user when users are present."""
    # Register a user first to populate users_db
    await client.post(
        "/api/v1/users/register",
        json={
            "email": "current@example.com",
            "password": "securepassword",
            "full_name": "Current User",
        },
    )

    # Log in the user to get a token
    login_response = await client.post(
        "/api/v1/users/login",
        json={"email": "current@example.com", "password": "securepassword"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["token"]

    response = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    user_data = response.json()
    assert user_data["email"] == "current@example.com"
    assert user_data["full_name"] == "Current User"


@pytest.mark.asyncio
async def test_get_user_stats_admin_success(client: AsyncClient):
    """Test fetching user statistics with a valid admin token."""
    # Register some users for statistics
    await client.post(
        "/api/v1/users/register",
        json={"email": "user1@example.com", "password": "password"},
    )
    await client.post(
        "/api/v1/users/register",
        json={"email": "user2@example.com", "password": "password"},
    )

    response = await client.get(
        "/api/v1/users/stats", headers={"X-Admin-Token": "test_admin_token"}
    )
    assert response.status_code == 200
    stats_data = response.json()
    assert stats_data["total_users"] >= 2  # At least 2 users registered
    assert "active_sessions" in stats_data
    assert "plans" in stats_data
    assert stats_data["plans"]["free"] >= 2


@pytest.mark.asyncio
async def test_get_user_stats_no_admin_token(client: AsyncClient):
    """Test fetching user statistics without an admin token."""
    response = await client.get("/api/v1/users/stats")
    assert response.status_code == 403
    assert "Admin access required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_user_stats_invalid_admin_token(client: AsyncClient):
    """Test fetching user statistics with an invalid admin token."""
    response = await client.get(
        "/api/v1/users/stats", headers={"X-Admin-Token": "wrong_token"}
    )
    assert response.status_code == 403
    assert "Admin access required" in response.json()["detail"]
