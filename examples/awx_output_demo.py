"""Offline AWX -> FastAPI -> Dispatcher simulation. Requires dev dependencies.

Run: DEBUG=false PYTHONPATH=src .venv/bin/python examples/awx_output_demo.py
"""

import asyncio
import time

import httpx
import respx
from fastapi import FastAPI

from tashtiot_apis_library import AWX


async def main():
    awx = AWX("https://awx.test", "demo-token")
    app = FastAPI()
    available = []
    processed = False

    @app.get("/jobs/{job_id}/output")
    async def output(job_id: int, start_line: int = 0):
        # Dedicated output endpoint: HTTP 200 means a successful read, not job success.
        return await awx.get_job_output(job_id, start_line=start_line, page_size=1)

    def status_response(request):
        return httpx.Response(
            200,
            json={
                "id": 42,
                "name": "linux",
                "status": "successful" if processed else "running",
                "event_processing_finished": processed,
            },
        )

    def event_response(request):
        cursor = int(request.url.params["start_line__gte"])
        remaining = [item for item in available if item["end_line"] > cursor]
        return httpx.Response(
            200,
            json={"results": remaining[:1], "next": "/next-page" if len(remaining) > 1 else None},
        )

    async def playbook():
        nonlocal processed
        for index, text in enumerate(
            ["TASK [Install packages]", "changed: [server-01]", "PLAY RECAP: failed=0"]
        ):
            await asyncio.sleep(0.01)
            available.append(
                {"id": index + 1, "start_line": index, "end_line": index + 1, "stdout": text}
            )
        processed = True

    printed = []
    producer = None
    try:
        with respx.mock:
            respx.get("https://awx.test/api/v2/jobs/42/").mock(side_effect=status_response)
            respx.get("https://awx.test/api/v2/jobs/42/job_events/").mock(
                side_effect=event_response
            )
            producer = asyncio.create_task(playbook())
            cursor = 0
            deadline = time.monotonic() + 10
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://linux-api"
            ) as dispatcher:
                while time.monotonic() < deadline:
                    response = await dispatcher.get(
                        "/jobs/42/output", params={"start_line": cursor}
                    )
                    response.raise_for_status()
                    body = response.json()
                    for line in body["stdout"].splitlines():
                        print(f"[AWX job=42] {line}", flush=True)
                        printed.append(line)
                    previous = cursor
                    cursor = body["next_line"]
                    if body["finished"]:
                        break
                    if body["has_more"] and cursor > previous:
                        continue  # Drain backlog without sleeping.
                    print("[Dispatcher] Sleeping; AWX continues producing output...", flush=True)
                    await asyncio.sleep(0.05)
                else:
                    raise TimeoutError("Output did not finish within the demo deadline")
            await producer
            assert cursor == 3 and len(printed) == len(set(printed)) == 3
    finally:
        if producer is not None and not producer.done():
            producer.cancel()
            await asyncio.gather(producer, return_exceptions=True)
        await awx.client.api.aclose()
    print("PASS: output added during sleep was printed once, including the final recap.")


if __name__ == "__main__":
    asyncio.run(main())
