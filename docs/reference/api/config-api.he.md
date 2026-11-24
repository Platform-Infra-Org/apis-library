# ‏Remote Config API {#remote-config-api}

יכולת ה-Remote Config: ‏proxy מאומת ל-Config API חיצוני (upstream). ייבאו מ-
`tashtiot_apis_library.fastapi_template.config_api` (ואת החיבור בקריאה אחת מ-
`tashtiot_apis_library.fastapi_template`):

```python
from tashtiot_apis_library.fastapi_template import enable_remote_config_api
from tashtiot_apis_library.fastapi_template.config_api import (
    RemoteConfigProvider,
    ConfigRemoteSettings,
    RequiredInfraMetadata,
    InfraMetadata,
)
```

לדוגמאות שימוש, ראו [הפעלת Remote Config API](../../how-to/enable-remote-config-api.md).

## enable_remote_config_api {#enable_remote_config_api}

::: tashtiot_apis_library.fastapi_template.config_api.wiring.enable_remote_config_api

## RemoteConfigProvider {#remoteconfigprovider}

::: tashtiot_apis_library.fastapi_template.config_api.provider.RemoteConfigProvider

## ConfigRemoteSettings {#configremotesettings}

הגדרות ה-`CONFIG_REMOTE_*` שמניעות את האימות היוצא (ראו
[קונפיגורציה](../configuration.md#remote-config-api-outbound-to-the-upstream)).

::: tashtiot_apis_library.fastapi_template.config_api.conf.ConfigRemoteSettings

## כלי עזר ל-OpenAPI ולוולידציה {#openapi-validation-helpers}

‏`enable_remote_config_api` מתקין אותם בשבילכם; הם מתועדים כאן למקרה שאתם מחברים את היכולת ידנית.

::: tashtiot_apis_library.fastapi_template.config_api.openapi.make_config_openapi

::: tashtiot_apis_library.fastapi_template.config_api.errors.install_coordinate_validation_error_handler

## מודלים ורשימות ערכים מותרים {#models-allowlists}

מודלי הקואורדינטות (`InfraMetadata`, `RequiredInfraMetadata`), מודלי התשובות המפוענחות
(`ConfigResolutionResponse`, `NamingConventionResponse`, `AllProjectsResponse`), ‏
`CoordinateCatalogResponse` לנתיב discovery ‏`/coordinates` (מוחזר מ-
`RemoteConfigProvider.get_coordinate_catalog`), ‏`CoordinateTreeResponse` לנתיב המקונן
`/coordinates/tree` (מוחזר מ-`RemoteConfigProvider.get_coordinate_tree`), ורשימות הערכים המותרים
החיות `LIVE_ALLOWED_*`, שמניעות גם את ה-validators של השדות וגם את רשימות הבחירה (`enum`) ב-OpenAPI.

::: tashtiot_apis_library.fastapi_template.config_api.models
