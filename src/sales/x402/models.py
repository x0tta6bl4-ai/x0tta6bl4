"""Pydantic models for x402 paid API endpoints."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FileSnippet(BaseModel):
    file_path: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RepoTriageRequest(BaseModel):
    language: str = ""
    files: list[FileSnippet] = Field(default_factory=list)
    context: str = ""


class ApiEndpointSpec(BaseModel):
    method: str = "GET"
    path: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    sample_request: dict[str, Any] = Field(default_factory=dict)


class ApiDocsRequest(BaseModel):
    api_url: str = ""
    endpoint_specs: list[ApiEndpointSpec] = Field(default_factory=list)
    context: str = ""


class ListingAuditRequest(BaseModel):
    listing_title: str = ""
    listing_url: str = ""
    listing_text: str = ""
    price: str = ""
    category: str = ""
    platform: str = ""
    context: str = ""


class PaymentRiskRequest(BaseModel):
    pay_to: str = ""
    network: str = ""
    amount: str = ""
    resource: str = ""
    facilitator: str = ""
    asset: str = ""
    context: str = ""


class IncomeRouteRequest(BaseModel):
    income_title: str = ""
    income_source: str = ""
    platform: str = ""
    upfront_cost: str = ""
    token_cost: str = ""
    price: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    context: str = ""


class X402ValidateRequest(BaseModel):
    endpoint_url: str
    context: str = ""


class UrlSnapshotRequest(BaseModel):
    target_url: str
    max_text_bytes: int = 4096
    include_links: bool = True
    context: str = ""


class DomainHealthRequest(BaseModel):
    target: str = ""
    port: int = 443
    context: str = ""


class AgentWorldMessageRequest(BaseModel):
    message: str
    sender: str = ""
    channel: str = ""


class PreviewRouteRequest(BaseModel):
    preview_url: str
    method: str = "GET"
    body: dict[str, Any] = Field(default_factory=dict)


class AgentBazaarTaskRequest(BaseModel):
    template: str
    input: dict[str, Any] = Field(default_factory=dict)
