"""Offline preview of concise stdout returned by the existing status methods.

Run: DEBUG=false PYTHONPATH=src .venv/bin/python examples/awx_status_summary_demo.py
"""

import asyncio

import respx
from linux_api.operation_linux import get_machine_status

from tashtiot_apis_library import AWX


async def main():
    base = "https://awx.test"
    awx = AWX(base, "demo-token")
    try:
        with respx.mock:
            respx.get(f"{base}/api/v2/workflow_jobs/500/").respond(
                200, json={"id": 500, "name": "New machine", "status": "failed"}
            )
            respx.get(f"{base}/api/v2/workflow_jobs/500/workflow_nodes/").respond(
                200,
                json={
                    "next": None,
                    "results": [
                        {
                            "id": index,
                            "job": 500 + index,
                            "summary_fields": {
                                "job": {
                                    "name": name,
                                    "status": status,
                                    "type": "job",
                                }
                            },
                        }
                        for index, name, status in [
                            (1, "Create VM", "successful"),
                            (2, "Configure Linux", "successful"),
                            (3, "Install monitoring", "failed"),
                        ]
                    ],
                },
            )
            respx.get(f"{base}/api/v2/jobs/503/stdout/").respond(
                200,
                text="""PLAY [Monitoring]
TASK [Install monitoring agent]
fatal: [server-01]: FAILED! => {"msg": "No package monitoring-agent available", "invocation": {"verbose": "omitted"}}
PLAY RECAP *********************************************************************
server-01 : ok=4 changed=2 unreachable=0 failed=1 skipped=0 rescued=0 ignored=0
""",
            )
            result = await get_machine_status(awx, 500)
            print(result.stdout, flush=True)
            assert "No package monitoring-agent available" in result.stdout
            assert "invocation" not in result.stdout
            assert result.status == "failed"
    finally:
        await awx.client.api.aclose()


if __name__ == "__main__":
    asyncio.run(main())
