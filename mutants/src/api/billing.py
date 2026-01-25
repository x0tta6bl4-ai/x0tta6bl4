import os
import time
import hmac
import hashlib
import json
from typing import Optional, Dict, Any

import httpx
from fastapi import APIRouter, HTTPException, Request, Header, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])
from inspect import signature as _mutmut_signature
from typing import Annotated
from typing import Callable
from typing import ClassVar


MutantDict = Annotated[dict[str, Callable], "Mutant"]


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg = None):
    """Forward call to original or mutated function, depending on the environment"""
    import os
    mutant_under_test = os.environ['MUTANT_UNDER_TEST']
    if mutant_under_test == 'fail':
        from mutmut.__main__ import MutmutProgrammaticFailException
        raise MutmutProgrammaticFailException('Failed programmatically')      
    elif mutant_under_test == 'stats':
        from mutmut.__main__ import record_trampoline_hit
        record_trampoline_hit(orig.__module__ + '.' + orig.__name__)
        result = orig(*call_args, **call_kwargs)
        return result
    prefix = orig.__module__ + '.' + orig.__name__ + '__mutmut_'
    if not mutant_under_test.startswith(prefix):
        result = orig(*call_args, **call_kwargs)
        return result
    mutant_name = mutant_under_test.rpartition('.')[-1]
    if self_arg is not None:
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs)
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs)
    return result


class CheckoutSessionRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    plan: str = Field(default="pro", min_length=1, max_length=32)
    quantity: int = Field(default=1, ge=1, le=100)


def x__get_env__mutmut_orig(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def x__get_env__mutmut_1(name: str) -> Optional[str]:
    value = None
    if value is None:
        return None
    value = value.strip()
    return value or None


def x__get_env__mutmut_2(name: str) -> Optional[str]:
    value = os.getenv(None)
    if value is None:
        return None
    value = value.strip()
    return value or None


def x__get_env__mutmut_3(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is not None:
        return None
    value = value.strip()
    return value or None


def x__get_env__mutmut_4(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    value = None
    return value or None


def x__get_env__mutmut_5(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value and None

x__get_env__mutmut_mutants : ClassVar[MutantDict] = {
'x__get_env__mutmut_1': x__get_env__mutmut_1, 
    'x__get_env__mutmut_2': x__get_env__mutmut_2, 
    'x__get_env__mutmut_3': x__get_env__mutmut_3, 
    'x__get_env__mutmut_4': x__get_env__mutmut_4, 
    'x__get_env__mutmut_5': x__get_env__mutmut_5
}

def _get_env(*args, **kwargs):
    result = _mutmut_trampoline(x__get_env__mutmut_orig, x__get_env__mutmut_mutants, args, kwargs)
    return result 

_get_env.__signature__ = _mutmut_signature(x__get_env__mutmut_orig)
x__get_env__mutmut_orig.__name__ = 'x__get_env'


def x__require_env__mutmut_orig(name: str) -> str:
    value = _get_env(name)
    if not value:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Missing required configuration: {name}",
        )
    return value


def x__require_env__mutmut_1(name: str) -> str:
    value = None
    if not value:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Missing required configuration: {name}",
        )
    return value


def x__require_env__mutmut_2(name: str) -> str:
    value = _get_env(None)
    if not value:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Missing required configuration: {name}",
        )
    return value


def x__require_env__mutmut_3(name: str) -> str:
    value = _get_env(name)
    if value:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Missing required configuration: {name}",
        )
    return value


def x__require_env__mutmut_4(name: str) -> str:
    value = _get_env(name)
    if not value:
        raise HTTPException(
            status_code=None,
            detail=f"Missing required configuration: {name}",
        )
    return value


def x__require_env__mutmut_5(name: str) -> str:
    value = _get_env(name)
    if not value:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=None,
        )
    return value


def x__require_env__mutmut_6(name: str) -> str:
    value = _get_env(name)
    if not value:
        raise HTTPException(
            detail=f"Missing required configuration: {name}",
        )
    return value


def x__require_env__mutmut_7(name: str) -> str:
    value = _get_env(name)
    if not value:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
    return value

x__require_env__mutmut_mutants : ClassVar[MutantDict] = {
'x__require_env__mutmut_1': x__require_env__mutmut_1, 
    'x__require_env__mutmut_2': x__require_env__mutmut_2, 
    'x__require_env__mutmut_3': x__require_env__mutmut_3, 
    'x__require_env__mutmut_4': x__require_env__mutmut_4, 
    'x__require_env__mutmut_5': x__require_env__mutmut_5, 
    'x__require_env__mutmut_6': x__require_env__mutmut_6, 
    'x__require_env__mutmut_7': x__require_env__mutmut_7
}

def _require_env(*args, **kwargs):
    result = _mutmut_trampoline(x__require_env__mutmut_orig, x__require_env__mutmut_mutants, args, kwargs)
    return result 

_require_env.__signature__ = _mutmut_signature(x__require_env__mutmut_orig)
x__require_env__mutmut_orig.__name__ = 'x__require_env'


@router.get("/config")
async def billing_config():
    publishable_key = _get_env("STRIPE_PUBLISHABLE_KEY")
    price_id = _get_env("STRIPE_PRICE_ID")
    return {
        "configured": bool(_get_env("STRIPE_SECRET_KEY") and price_id),
        "publishable_key": publishable_key,
        "price_id": price_id,
    }


@router.post("/checkout-session")
async def create_checkout_session(payload: CheckoutSessionRequest):
    if "@" not in payload.email:
        raise HTTPException(status_code=400, detail="Invalid email")

    secret_key = _require_env("STRIPE_SECRET_KEY")
    price_id = _require_env("STRIPE_PRICE_ID")
    success_url = _get_env("STRIPE_SUCCESS_URL") or "http://localhost:8080/?success=1"
    cancel_url = _get_env("STRIPE_CANCEL_URL") or "http://localhost:8080/?canceled=1"

    data: Dict[str, Any] = {
        "mode": "subscription",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "customer_email": payload.email,
        "client_reference_id": payload.email,
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": str(payload.quantity),
        "metadata[user_email]": payload.email,
        "metadata[plan]": payload.plan,
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            "https://api.stripe.com/v1/checkout/sessions",
            data=data,
            auth=(secret_key, ""),
        )

    if resp.status_code >= 400:
        try:
            err = resp.json()
        except Exception:
            err = {"error": {"message": resp.text}}
        raise HTTPException(status_code=502, detail=err)

    session = resp.json()
    return {"id": session.get("id"), "url": session.get("url")}


def x__verify_stripe_signature__mutmut_orig(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_1(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 301) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_2(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = None
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_3(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(None):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_4(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split("XX,XX"):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_5(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = None
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_6(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "XX=XX" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_7(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" not in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_8(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = None
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_9(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split(None, 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_10(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", None)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_11(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split(1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_12(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", )
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_13(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.rsplit("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_14(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("XX=XX", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_15(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 2)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_16(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = None

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_17(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = None
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_18(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get(None)
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_19(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("XXtXX")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_20(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("T")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_21(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = None
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_22(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get(None)
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_23(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("XXv1XX")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_24(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("V1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_25(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp and not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_26(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_27(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_28(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=None, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_29(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail=None)

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_30(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_31(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, )

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_32(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=401, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_33(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="XXInvalid Stripe-Signature headerXX")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_34(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="invalid stripe-signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_35(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="INVALID STRIPE-SIGNATURE HEADER")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_36(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_37(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(None)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_38(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=None, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_39(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail=None)

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_40(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_41(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, )

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_42(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_43(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="XXInvalid signature timestampXX")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_44(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_45(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="INVALID SIGNATURE TIMESTAMP")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_46(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(None) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_47(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) + ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_48(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(None) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_49(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) >= tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_50(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=None, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_51(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail=None)

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_52(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_53(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, )

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_54(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=401, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_55(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="XXSignature timestamp outside toleranceXX")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_56(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_57(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="SIGNATURE TIMESTAMP OUTSIDE TOLERANCE")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_58(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = None
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_59(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") - payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_60(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode(None) + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_61(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("XXutf-8XX") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_62(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("UTF-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_63(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = None

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_64(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(None, signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_65(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), None, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_66(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, None).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_67(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_68(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_69(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, ).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_70(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode(None), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_71(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("XXutf-8XX"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_72(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("UTF-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_73(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_74(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(None, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_75(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, None):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_76(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_77(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, ):
        raise HTTPException(status_code=400, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_78(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=None, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_79(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail=None)


def x__verify_stripe_signature__mutmut_80(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(detail="Invalid signature")


def x__verify_stripe_signature__mutmut_81(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, )


def x__verify_stripe_signature__mutmut_82(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=401, detail="Invalid signature")


def x__verify_stripe_signature__mutmut_83(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="XXInvalid signatureXX")


def x__verify_stripe_signature__mutmut_84(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="invalid signature")


def x__verify_stripe_signature__mutmut_85(payload: bytes, signature_header: str, secret: str, tolerance_seconds: int = 300) -> None:
    parts: Dict[str, str] = {}
    for item in signature_header.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v

    timestamp = parts.get("t")
    sig = parts.get("v1")
    if not timestamp or not sig:
        raise HTTPException(status_code=400, detail="Invalid Stripe-Signature header")

    try:
        ts_int = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature timestamp")

    if abs(int(time.time()) - ts_int) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="Signature timestamp outside tolerance")

    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="INVALID SIGNATURE")

x__verify_stripe_signature__mutmut_mutants : ClassVar[MutantDict] = {
'x__verify_stripe_signature__mutmut_1': x__verify_stripe_signature__mutmut_1, 
    'x__verify_stripe_signature__mutmut_2': x__verify_stripe_signature__mutmut_2, 
    'x__verify_stripe_signature__mutmut_3': x__verify_stripe_signature__mutmut_3, 
    'x__verify_stripe_signature__mutmut_4': x__verify_stripe_signature__mutmut_4, 
    'x__verify_stripe_signature__mutmut_5': x__verify_stripe_signature__mutmut_5, 
    'x__verify_stripe_signature__mutmut_6': x__verify_stripe_signature__mutmut_6, 
    'x__verify_stripe_signature__mutmut_7': x__verify_stripe_signature__mutmut_7, 
    'x__verify_stripe_signature__mutmut_8': x__verify_stripe_signature__mutmut_8, 
    'x__verify_stripe_signature__mutmut_9': x__verify_stripe_signature__mutmut_9, 
    'x__verify_stripe_signature__mutmut_10': x__verify_stripe_signature__mutmut_10, 
    'x__verify_stripe_signature__mutmut_11': x__verify_stripe_signature__mutmut_11, 
    'x__verify_stripe_signature__mutmut_12': x__verify_stripe_signature__mutmut_12, 
    'x__verify_stripe_signature__mutmut_13': x__verify_stripe_signature__mutmut_13, 
    'x__verify_stripe_signature__mutmut_14': x__verify_stripe_signature__mutmut_14, 
    'x__verify_stripe_signature__mutmut_15': x__verify_stripe_signature__mutmut_15, 
    'x__verify_stripe_signature__mutmut_16': x__verify_stripe_signature__mutmut_16, 
    'x__verify_stripe_signature__mutmut_17': x__verify_stripe_signature__mutmut_17, 
    'x__verify_stripe_signature__mutmut_18': x__verify_stripe_signature__mutmut_18, 
    'x__verify_stripe_signature__mutmut_19': x__verify_stripe_signature__mutmut_19, 
    'x__verify_stripe_signature__mutmut_20': x__verify_stripe_signature__mutmut_20, 
    'x__verify_stripe_signature__mutmut_21': x__verify_stripe_signature__mutmut_21, 
    'x__verify_stripe_signature__mutmut_22': x__verify_stripe_signature__mutmut_22, 
    'x__verify_stripe_signature__mutmut_23': x__verify_stripe_signature__mutmut_23, 
    'x__verify_stripe_signature__mutmut_24': x__verify_stripe_signature__mutmut_24, 
    'x__verify_stripe_signature__mutmut_25': x__verify_stripe_signature__mutmut_25, 
    'x__verify_stripe_signature__mutmut_26': x__verify_stripe_signature__mutmut_26, 
    'x__verify_stripe_signature__mutmut_27': x__verify_stripe_signature__mutmut_27, 
    'x__verify_stripe_signature__mutmut_28': x__verify_stripe_signature__mutmut_28, 
    'x__verify_stripe_signature__mutmut_29': x__verify_stripe_signature__mutmut_29, 
    'x__verify_stripe_signature__mutmut_30': x__verify_stripe_signature__mutmut_30, 
    'x__verify_stripe_signature__mutmut_31': x__verify_stripe_signature__mutmut_31, 
    'x__verify_stripe_signature__mutmut_32': x__verify_stripe_signature__mutmut_32, 
    'x__verify_stripe_signature__mutmut_33': x__verify_stripe_signature__mutmut_33, 
    'x__verify_stripe_signature__mutmut_34': x__verify_stripe_signature__mutmut_34, 
    'x__verify_stripe_signature__mutmut_35': x__verify_stripe_signature__mutmut_35, 
    'x__verify_stripe_signature__mutmut_36': x__verify_stripe_signature__mutmut_36, 
    'x__verify_stripe_signature__mutmut_37': x__verify_stripe_signature__mutmut_37, 
    'x__verify_stripe_signature__mutmut_38': x__verify_stripe_signature__mutmut_38, 
    'x__verify_stripe_signature__mutmut_39': x__verify_stripe_signature__mutmut_39, 
    'x__verify_stripe_signature__mutmut_40': x__verify_stripe_signature__mutmut_40, 
    'x__verify_stripe_signature__mutmut_41': x__verify_stripe_signature__mutmut_41, 
    'x__verify_stripe_signature__mutmut_42': x__verify_stripe_signature__mutmut_42, 
    'x__verify_stripe_signature__mutmut_43': x__verify_stripe_signature__mutmut_43, 
    'x__verify_stripe_signature__mutmut_44': x__verify_stripe_signature__mutmut_44, 
    'x__verify_stripe_signature__mutmut_45': x__verify_stripe_signature__mutmut_45, 
    'x__verify_stripe_signature__mutmut_46': x__verify_stripe_signature__mutmut_46, 
    'x__verify_stripe_signature__mutmut_47': x__verify_stripe_signature__mutmut_47, 
    'x__verify_stripe_signature__mutmut_48': x__verify_stripe_signature__mutmut_48, 
    'x__verify_stripe_signature__mutmut_49': x__verify_stripe_signature__mutmut_49, 
    'x__verify_stripe_signature__mutmut_50': x__verify_stripe_signature__mutmut_50, 
    'x__verify_stripe_signature__mutmut_51': x__verify_stripe_signature__mutmut_51, 
    'x__verify_stripe_signature__mutmut_52': x__verify_stripe_signature__mutmut_52, 
    'x__verify_stripe_signature__mutmut_53': x__verify_stripe_signature__mutmut_53, 
    'x__verify_stripe_signature__mutmut_54': x__verify_stripe_signature__mutmut_54, 
    'x__verify_stripe_signature__mutmut_55': x__verify_stripe_signature__mutmut_55, 
    'x__verify_stripe_signature__mutmut_56': x__verify_stripe_signature__mutmut_56, 
    'x__verify_stripe_signature__mutmut_57': x__verify_stripe_signature__mutmut_57, 
    'x__verify_stripe_signature__mutmut_58': x__verify_stripe_signature__mutmut_58, 
    'x__verify_stripe_signature__mutmut_59': x__verify_stripe_signature__mutmut_59, 
    'x__verify_stripe_signature__mutmut_60': x__verify_stripe_signature__mutmut_60, 
    'x__verify_stripe_signature__mutmut_61': x__verify_stripe_signature__mutmut_61, 
    'x__verify_stripe_signature__mutmut_62': x__verify_stripe_signature__mutmut_62, 
    'x__verify_stripe_signature__mutmut_63': x__verify_stripe_signature__mutmut_63, 
    'x__verify_stripe_signature__mutmut_64': x__verify_stripe_signature__mutmut_64, 
    'x__verify_stripe_signature__mutmut_65': x__verify_stripe_signature__mutmut_65, 
    'x__verify_stripe_signature__mutmut_66': x__verify_stripe_signature__mutmut_66, 
    'x__verify_stripe_signature__mutmut_67': x__verify_stripe_signature__mutmut_67, 
    'x__verify_stripe_signature__mutmut_68': x__verify_stripe_signature__mutmut_68, 
    'x__verify_stripe_signature__mutmut_69': x__verify_stripe_signature__mutmut_69, 
    'x__verify_stripe_signature__mutmut_70': x__verify_stripe_signature__mutmut_70, 
    'x__verify_stripe_signature__mutmut_71': x__verify_stripe_signature__mutmut_71, 
    'x__verify_stripe_signature__mutmut_72': x__verify_stripe_signature__mutmut_72, 
    'x__verify_stripe_signature__mutmut_73': x__verify_stripe_signature__mutmut_73, 
    'x__verify_stripe_signature__mutmut_74': x__verify_stripe_signature__mutmut_74, 
    'x__verify_stripe_signature__mutmut_75': x__verify_stripe_signature__mutmut_75, 
    'x__verify_stripe_signature__mutmut_76': x__verify_stripe_signature__mutmut_76, 
    'x__verify_stripe_signature__mutmut_77': x__verify_stripe_signature__mutmut_77, 
    'x__verify_stripe_signature__mutmut_78': x__verify_stripe_signature__mutmut_78, 
    'x__verify_stripe_signature__mutmut_79': x__verify_stripe_signature__mutmut_79, 
    'x__verify_stripe_signature__mutmut_80': x__verify_stripe_signature__mutmut_80, 
    'x__verify_stripe_signature__mutmut_81': x__verify_stripe_signature__mutmut_81, 
    'x__verify_stripe_signature__mutmut_82': x__verify_stripe_signature__mutmut_82, 
    'x__verify_stripe_signature__mutmut_83': x__verify_stripe_signature__mutmut_83, 
    'x__verify_stripe_signature__mutmut_84': x__verify_stripe_signature__mutmut_84, 
    'x__verify_stripe_signature__mutmut_85': x__verify_stripe_signature__mutmut_85
}

def _verify_stripe_signature(*args, **kwargs):
    result = _mutmut_trampoline(x__verify_stripe_signature__mutmut_orig, x__verify_stripe_signature__mutmut_mutants, args, kwargs)
    return result 

_verify_stripe_signature.__signature__ = _mutmut_signature(x__verify_stripe_signature__mutmut_orig)
x__verify_stripe_signature__mutmut_orig.__name__ = 'x__verify_stripe_signature'


@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: Optional[str] = Header(default=None, alias="Stripe-Signature")):
    secret = _require_env("STRIPE_WEBHOOK_SECRET")
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    payload = await request.body()
    _verify_stripe_signature(payload, stripe_signature, secret)

    try:
        event = json.loads(payload.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = event.get("type")
    obj = ((event.get("data") or {}).get("object") or {})

    email = None
    customer_details = obj.get("customer_details") if isinstance(obj, dict) else None
    if isinstance(customer_details, dict):
        email = customer_details.get("email")
    if not email:
        email = obj.get("customer_email") if isinstance(obj, dict) else None
    if not email:
        metadata = obj.get("metadata") if isinstance(obj, dict) else None
        if isinstance(metadata, dict):
            email = metadata.get("user_email")

    if email and event_type in {"checkout.session.completed", "invoice.paid", "customer.subscription.created"}:
        try:
            from src.api.users import users_db
            from src.database import SessionLocal, User, License
            from src.sales.telegram_bot import TokenGenerator
            
            # Update in-memory user
            user = users_db.get(email)
            if user is not None:
                user["plan"] = "pro"
                user["stripe_customer_id"] = obj.get("customer")
                user["stripe_subscription_id"] = obj.get("subscription")
            
            # Update database
            db = SessionLocal()
            try:
                db_user = db.query(User).filter(User.email == email).first()
                if db_user:
                    db_user.plan = "pro"
                    db_user.stripe_customer_id = obj.get("customer")
                    db_user.stripe_subscription_id = obj.get("subscription")
                    db.commit()
                    db.refresh(db_user)
                    
                    # Generate license for pro plan
                    license_token = TokenGenerator.generate(tier="pro")
                    new_license = License(
                        token=license_token,
                        user_id=db_user.id,
                        tier="pro",
                        is_active=True
                    )
                    db.add(new_license)
                    db.commit()
                    
                    logger.info(f"Generated pro license {license_token} for user {email}")
            except Exception as e:
                logger.error(f"Database update failed: {e}")
                db.rollback()
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Webhook processing failed: {e}")

    return {"received": True}
