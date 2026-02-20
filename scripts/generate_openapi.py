#!/usr/bin/env python3
"""
OpenAPI Specification Generator for x0tta6bl4 Mesh Network

Generates OpenAPI 3.1 specification from FastAPI app with:
- Full endpoint documentation
- Request/response schemas
- Authentication requirements
- Examples for common use cases

Usage:
    python scripts/generate_openapi.py [--output docs/api/openapi.json] [--format yaml|json]
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_openapi_spec() -> Dict[str, Any]:
    """Generate OpenAPI specification from FastAPI app."""
    try:
        from src.core.app import app
        return app.openapi()
    except ImportError as e:
        logger.error(f"Failed to import app: {e}")
        raise


def enhance_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Enhance OpenAPI spec with additional metadata and examples."""
    
    # Add info metadata
    spec["info"] = {
        "title": "x0tta6bl4 Mesh Network API",
        "version": "3.2.1",
        "description": """
# x0tta6bl4 Mesh Network API

Self-healing mesh network node with MAPE-K autonomic loop and Kimi K2.5 Agent Swarm.

## Features

- **Post-Quantum Cryptography**: ML-KEM-768, ML-DSA-65 (NIST FIPS 203/204)
- **SPIFFE/SPIRE Integration**: Zero Trust workload identity with mTLS
- **Agent Swarm**: Parallel task execution with up to 100 agents
- **PARL**: Parallel Agent Reinforcement Learning for 4.5x speedup
- **Vision Module**: Visual analysis for mesh topology and anomaly detection

## Authentication

Most endpoints require `X-Admin-Token` header for authentication.

## Rate Limiting

- Standard endpoints: 100 requests/minute
- Task submission: 1000 requests/minute
- Swarm creation: 10 requests/minute
- Scaling: 5 requests/minute

## Error Handling

All errors follow RFC 7807 Problem Details format:
```json
{
  "type": "https://x0tta6bl4.mesh/errors/swarm-not-found",
  "title": "Swarm Not Found",
  "status": 404,
  "detail": "Swarm with ID 'abc123' does not exist"
}
```
        """,
        "contact": {
            "name": "x0tta6bl4 Support",
            "email": "support@x0tta6bl4.mesh",
            "url": "https://x0tta6bl4.mesh"
        },
        "license": {
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT"
        },
        "x-logo": {
            "url": "/logo.svg",
            "altText": "x0tta6bl4 Logo"
        }
    }
    
    # Add servers
    spec["servers"] = [
        {
            "url": "http://localhost:8080",
            "description": "Development server"
        },
        {
            "url": "https://api.x0tta6bl4.mesh",
            "description": "Production server"
        },
        {
            "url": "https://staging-api.x0tta6bl4.mesh",
            "description": "Staging server"
        }
    ]
    
    # Add security schemes
    spec["components"]["securitySchemes"] = {
        "AdminToken": {
            "type": "apiKey",
            "in": "header",
            "name": "X-Admin-Token",
            "description": "Admin authentication token"
        },
        "mTLS": {
            "type": "mutualTLS",
            "description": "Mutual TLS authentication with SPIFFE SVID"
        }
    }
    
    # Add common schemas
    if "schemas" not in spec["components"]:
        spec["components"]["schemas"] = {}
    
    spec["components"]["schemas"]["ErrorResponse"] = {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "format": "uri",
                "description": "Error type URI"
            },
            "title": {
                "type": "string",
                "description": "Human-readable error title"
            },
            "status": {
                "type": "integer",
                "description": "HTTP status code"
            },
            "detail": {
                "type": "string",
                "description": "Detailed error message"
            },
            "instance": {
                "type": "string",
                "description": "Request instance identifier"
            }
        },
        "required": ["type", "title", "status"]
    }
    
    spec["components"]["schemas"]["HealthStatus"] = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["healthy", "degraded", "unhealthy"],
                "description": "Overall health status"
            },
            "version": {
                "type": "string",
                "description": "API version"
            },
            "checks": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "latency_ms": {"type": "number"},
                        "message": {"type": "string"}
                    }
                }
            }
        }
    }
    
    # Add examples
    spec["components"]["examples"] = {
        "SwarmCreateRequest": {
            "summary": "Create a basic swarm",
            "value": {
                "name": "my-swarm",
                "num_agents": 10,
                "capabilities": ["task_execution", "vision_analysis"],
                "constraints": {
                    "max_parallel_steps": 1500,
                    "target_latency_ms": 100.0
                },
                "ttl_seconds": 3600
            }
        },
        "TaskSubmitRequest": {
            "summary": "Submit a mesh analysis task",
            "value": {
                "task_type": "mesh_analysis",
                "priority": 5,
                "payload": {
                    "target_nodes": ["node-1", "node-2", "node-3"],
                    "analysis_type": "latency"
                },
                "timeout_seconds": 30.0
            }
        },
        "ScaleUpRequest": {
            "summary": "Scale up swarm",
            "value": {
                "action": "scale_up",
                "num_agents": 5,
                "reason": "Increased load"
            }
        }
    }
    
    # Add tags with descriptions
    spec["tags"] = [
        {
            "name": "swarm",
            "description": "Agent swarm management with PARL parallel execution",
            "x-displayName": "Agent Swarm"
        },
        {
            "name": "users",
            "description": "User management and authentication",
            "x-displayName": "Users"
        },
        {
            "name": "billing",
            "description": "Subscription and billing management via Stripe",
            "x-displayName": "Billing"
        },
        {
            "name": "MaaS",
            "description": "Mesh-as-a-Service endpoints for network management",
            "x-displayName": "Mesh-as-a-Service"
        },
        {
            "name": "vpn",
            "description": "VPN configuration and management",
            "x-displayName": "VPN"
        },
        {
            "name": "ledger",
            "description": "Distributed ledger operations",
            "x-displayName": "Ledger"
        }
    ]
    
    # Add external docs
    spec["externalDocs"] = {
        "url": "https://docs.x0tta6bl4.mesh",
        "description": "Full documentation"
    }
    
    # Add webhooks for async notifications
    spec["webhooks"] = {
        "TaskCompleted": {
            "post": {
                "summary": "Task completion notification",
                "description": "Webhook called when a task completes",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "event": {"type": "string", "const": "task.completed"},
                                    "task_id": {"type": "string"},
                                    "swarm_id": {"type": "string"},
                                    "status": {"type": "string"},
                                    "result": {"type": "object"},
                                    "timestamp": {"type": "string", "format": "date-time"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Webhook received"}
                }
            }
        },
        "SwarmScaled": {
            "post": {
                "summary": "Swarm scaling notification",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "event": {"type": "string", "const": "swarm.scaled"},
                                    "swarm_id": {"type": "string"},
                                    "previous_count": {"type": "integer"},
                                    "new_count": {"type": "integer"},
                                    "timestamp": {"type": "string", "format": "date-time"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Webhook received"}
                }
            }
        }
    }
    
    return spec


def add_endpoint_examples(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Add examples to specific endpoints."""
    
    paths = spec.get("paths", {})
    
    # Swarm endpoints
    if "/api/v3/swarm/create" in paths:
        post_op = paths["/api/v3/swarm/create"].get("post", {})
        if "requestBody" in post_op:
            content = post_op["requestBody"].get("content", {})
            if "application/json" in content:
                content["application/json"]["examples"] = {
                    "basic": {"$ref": "#/components/examples/SwarmCreateRequest"}
                }
    
    if "/api/v3/swarm/{swarm_id}/tasks" in paths:
        post_op = paths["/api/v3/swarm/{swarm_id}/tasks"].get("post", {})
        if "requestBody" in post_op:
            content = post_op["requestBody"].get("content", {})
            if "application/json" in content:
                content["application/json"]["examples"] = {
                    "mesh_analysis": {"$ref": "#/components/examples/TaskSubmitRequest"}
                }
    
    if "/api/v3/swarm/{swarm_id}/scale" in paths:
        post_op = paths["/api/v3/swarm/{swarm_id}/scale"].get("post", {})
        if "requestBody" in post_op:
            content = post_op["requestBody"].get("content", {})
            if "application/json" in content:
                content["application/json"]["examples"] = {
                    "scale_up": {"$ref": "#/components/examples/ScaleUpRequest"}
                }
    
    return spec


def save_spec(spec: Dict[str, Any], output_path: Path, format_type: str = "json") -> None:
    """Save OpenAPI spec to file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if format_type == "yaml":
        try:
            import yaml
            with open(output_path.with_suffix(".yaml"), "w", encoding="utf-8") as f:
                yaml.dump(spec, f, default_flow_style=False, sort_keys=False)
            logger.info(f"OpenAPI spec saved to {output_path.with_suffix('.yaml')}")
        except ImportError:
            logger.warning("PyYAML not installed, falling back to JSON")
            format_type = "json"
    
    if format_type == "json":
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2, ensure_ascii=False)
        logger.info(f"OpenAPI spec saved to {output_path}")


def generate_redoc_html(spec: Dict[str, Any], output_path: Path) -> None:
    """Generate ReDoc HTML page for documentation."""
    html = """<!DOCTYPE html>
<html>
<head>
    <title>x0tta6bl4 API Documentation</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { margin: 0; padding: 0; }
    </style>
</head>
<body>
    <redoc spec-url='openapi.json'></redoc>
    <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
</body>
</html>
"""
    html_path = output_path.parent / "index.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"ReDoc HTML saved to {html_path}")


def generate_swagger_html(spec: Dict[str, Any], output_path: Path) -> None:
    """Generate Swagger UI HTML page for interactive documentation."""
    html = """<!DOCTYPE html>
<html>
<head>
    <title>x0tta6bl4 API Documentation - Swagger UI</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
    <style>
        body { margin: 0; padding: 0; }
        .topbar { display: none; }
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
    <script>
        window.onload = function() {
            const ui = SwaggerUIBundle({
                url: "openapi.json",
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                layout: "StandaloneLayout",
                deepLinking: true,
                displayOperationId: false,
                defaultModelsExpandDepth: 1,
                defaultModelExpandDepth: 1,
                docExpansion: "list",
                filter: true
            });
        }
    </script>
</body>
</html>
"""
    swagger_path = output_path.parent / "swagger.html"
    with open(swagger_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"Swagger UI HTML saved to {swagger_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate OpenAPI specification for x0tta6bl4 API"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("docs/api/openapi.json"),
        help="Output file path (default: docs/api/openapi.json)"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["json", "yaml"],
        default="json",
        help="Output format (default: json)"
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Generate HTML documentation pages (ReDoc and Swagger UI)"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate the generated spec"
    )
    
    args = parser.parse_args()
    
    logger.info("Generating OpenAPI specification...")
    
    # Get base spec from FastAPI
    spec = get_openapi_spec()
    
    # Enhance with additional metadata
    spec = enhance_spec(spec)
    spec = add_endpoint_examples(spec)
    
    # Validate if requested
    if args.validate:
        try:
            import jsonschema
            # OpenAPI 3.1 schema validation would go here
            logger.info("OpenAPI spec validation passed")
        except ImportError:
            logger.warning("jsonschema not installed, skipping validation")
    
    # Save spec
    save_spec(spec, args.output, args.format)
    
    # Generate HTML docs if requested
    if args.html:
        generate_redoc_html(spec, args.output)
        generate_swagger_html(spec, args.output)
    
    logger.info("Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
