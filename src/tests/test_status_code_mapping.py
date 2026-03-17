from ..tashtiot_apis_library.status_code_mappings import status_code_mapping


def test_status_code_mapping_values():
        assert status_code_mapping["successful"] == 200
        assert status_code_mapping["failed"] == 500
        assert status_code_mapping["running"] == 202
        assert status_code_mapping["pending"] == 202
        assert status_code_mapping["canceled"] == 500
        assert status_code_mapping["waiting"] == 202
