"""
Integration tests for src/api/users.py
Tests user management API endpoints.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

# Import API and dependencies
try:
    from src.api.users import router as users_router
    from src.database import User, Session, get_db
    API_AVAILABLE = True
except ImportError:
    API_AVAILABLE = False


@pytest.mark.skipif(not API_AVAILABLE, reason="users API not available")
class TestUsersAPI:
    """Test users API endpoints."""

    @pytest.fixture
    def client(self, mock_db): # Add mock_db as argument
        """Create a test client."""
        from fastapi import FastAPI
        app = FastAPI()
        
        # Override get_db dependency to use the mock_db
        def override_get_db():
            yield mock_db
        app.dependency_overrides[get_db] = override_get_db
        
        app.include_router(users_router) 
        return TestClient(app)

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = Mock()
        db.query = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        db.delete = Mock()
        db.close = Mock()
        return db

    @pytest.fixture
    def mock_user(self):
        """Create a mock user."""
        user = Mock(spec=User)
        user.id = 1
        user.email = "test@example.com"
        user.username = "testuser"
        user.is_active = True
        user.is_admin = False
        user.created_at = datetime.utcnow()
        return user

    def test_get_users_empty(self, client, mock_db, monkeypatch):
        """Test GET /users with no users."""
        mock_db.query.return_value.all.return_value = []
        
        with patch('src.api.users.get_db', return_value=mock_db):
            monkeypatch.setenv("ADMIN_TOKEN", "test_admin_token")
            response = client.get("/api/v1/users/", headers={"X-Admin-Token": "test_admin_token"})
        
        assert response.status_code == 200
        assert response.json() == []

    def test_get_users_with_data(self, client, mock_db, mock_user):
        """Test GET /users with existing users."""
        mock_db.query.return_value.all.return_value = [mock_user]
        
        with patch('src.api.users.get_db', return_value=mock_db):
            response = client.get("/api/v1/users")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["email"] == "test@example.com"

    def test_get_user_by_id(self, client, mock_db, mock_user):
        """Test GET /users/{id}."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        with patch('src.api.users.get_db', return_value=mock_db):
            response = client.get("/api/v1/users/1")
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["username"] == "testuser"

    def test_get_user_not_found(self, client, mock_db):
        """Test GET /users/{id} with non-existent user."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with patch('src.api.users.get_db', return_value=mock_db):
            response = client.get("/api/v1/users/999")
        
        assert response.status_code == 404

    def test_create_user(self, client, mock_db, mock_user):
        """Test POST /users."""
        user_data = {
            "email": "new@example.com",
            "username": "newuser",
            "password": "securepassword123"
        }
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.add.return_value = None
        mock_db.refresh.return_value = mock_user
        
        with patch('src.api.users.get_db', return_value=mock_db):
            response = client.post("/api/v1/users", json=user_data)
        
        assert response.status_code in [200, 201]
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_create_user_duplicate_email(self, client, mock_db, mock_user):
        """Test POST /users with duplicate email."""
        user_data = {
            "email": "test@example.com",
            "username": "newuser",
            "password": "securepassword123"
        }
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        with patch('src.api.users.get_db', return_value=mock_db):
            response = client.post("/api/v1/users", json=user_data)
        
        assert response.status_code == 400

    def test_create_user_invalid_email(self, client, mock_db):
        """Test POST /users with invalid email."""
        user_data = {
            "email": "invalid-email",
            "username": "newuser",
            "password": "securepassword123"
        }
        
        with patch('src.api.users.get_db', return_value=mock_db):
            response = client.post("/api/v1/users", json=user_data)
        
        assert response.status_code == 422

    def test_create_user_weak_password(self, client, mock_db):
        """Test POST /users with weak password."""
        user_data = {
            "email": "new@example.com",
            "username": "newuser",
            "password": "123"
        }
        
        with patch('src.api.users.get_db', return_value=mock_db):
            response = client.post("/api/v1/users", json=user_data)
        
        assert response.status_code == 422

    def test_update_user(self, client, mock_db, mock_user):
        """Test PUT /users/{id}."""
        update_data = {
            "username": "updateduser"
        }
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        with patch('src.api.users.get_db', return_value=mock_db):
            response = client.put("/api/v1/users/1", json=update_data)
        
        assert response.status_code == 200
        mock_db.commit.assert_called_once()

    def test_update_user_not_found(self, client, mock_db):
        """Test PUT /users/{id} with non-existent user."""
        update_data = {
            "username": "updateduser"
        }
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with patch('src.api.users.get_db', return_value=mock_db):
            response = client.put("/api/v1/users/999", json=update_data)
        
        assert response.status_code == 404

    def test_delete_user(self, client, mock_db, mock_user):
        """Test DELETE /users/{id}."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        with patch('src.api.users.get_db', return_value=mock_db):
            response = client.delete("/api/v1/users/1")
        
        assert response.status_code == 200
        mock_db.delete.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_delete_user_not_found(self, client, mock_db):
        """Test DELETE /users/{id} with non-existent user."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with patch('src.api.users.get_db', return_value=mock_db):
            response = client.delete("/api/v1/users/999")
        
        assert response.status_code == 404


@pytest.mark.skipif(not API_AVAILABLE, reason="users API not available")
class TestUsersAPIAuthentication:
    """Test authentication in users API."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(users_router, prefix="/api/v1/users")
        return TestClient(app)

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = Mock()
        db.query = Mock()
        return db

    def test_login_success(self, client, mock_db):
        """Test POST /login with valid credentials."""
        mock_user = Mock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.username = "testuser"
        mock_user.hashed_password = "hashed_password"
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        login_data = {
            "email": "test@example.com",
            "password": "testpassword"
        }
        
        with patch('src.api.users.get_db', return_value=mock_db):
            with patch('src.api.users.verify_password', return_value=True):
                response = client.post("/api/v1/users/login", json=login_data)
        
        assert response.status_code == 200

    def test_login_invalid_credentials(self, client, mock_db):
        """Test POST /login with invalid credentials."""
        mock_user = Mock()
        mock_user.hashed_password = "hashed_password"
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        login_data = {
            "email": "test@example.com",
            "password": "wrongpassword"
        }
        
        with patch('src.api.users.get_db', return_value=mock_db):
            with patch('src.api.users.verify_password', return_value=False):
                response = client.post("/api/v1/users/login", json=login_data)
        
        assert response.status_code == 401

    def test_login_user_not_found(self, client, mock_db):
        """Test POST /login with non-existent user."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        login_data = {
            "email": "nonexistent@example.com",
            "password": "testpassword"
        }
        
        with patch('src.api.users.get_db', return_value=mock_db):
            response = client.post("/api/v1/users/login", json=login_data)
        
        assert response.status_code == 401


@pytest.mark.skipif(not API_AVAILABLE, reason="users API not available")
class TestUsersAPIAdmin:
    """Test admin endpoints in users API."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(users_router, prefix="/api/v1/users")
        return TestClient(app)

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = Mock()
        db.query = Mock()
        return db

    def test_get_stats_with_admin_token(self, client, mock_db):
        """Test GET /stats with valid admin token."""
        mock_db.query.return_value.count.return_value = 100
        
        with patch('src.api.users.get_db', return_value=mock_db):
            with patch.dict('os.environ', {'ADMIN_TOKEN': 'test_admin_token'}):
                response = client.get(
                    "/api/v1/users/stats",
                    headers={"X-Admin-Token": "test_admin_token"}
                )
        
        assert response.status_code == 200

    def test_get_stats_without_admin_token(self, client, mock_db):
        """Test GET /stats without admin token."""
        with patch('src.api.users.get_db', return_value=mock_db):
            response = client.get("/api/v1/users/stats")
        
        assert response.status_code == 401

    def test_get_stats_with_invalid_admin_token(self, client, mock_db):
        """Test GET /stats with invalid admin token."""
        with patch('src.api.users.get_db', return_value=mock_db):
            with patch.dict('os.environ', {'ADMIN_TOKEN': 'correct_token'}):
                response = client.get(
                    "/api/v1/users/stats",
                    headers={"X-Admin-Token": "wrong_token"}
                )
        
        assert response.status_code == 401


@pytest.mark.skipif(not API_AVAILABLE, reason="users API not available")
class TestUsersAPISessions:
    """Test session management in users API."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(users_router, prefix="/api/v1/users")
        return TestClient(app)

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = Mock()
        db.query = Mock()
        db.add = Mock()
        db.commit = Mock()
        return db

    @pytest.fixture
    def mock_session(self):
        """Create a mock session object."""
        session = Mock(spec=Session)
        session.id = 1
        session.user_id = 1
        session.session_token = "test_token"
        session.expires_at = datetime.utcnow() + timedelta(hours=24)
        session.is_active = True
        return session

    def test_create_session(self, client, mock_db, mock_session):
        """Test POST /sessions."""
        session_data = {
            "user_id": 1
        }
        
        mock_db.add.return_value = None
        mock_db.refresh.return_value = mock_session
        
        with patch('src.api.users.get_db', return_value=mock_db):
            response = client.post("/api/v1/users/sessions", json=session_data)
        
        assert response.status_code in [200, 201]
        mock_db.add.assert_called_once()

    def test_get_sessions(self, client, mock_db, mock_session):
        """Test GET /sessions."""
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_session]
        
        with patch('src.api.users.get_db', return_value=mock_db):
            response = client.get("/api/v1/users/sessions?user_id=1")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_delete_session(self, client, mock_db, mock_session):
        """Test DELETE /sessions/{id}."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session
        
        with patch('src.api.users.get_db', return_value=mock_db):
            response = client.delete("/api/v1/users/sessions/1")
        
        assert response.status_code == 200
        mock_db.delete.assert_called_once()

    def test_delete_all_sessions(self, client, mock_db):
        """Test DELETE /sessions for user."""
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        with patch('src.api.users.get_db', return_value=mock_db):
            response = client.delete("/api/v1/users/sessions?user_id=1")
        
        assert response.status_code == 200


@pytest.mark.skipif(not API_AVAILABLE, reason="users API not available")
class TestUsersAPIValidation:
    """Test input validation in users API."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(users_router, prefix="/api/v1/users")
        return TestClient(app)

    def test_create_user_missing_email(self, client):
        """Test POST /users without email."""
        user_data = {
            "username": "newuser",
            "password": "securepassword123"
        }
        
        response = client.post("/api/v1/users", json=user_data)
        assert response.status_code == 422

    def test_create_user_missing_username(self, client):
        """Test POST /users without username."""
        user_data = {
            "email": "new@example.com",
            "password": "securepassword123"
        }
        
        response = client.post("/api/v1/users", json=user_data)
        assert response.status_code == 422

    def test_create_user_missing_password(self, client):
        """Test POST /users without password."""
        user_data = {
            "email": "new@example.com",
            "username": "newuser"
        }
        
        response = client.post("/api/v1/users", json=user_data)
        assert response.status_code == 422

    def test_create_user_invalid_email_format(self, client):
        """Test POST /users with invalid email format."""
        user_data = {
            "email": "not-an-email",
            "username": "newuser",
            "password": "securepassword123"
        }
        
        response = client.post("/api/v1/users", json=user_data)
        assert response.status_code == 422

    def test_create_user_short_username(self, client):
        """Test POST /users with short username."""
        user_data = {
            "email": "new@example.com",
            "username": "ab",
            "password": "securepassword123"
        }
        
        response = client.post("/api/v1/users", json=user_data)
        assert response.status_code == 422

    def test_create_user_short_password(self, client):
        """Test POST /users with short password."""
        user_data = {
            "email": "new@example.com",
            "username": "newuser",
            "password": "short"
        }
        
        response = client.post("/api/v1/users", json=user_data)
        assert response.status_code == 422
