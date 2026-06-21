# FastAPI app API

The application factory and shared infrastructure utilities.

```python
from tashtiot_apis_library import general_create_app
from tashtiot_apis_library.fastapi_template.utils import BaseAPI, settings
```

## general_create_app

::: tashtiot_apis_library.fastapi_template._internal.general_create_app

## BaseAPI

The outbound HTTP client wrapper the connectors build on. Accepts an `httpx.Auth` via `auth=`, so it
composes with the [SSO helpers](security.md).

::: tashtiot_apis_library.fastapi_template._internal.database.basic_api.BaseAPI

## Settings

`settings` is an instance of `ApplicationSettings`. Its fields are the environment variables
documented in the [Configuration reference](../configuration.md).

::: tashtiot_apis_library.fastapi_template._internal.utils.config.ApplicationSettings
