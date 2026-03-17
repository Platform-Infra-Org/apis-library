import pytest
from ..tashtiot_apis_library.connectors.awx.models import MetadataRequest, OperationRequest, OperationResponse, AWXOperationResponse, TerraformOperationResponse

def test_metadata_request():
    metadata_request = MetadataRequest(project="test_project", network="test_network", region="test_region", space="test_space", environment="test_env")
    assert metadata_request.project == "test_project"
    assert metadata_request.network == "test_network"
    assert metadata_request.region == "test_region"
    assert metadata_request.space == "test_space"
    assert metadata_request.environment == "test_env"
    assert metadata_request.island is None

def test_metadata_request_with_optional_fields():
    metadata_request = MetadataRequest(project="test_project", network="test_network", region="test_region", space="test_space", island="test_island", environment="test_env")
    assert metadata_request.project == "test_project"
    assert metadata_request.network == "test_network"
    assert metadata_request.region == "test_region"
    assert metadata_request.space == "test_space"
    assert metadata_request.island == "test_island"
    assert metadata_request.environment == "test_env"

def test_operation_request():
    metadata_request = MetadataRequest(project="test_project", network="test_network", region="test_region", space="test_space", environment="test_env")
    operation_request = OperationRequest(metadata=metadata_request)
    assert operation_request.metadata == metadata_request

def test_operation_response():
    operation_response = OperationResponse(status="success", status_code=200, stdout="test_stdout")
    assert operation_response.status == "success"
    assert operation_response.status_code == 200
    assert operation_response.stdout == "test_stdout"

def test_awx_operation_response():
    awx_operation_response = AWXOperationResponse(status="success", status_code=200, stdout="test_stdout", job_id=123)
    assert awx_operation_response.status == "success"
    assert awx_operation_response.status_code == 200
    assert awx_operation_response.stdout == "test_stdout"
    assert awx_operation_response.job_id == 123

def test_terraform_operation_response():
    terraform_operation_response = TerraformOperationResponse(status="success", status_code=200, stdout="test_stdout", process_id=123)
    assert terraform_operation_response.status == "success"
    assert terraform_operation_response.status_code == 200
    assert terraform_operation_response.stdout == "test_stdout"
    assert terraform_operation_response.process_id == 123