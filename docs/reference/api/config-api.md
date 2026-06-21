# Remote Config API

The Remote Config capability — an authenticated proxy to an upstream Config API. Import from
`tashtiot_apis_library.fastapi_template.config_api` (and the one-call wiring from
`tashtiot_apis_library.fastapi_template`):

```python
from tashtiot_apis_library.fastapi_template import enable_remote_config_api
from tashtiot_apis_library.fastapi_template.config_api import (
    RemoteConfigProvider, ConfigRemoteSettings, RequiredInfraMetadata, InfraMetadata,
)
```

See [Enable the Remote Config API](../../how-to/enable-remote-config-api.md) for usage.

## enable_remote_config_api

::: tashtiot_apis_library.fastapi_template.config_api.wiring.enable_remote_config_api

## RemoteConfigProvider

::: tashtiot_apis_library.fastapi_template.config_api.provider.RemoteConfigProvider

## ConfigRemoteSettings

The `CONFIG_REMOTE_*` settings driving outbound auth (see
[Configuration](../configuration.md#remote-config-api-outbound-to-the-upstream)).

::: tashtiot_apis_library.fastapi_template.config_api.conf.ConfigRemoteSettings

## Coordinate models

::: tashtiot_apis_library.fastapi_template.config_api.schemas.InfraMetadata

::: tashtiot_apis_library.fastapi_template.config_api.schemas.RequiredInfraMetadata
