"""The single wiring point: build connectors once, wire optional capabilities, mount routers."""

import argparse

import uvicorn
from fastapi import FastAPI
from loguru import logger

from tashtiot_apis_library import AWX, general_create_app
from tashtiot_apis_library.fastapi_template import enable_remote_config_api
from tashtiot_apis_library.fastapi_template.errors import AuthConfigError

from .global_conf import global_config
from .v1.dns.conf import config as dns_config
from .v1.dns.routes import get_v1_dns_router


def create_app() -> FastAPI:
    # enable_auth=True always; AUTH_ENABLED decides at runtime whether auth is enforced.
    app = general_create_app(
        enable_auth=True, title=global_config.API_TITLE, version=global_config.APP_VERSION
    )

    awx = AWX(global_config.AWX_URL, global_config.AWX_TOKEN)  # once, never per request

    # Remote Config: opt-in, only when an upstream is configured.
    provider = None
    if global_config.CONFIG_API_URL:
        try:
            provider = enable_remote_config_api(
                app,
                base_url=global_config.CONFIG_API_URL,
                remote_prefix=global_config.CONFIG_API_REMOTE_PREFIX,
                coordinate_paths=[f"{dns_config.API_PREFIX}/"],  # regexes (re.fullmatch)
            )
        except AuthConfigError as exc:
            logger.warning("Remote Config provider not enabled: {}", exc)

    app.include_router(get_v1_dns_router(awx, provider))
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the API.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    uvicorn.run(create_app(), host=args.host, port=args.port)
