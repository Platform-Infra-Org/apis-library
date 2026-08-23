"""AWX status-HTTP-code mappings.

Maps AWX job status values to the appropriate HTTP status codes that
consumers should return in their API responses. Used by status endpoints.
Launch endpoints always return status="successful" and status_code=200
(the AWX launch HTTP response code), matching the original API behavior.
"""

status_code_mapping = {
    "successful": 200,
    "running": 202,
    "pending": 202,
    "waiting": 202,
    "failed": 500,
    "error": 500,
    "canceled": 500,
}
