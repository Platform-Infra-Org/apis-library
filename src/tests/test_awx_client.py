import unittest
from unittest.mock import patch, Mock
from ..tashtiot_apis_library.connectors.awx.service import AWX
import requests
from ..tashtiot_apis_library.connectors.awx.models import AWXOperationResponse

awx_client = AWX("https://example.com", "token")

class TestAWXOperations(unittest.TestCase):

    def setUp(self):
        self.base_url = "https://example.com"
        self.token = "token"
        self.job_template_id = 1
        self.extra_vars = {"key": "value"}
        self.job_id = 1

    @patch('requests.post')
    def test_launch_job(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {"url": "/job/1", "job": 123}
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        response = awx_client.launch_job(self.job_template_id, self.extra_vars)

        self.assertEqual(response.status, "successful")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.stdout, f"{self.base_url}/job/1")
        self.assertEqual(response.job_id, 123)

    @patch('requests.post')
    def test_launch_job_failure(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {"error": "error"}
        mock_response.status_code = 404
        mock_post.return_value = mock_response
        with self.assertRaises(Exception):
            launch_job(self.job_template_id, self.extra_vars, self.logger, self.base_url, self.token)

    @patch('requests.get')
    def test_get_job_status(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {"status": "successful"}
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        response = awx_client.get_job_status(self.job_id)
        self.assertEqual(response.status, "successful")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.stdout, f"{self.base_url}/api/v2/jobs/{self.job_id}/stdout")
        self.assertEqual(response.job_id, self.job_id)

    @patch('requests.get')
    def test_get_job_status_failure(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {"error": "error"}
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        with self.assertRaises(Exception):
            get_job_status(self.job_id, self.base_url, self.token)

if __name__ == '__main__':
    unittest.main()