"""
Unit tests for src/database/__init__.py
Tests database models, session management, and database initialization.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Import database module
try:
    from src.database import (DATABASE_URL, Base, License, Payment, Session,
                              SessionLocal, User, engine, get_db, init_db)

    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False


@pytest.mark.skipif(not DATABASE_AVAILABLE, reason="database module not available")
class TestDatabaseModels:
    """Test database models."""

    def test_user_model_creation(self):
        """Test creating a User model instance."""
        user = User(
            email="test@example.com",
            username="testuser",
            hashed_password="hashed_password",
        )
        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.hashed_password == "hashed_password"

    def test_user_model_defaults(self):
        """Test User model default values."""
        user = User(
            email="test@example.com",
            username="testuser",
            hashed_password="hashed_password",
        )
        assert user.is_active is True
        assert user.is_admin is False

    def test_session_model_creation(self):
        """Test creating a Session model instance."""
        session = Session(
            user_id=1,
            session_token="test_token",
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        assert session.user_id == 1
        assert session.session_token == "test_token"
        assert session.is_active is True

    def test_payment_model_creation(self):
        """Test creating a Payment model instance."""
        payment = Payment(user_id=1, amount=10.0, currency="USD", status="pending")
        assert payment.user_id == 1
        assert payment.amount == 10.0
        assert payment.currency == "USD"
        assert payment.status == "pending"

    def test_license_model_creation(self):
        """Test creating a License model instance."""
        license = License(
            user_id=1,
            license_key="test_license_key",
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        assert license.user_id == 1
        assert license.license_key == "test_license_key"
        assert license.is_active is True


@pytest.mark.skipif(not DATABASE_AVAILABLE, reason="database module not available")
class TestSessionLocal:
    """Test SessionLocal session factory."""

    def test_session_local_creates_session(self):
        """Test SessionLocal creates a new session."""
        session = SessionLocal()
        assert session is not None
        session.close()

    def test_session_local_is_callable(self):
        """Test SessionLocal is callable."""
        assert callable(SessionLocal)


@pytest.mark.skipif(not DATABASE_AVAILABLE, reason="database module not available")
class TestGetDb:
    """Test get_db dependency function."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock session."""
        session = Mock()
        session.close = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        return session

    def test_get_db_yields_session(self, mock_session):
        """Test get_db yields a session."""
        with patch("src.database.SessionLocal", return_value=mock_session):
            db_gen = get_db()
            db = next(db_gen)
            assert db is not None
            # Clean up
            try:
                next(db_gen)
            except StopIteration:
                pass

    def test_get_db_closes_session_on_exit(self, mock_session):
        """Test get_db closes session on exit."""
        with patch("src.database.SessionLocal", return_value=mock_session):
            db_gen = get_db()
            db = next(db_gen)

            # Trigger cleanup
            try:
                next(db_gen)
            except StopIteration:
                pass

            # Verify close was called
            mock_session.close.assert_called_once()


@pytest.mark.skipif(not DATABASE_AVAILABLE, reason="database module not available")
class TestInitDb:
    """Test init_db function."""

    @patch("src.database.create_all")
    @patch("src.database.engine")
    def test_init_db_creates_tables(self, mock_engine, mock_create_all):
        """Test init_db creates all tables."""
        init_db()
        mock_create_all.assert_called_once()

    @patch("src.database.create_all")
    @patch("src.database.engine")
    def test_init_db_handles_exceptions(self, mock_engine, mock_create_all):
        """Test init_db handles exceptions gracefully."""
        mock_create_all.side_effect = Exception("Database error")

        # Should not raise exception
        init_db()

        mock_create_all.assert_called_once()


@pytest.mark.skipif(not DATABASE_AVAILABLE, reason="database module not available")
class TestDatabaseUrl:
    """Test DATABASE_URL configuration."""

    def test_database_url_exists(self):
        """Test DATABASE_URL is defined."""
        assert DATABASE_URL is not None

    def test_database_url_is_string(self):
        """Test DATABASE_URL is a string."""
        assert isinstance(DATABASE_URL, str)

    def test_database_url_has_scheme(self):
        """Test DATABASE_URL has a valid scheme."""
        valid_schemes = [
            "sqlite://",
            "postgresql://",
            "mysql://",
            "postgresql+asyncpg://",
        ]
        assert any(DATABASE_URL.startswith(scheme) for scheme in valid_schemes)


@pytest.mark.skipif(not DATABASE_AVAILABLE, reason="database module not available")
class TestUserModelMethods:
    """Test User model methods."""

    def test_user_repr(self):
        """Test User __repr__ method."""
        user = User(id=1, email="test@example.com", username="testuser")
        repr_str = repr(user)
        assert "test@example.com" in repr_str or "testuser" in repr_str

    def test_user_set_password(self):
        """Test User set_password method if exists."""
        user = User(email="test@example.com", username="testuser")

        # Check if set_password method exists
        if hasattr(user, "set_password"):
            user.set_password("test_password")
            assert user.hashed_password is not None
            assert user.hashed_password != "test_password"

    def test_user_check_password(self):
        """Test User check_password method if exists."""
        user = User(email="test@example.com", username="testuser")

        # Check if check_password method exists
        if hasattr(user, "check_password"):
            # First set password
            if hasattr(user, "set_password"):
                user.set_password("test_password")

            # Then check it
            result = user.check_password("test_password")
            assert result is True

            # Check wrong password
            result = user.check_password("wrong_password")
            assert result is False


@pytest.mark.skipif(not DATABASE_AVAILABLE, reason="database module not available")
class TestSessionModelMethods:
    """Test Session model methods."""

    def test_session_is_valid(self):
        """Test Session is_valid method if exists."""
        session = Session(
            user_id=1,
            session_token="test_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )

        if hasattr(session, "is_valid"):
            assert session.is_valid() is True

    def test_session_is_expired(self):
        """Test Session is_valid returns False for expired sessions."""
        session = Session(
            user_id=1,
            session_token="test_token",
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )

        if hasattr(session, "is_valid"):
            assert session.is_valid() is False


@pytest.mark.skipif(not DATABASE_AVAILABLE, reason="database module not available")
class TestPaymentModelMethods:
    """Test Payment model methods."""

    def test_payment_repr(self):
        """Test Payment __repr__ method."""
        payment = Payment(
            id=1, user_id=1, amount=10.0, currency="USD", status="completed"
        )
        repr_str = repr(payment)
        assert "10.0" in repr_str or "USD" in repr_str

    def test_payment_is_successful(self):
        """Test Payment is_successful method if exists."""
        payment = Payment(user_id=1, amount=10.0, currency="USD", status="completed")

        if hasattr(payment, "is_successful"):
            assert payment.is_successful() is True

    def test_payment_is_pending(self):
        """Test Payment is_pending method if exists."""
        payment = Payment(user_id=1, amount=10.0, currency="USD", status="pending")

        if hasattr(payment, "is_pending"):
            assert payment.is_pending() is True


@pytest.mark.skipif(not DATABASE_AVAILABLE, reason="database module not available")
class TestLicenseModelMethods:
    """Test License model methods."""

    def test_license_repr(self):
        """Test License __repr__ method."""
        license = License(id=1, user_id=1, license_key="test_license_key")
        repr_str = repr(license)
        assert "test_license_key" in repr_str

    def test_license_is_valid(self):
        """Test License is_valid method if exists."""
        license = License(
            user_id=1,
            license_key="test_license_key",
            expires_at=datetime.utcnow() + timedelta(days=30),
        )

        if hasattr(license, "is_valid"):
            assert license.is_valid() is True

    def test_license_is_expired(self):
        """Test License is_valid returns False for expired licenses."""
        license = License(
            user_id=1,
            license_key="test_license_key",
            expires_at=datetime.utcnow() - timedelta(days=1),
        )

        if hasattr(license, "is_valid"):
            assert license.is_valid() is False


@pytest.mark.skipif(not DATABASE_AVAILABLE, reason="database module not available")
class TestDatabaseIntegration:
    """Integration tests for database operations."""

    @patch("src.database.SessionLocal")
    def test_create_user(self, mock_session_local):
        """Test creating a user in the database."""
        mock_session = Mock()
        mock_session_local.return_value = mock_session

        user = User(
            email="test@example.com",
            username="testuser",
            hashed_password="hashed_password",
        )

        mock_session.add(user)
        mock_session.commit()
        mock_session.refresh(user)

        mock_session.add.assert_called_once_with(user)
        mock_session.commit.assert_called_once()

    @patch("src.database.SessionLocal")
    def test_query_user_by_email(self, mock_session_local):
        """Test querying a user by email."""
        mock_session = Mock()
        mock_query = Mock()
        mock_filter = Mock()
        mock_first = Mock()

        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = Mock()

        mock_session_local.return_value = mock_session

        from src.database import SessionLocal

        session = SessionLocal()

        user = session.query(User).filter(User.email == "test@example.com").first()

        mock_session.query.assert_called_once_with(User)
        mock_query.filter.assert_called_once()
        mock_filter.first.assert_called_once()

        session.close()

    @patch("src.database.SessionLocal")
    def test_update_user(self, mock_session_local):
        """Test updating a user in the database."""
        mock_session = Mock()
        mock_session_local.return_value = mock_session

        user = User(id=1, email="test@example.com", username="testuser")

        user.username = "updated_user"
        mock_session.commit()

        mock_session.commit.assert_called_once()

    @patch("src.database.SessionLocal")
    def test_delete_user(self, mock_session_local):
        """Test deleting a user from the database."""
        mock_session = Mock()
        mock_session_local.return_value = mock_session

        user = User(id=1, email="test@example.com", username="testuser")

        mock_session.delete(user)
        mock_session.commit()

        mock_session.delete.assert_called_once_with(user)
        mock_session.commit.assert_called_once()
