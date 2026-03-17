# Tashtiot APIs Library

A unified Python package that consolidates infrastructure connectors and FastAPI utilities for building production-ready APIs.

## 🎯 What's Inside

This package combines two powerful toolsets:

1. **Infrastructure Connectors** - Async clients for AWX, ArgoCD, Bitbucket Server, and HashiCorp Vault
2. **FastAPI Template** - A reusable FastAPI application factory with built-in middleware, monitoring, and documentation

## 🚀 Quick Start

### Installation

```bash
pip install tashtiot-apis-library
```

### Using Infrastructure Connectors

```python
from tashtiot_apis_library import AWX, ArgoCD, Git, Vault

awx = AWX(
	base_url="https://awx.example.com",
    token="token",
)

# ArgoCD client
argo = ArgoCD(
    base_url="https://argo.example.com",
    api_key="token",
    application_set_timeout=30, # The time client waits for argo application to be synced/deleted
)

# Git client (Bitbucket Server)
git = Git(
    base_url="https://bitbucket.example.com", # The base Bitbucket URL
    token="token", # HTTP token with write permissions to bitbucket repo
    username_or_email="user@example.com", # Username or email that would connect to the bitbucket (svc account)
    project_key="PROJ", # The project key in bitbucket world
    repo_slug="repo-name", # The repo name in lower cases
    default_ref="default_ref", # The default branch the git would commuincate with
    ssh_key_file_path="/path/to/ssh/private/key", # Path to SSH private key with write permissions (for delete operations)
)

# Vault client
vault = Vault(
    base_url="https://vault.example.com", # The base Vault URL
    token="token", # Vault token with write permissions
)
```

#### Example: Reading a yaml file from Bitbucket Server and print as json

```python
import asyncio
from tashtiot_apis_library import Git

async def main():
    git = Git(
        base_url="https://bitbucket.example.com",
        token="token",
        username_or_email="user@example.com",
        project_key="PROJ",
        repo_slug="repo-name",
        default_ref="default_ref",
        ssh_key_file_path="/path/to/ssh/private/key",
    )
    values_file = await git.get_file_content("/hapoel/ole/ole/values.yaml")
    json_values = yaml.safe_load(response)
    print(json_values)
    
asyncio.run(main())
```

### Using FastAPI Template

```python
from tashtiot_apis_library import general_create_app
from tashtiot_apis_library.fastapi_template.utils import settings

app = general_create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
```

## 📦 Components

### Infrastructure Connectors

```python
from tashtiot_apis_library.connectors import ArgoCD, Git, Vault
from tashtiot_apis_library.connectors.errors import (
    ExternalServiceError,
    ArgoCDError,
    GitError,
    VaultError,
)
```

**Features:**
- ✅ Async clients that validate responses and raise typed exceptions
- ✅ High-level helpers for ArgoCD apps, Bitbucket Server repo manipulation, and Vault secrets
- ✅ Shared logging configuration with Loguru
- ✅ Minimal dependency footprint

### Standardized Return Types

Key operations in `ArgoCD` and `AWX` connectors return standardized response models:

- **Base Schema**: `OperationResponse` (status, status_code, stdout)
- **AWX**: `AWXOperationResponse` (includes `job_id`)
- **ArgoCD**: `ArgoOperationResponse` (includes `app_name`)

**Example Usage:**

```python
response = await awx.launch_job(job_template_id=1)
if response.status == "successful":
    print(f"Job {response.job_id} finished!")
```

### FastAPI Template

```python
from tashtiot_apis_library.fastapi_template import general_create_app
```

**Features:**
- ✅ Structured logging powered by Loguru
- ✅ Prometheus-compatible metrics endpoint
- ✅ Swagger UI and ReDoc with customizable static assets
- ✅ Built-in middleware for request timing, exception handling, and logging
- ✅ Health check endpoints for Kubernetes readiness/liveness probes
- ✅ Utilities for HTTP, FTP, and Kubernetes interactions

## 🔧 Configuration

The FastAPI template uses environment variables for configuration:

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Application port | `8000` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `APP_NAME` | Application name | `MyApp` |
| `DEBUG` | Debug mode | `false` |

Create a `.env` file for configuration:

```env
PORT=8000
LOG_LEVEL=INFO
APP_NAME=MyFastAPIApp
```
