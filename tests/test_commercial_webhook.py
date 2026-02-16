from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
from src.api.billing import router
from src.database import get_db, User
import json

app = FastAPI()
app.include_router(router)

def override_get_db():
    mock_db = MagicMock()
    try:
        yield mock_db
    finally:
        pass

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@patch("src.api.billing._require_env")
@patch("src.api.billing.XrayManager")
@patch("src.api.billing._verify_stripe_signature")
@patch("src.api.billing.mesh_provisioner") 
def test_stripe_webhook_provisioning(mock_provisioner, mock_verify, mock_xray, mock_env):
    """Test that valid Stripe webhook triggers mesh provisioning."""
    # Mocks
    mock_env.return_value = "test_secret"
    mock_verify.return_value = None # Pass signature check
    
    # Fix AsyncMock for awaited method
    mock_xray.add_user = AsyncMock()
    
    # Mock DB
    mock_db = MagicMock()
    mock_user = User(id="u1", email="test@example.com", vpn_uuid="uuid-123", plan="free")
    
    mock_query = mock_db.query.return_value
    mock_filter = mock_query.filter.return_value
    mock_filter.first.side_effect = [mock_user, MockUserAfterCommit(mock_user)] 
    
    # We need to simulate the DB commit updating the user?
    # Actually logic is: db_user = db.query... if db_user: Update fields... db.commit()
    
    app.dependency_overrides[get_db] = lambda: mock_db
    
    # Payload
    payload = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer_details": {"email": "test@example.com"},
                "customer": "cus_123",
                "subscription": "sub_123"
            }
        }
    }
    
    headers = {"Stripe-Signature": "t=123,v1=sig"}
    
    response = client.post("/api/v1/billing/webhook", json=payload, headers=headers)
    
    assert response.status_code == 200
    assert response.json() == {"received": True}
    
    # Verify User Update
    assert mock_user.plan == "pro"
    assert mock_user.stripe_customer_id == "cus_123"
    
    # Verify Provisioning Triggered
    mock_provisioner.create.assert_called_once()
    args, kwargs = mock_provisioner.create.call_args
    assert "auto-mesh-u1" in kwargs.get("name") or "auto-mesh-u1" in args[0]
    assert kwargs.get("nodes") == 5
    print("test_stripe_webhook_provisioning PASSED")

class MockUserAfterCommit:
    def __init__(self, original_user):
        self.original = original_user
        self.id = original_user.id
        self.email = original_user.email
        self.vpn_uuid = original_user.vpn_uuid
        self.plan = "pro" # Simulated update

if __name__ == "__main__":
    try:
        # The function is already decorated with patches, so we just call it.
        # The decorators will inject the mock objects.
        test_stripe_webhook_provisioning()
    except Exception as e:
        print(f"TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
