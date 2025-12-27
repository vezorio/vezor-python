# Vezor Python SDK

A Python SDK for interacting with the Vezor secrets management platform.

## Installation

```bash
pip install vezor
```

This installs both the SDK and CLI tools. After installation, you can use the `vezor` command in your terminal.

## Quick Start

```python
from vezor import VezorClient

# Initialize the client
client = VezorClient(
    base_url="https://api.vezor.io",
    token="your-api-token",
    organization_id="your-org-uuid"
)

# List all secrets
result = client.list_secrets()
for secret in result["secrets"]:
    print(f"{secret['key_name']}: {secret['tags']}")

# Get a secret by name
secret = client.get_secret_by_name("DATABASE_URL", tags={"env": "prod"})
if secret:
    print(secret["value"])

# Create a new secret
client.create_secret(
    key_name="API_KEY",
    value="sk-live-xxx",
    tags={"env": "prod", "app": "api"},
    description="Stripe API key"
)
```

## Authentication

The Vezor SDK supports two authentication methods:

### 1. API Token (Recommended for programmatic use)

```python
from vezor import VezorClient

client = VezorClient(
    base_url="https://api.vezor.io",
    token="your-api-token",
    organization_id="your-org-uuid"
)
```

### 2. Set token after initialization

```python
client = VezorClient(base_url="https://api.vezor.io")
client.set_token("your-api-token")
client.set_organization("your-org-uuid")
```

## Core Operations

### Listing Secrets

```python
# List all secrets
result = client.list_secrets()

# Filter by tags
result = client.list_secrets(tags={"env": "prod", "app": "api"})

# Search by key name
result = client.list_secrets(search="DATABASE")

# Pagination
result = client.list_secrets(limit=10, offset=0)

# Combined
result = client.list_secrets(
    tags={"env": "prod"},
    search="API",
    limit=25,
    offset=0
)

# Response structure
print(result["secrets"])  # List of secret objects
print(result["total"])    # Total matching secrets
print(result["count"])    # Secrets in this page
```

### Getting Secrets

```python
# Get by ID
secret = client.get_secret("secret-uuid")
print(secret["value"])

# Get a specific version
old_secret = client.get_secret("secret-uuid", version=2)

# Get by name (convenience method)
secret = client.get_secret_by_name("DATABASE_URL", tags={"env": "prod"})
```

### Creating Secrets

```python
client.create_secret(
    key_name="DATABASE_URL",
    value="postgres://user:pass@host:5432/db",
    tags={"env": "prod", "app": "api", "team": "backend"},
    description="Production PostgreSQL connection string",
    value_type="connection_string"  # string, password, url, connection_string
)
```

### Updating Secrets

```python
# Update value (creates a new version)
client.update_secret("secret-uuid", value="new-password")

# Update description
client.update_secret("secret-uuid", description="Updated description")

# Update tags
client.update_secret("secret-uuid", tags={"env": "prod", "app": "api-v2"})
```

### Deleting Secrets

```python
client.delete_secret("secret-uuid")
```

### Version History

```python
# Get all versions
versions = client.get_secret_versions("secret-uuid")
for v in versions["versions"]:
    print(f"v{v['version']} - {v['created_at']} by {v['created_by']}")

# Get a specific version's value
old_value = client.get_secret("secret-uuid", version=2)
```

## Tags

Tags are key-value pairs used to organize and filter secrets.

```python
# Get all available tags
tags = client.get_tags()
# {"env": ["dev", "staging", "prod"], "app": ["api", "web", "worker"]}

# Filter secrets by tags
prod_secrets = client.list_secrets(tags={"env": "prod"})
api_secrets = client.list_secrets(tags={"env": "prod", "app": "api"})
```

## Groups

Groups are predefined tag combinations for organizing secrets.

```python
# List all groups
groups = client.list_groups()

# Get a specific group
group = client.get_group("production-api")

# Get secret count for a group
count = client.get_group_secret_count("production-api")

# Pull all secrets for a group
secrets = client.pull_group_secrets("production-api")
for key, value in secrets["secrets"].items():
    print(f"{key}={value}")

# Export as .env format
env_content = client.pull_group_secrets("production-api", format="env")
```

## Import/Export

```python
# Export secrets as .env format
env_content = client.export_env(tags={"env": "prod", "app": "api"})
with open(".env.prod", "w") as f:
    f.write(env_content)

# Import from .env file
with open(".env.local") as f:
    content = f.read()
client.import_env("development", content)
```

## Organizations

```python
# List your organizations
orgs = client.list_organizations()
for org in orgs["organizations"]:
    print(f"{org['name']} ({org['id']})")

# Get organization details
org = client.get_organization("org-uuid")

# Create a new organization
new_org = client.create_organization(
    name="My Team",
    description="Development team secrets"
)
```

## Schema Validation

```python
schema = """
version: 1
project: my-app

base:
  database_url:
    type: connection_string
    required: true
  api_key:
    type: password
    required: true
"""

result = client.validate_schema(schema, environment="production")
if result.get("valid"):
    print("All secrets present!")
else:
    print("Missing secrets:", result.get("missing"))
```

## Audit Log

```python
# Get recent audit entries
audit = client.get_audit_log(limit=50)
for entry in audit["entries"]:
    print(f"{entry['timestamp']} - {entry['action']} - {entry['user_email']}")
```

## Error Handling

The SDK provides specific exception classes for different error types:

```python
from vezor import (
    VezorClient,
    VezorError,
    VezorAuthError,
    VezorNotFoundError,
    VezorValidationError,
    VezorPermissionError,
    VezorAPIError,
)

client = VezorClient(base_url="https://api.vezor.io", token="...")

try:
    secret = client.get_secret("non-existent-id")
except VezorAuthError:
    print("Authentication failed - check your token")
except VezorNotFoundError:
    print("Secret not found")
except VezorPermissionError:
    print("You don't have access to this secret")
except VezorValidationError as e:
    print(f"Invalid request: {e}")
except VezorAPIError as e:
    print(f"API error {e.status_code}: {e}")
except VezorError as e:
    print(f"General error: {e}")
```

## Environment Variables

The SDK can be configured using environment variables:

```bash
export VEZOR_API_URL="https://api.vezor.io"
export VEZOR_TOKEN="your-api-token"
export VEZOR_ORGANIZATION_ID="your-org-uuid"
```

```python
import os
from vezor import VezorClient

client = VezorClient(
    base_url=os.environ.get("VEZOR_API_URL", "https://api.vezor.io"),
    token=os.environ.get("VEZOR_TOKEN"),
    organization_id=os.environ.get("VEZOR_ORGANIZATION_ID")
)
```

## Use Cases

### CI/CD Pipeline

```python
# .github/workflows/deploy.yml equivalent in Python
from vezor import VezorClient
import os

client = VezorClient(
    base_url=os.environ["VEZOR_API_URL"],
    token=os.environ["VEZOR_TOKEN"],
    organization_id=os.environ["VEZOR_ORG_ID"]
)

# Pull production secrets and write to .env
env_content = client.export_env(tags={"env": "prod", "app": "api"})
with open(".env", "w") as f:
    f.write(env_content)
```

### Local Development Setup

```python
from vezor import VezorClient

def setup_local_env():
    client = VezorClient(
        base_url="https://api.vezor.io",
        token=os.environ.get("VEZOR_TOKEN"),
        organization_id="your-org-uuid"
    )

    # Get development secrets
    env_content = client.export_env(tags={"env": "dev"})

    with open(".env", "w") as f:
        f.write(env_content)

    print("Development environment configured!")

if __name__ == "__main__":
    setup_local_env()
```

### Secret Rotation Script

```python
from vezor import VezorClient
import secrets

def rotate_api_key(client, key_name, env):
    # Find existing secret
    secret = client.get_secret_by_name(key_name, tags={"env": env})

    if not secret:
        print(f"Secret {key_name} not found")
        return

    # Generate new value
    new_key = secrets.token_urlsafe(32)

    # Update (creates new version, preserves history)
    client.update_secret(secret["id"], value=new_key)

    print(f"Rotated {key_name} - new version: {secret['version'] + 1}")
    return new_key

# Usage
client = VezorClient(...)
new_key = rotate_api_key(client, "API_SECRET_KEY", "prod")
```

### Bulk Operations

```python
from vezor import VezorClient

client = VezorClient(...)

# Copy secrets from one environment to another
def copy_env(source_env, target_env):
    source_secrets = client.list_secrets(tags={"env": source_env})

    for secret in source_secrets["secrets"]:
        # Get the full secret with value
        full_secret = client.get_secret(secret["id"])

        # Update tags for target environment
        new_tags = full_secret["tags"].copy()
        new_tags["env"] = target_env

        # Create in target environment
        client.create_secret(
            key_name=full_secret["key_name"],
            value=full_secret["value"],
            tags=new_tags,
            description=full_secret.get("description", "")
        )

copy_env("staging", "prod")
```

## API Reference

### VezorClient

| Method | Description |
|--------|-------------|
| `list_secrets(tags, search, limit, offset)` | List secrets with filtering |
| `get_secret(id, version)` | Get secret by ID |
| `get_secret_by_name(name, tags)` | Get secret by key name |
| `create_secret(key_name, value, tags, ...)` | Create new secret |
| `update_secret(id, value, description, tags)` | Update existing secret |
| `delete_secret(id)` | Delete secret |
| `get_secret_versions(id)` | Get version history |
| `get_tags()` | Get available tags |
| `export_env(tags)` | Export as .env format |
| `import_env(environment, content)` | Import from .env |
| `list_groups()` | List secret groups |
| `get_group(name)` | Get group details |
| `pull_group_secrets(name, format)` | Pull secrets by group |
| `list_organizations()` | List organizations |
| `get_organization(id)` | Get organization |
| `create_organization(name, description)` | Create organization |
| `validate_schema(content, environment)` | Validate schema |
| `get_audit_log(limit, offset)` | Get audit entries |
| `health()` | Check API health |

## Requirements

- Python 3.8+
- `requests` library (automatically installed)

## License

MIT License
