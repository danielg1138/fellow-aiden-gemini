import unittest
import json
from unittest.mock import patch, MagicMock
from fellow_aiden import FellowAiden

class TestFellowAiden(unittest.TestCase):

    def setUp(self):
        self.email = "test@example.com"
        self.password = "password"

    @patch.object(FellowAiden, 'SESSION')
    def test_authentication_success(self, mock_session):
        mock_auth_res = MagicMock()
        mock_auth_res.content = json.dumps({
            'accessToken': 'test_access_token',
            'refreshToken': 'test_refresh_token'
        }).encode('utf-8')
        mock_device_res = MagicMock()
        mock_device_res.content = json.dumps([{
            'id': 'test_brewer_id',
            'profiles': [],
            'displayName': 'Test Brewer'
        }]).encode('utf-8')
        mock_session.post.return_value = mock_auth_res
        mock_session.get.return_value = mock_device_res

        aiden = FellowAiden(self.email, self.password)
        self.assertTrue(aiden._auth)
        self.assertEqual(aiden._token, 'test_access_token')

    @patch.object(FellowAiden, 'SESSION')
    def test_device_fetch_success(self, mock_session):
        mock_auth_res = MagicMock()
        mock_auth_res.content = json.dumps({
            'accessToken': 'test_access_token',
            'refreshToken': 'test_refresh_token'
        }).encode('utf-8')

        mock_device_res = MagicMock()
        mock_device_res.content = json.dumps([{
            'id': 'test_brewer_id',
            'profiles': [],
            'displayName': 'Test Brewer'
        }]).encode('utf-8')

        mock_session.post.return_value = mock_auth_res
        mock_session.get.return_value = mock_device_res

        aiden = FellowAiden(self.email, self.password)
        self.assertEqual(aiden._brewer_id, 'test_brewer_id')
        self.assertEqual(aiden.get_display_name(), 'Test Brewer')

    @patch.object(FellowAiden, 'SESSION')
    def test_create_profile_success(self, mock_session):
        mock_auth_res = MagicMock()
        mock_auth_res.content = json.dumps({
            'accessToken': 'test_access_token',
            'refreshToken': 'test_refresh_token'
        }).encode('utf-8')

        mock_device_res = MagicMock()
        mock_device_res.content = json.dumps([{
            'id': 'test_brewer_id',
            'profiles': [{'id': 'test_profile_id', 'title': 'Test Profile'}],
            'displayName': 'Test Brewer'
        }]).encode('utf-8')

        mock_create_res = MagicMock()
        mock_create_res.content = json.dumps({'id': 'test_profile_id'}).encode('utf-8')

        mock_session.post.side_effect = [mock_auth_res, mock_create_res]
        mock_session.get.return_value = mock_device_res

        aiden = FellowAiden(self.email, self.password)
        data = {
            "profileType": 0,
            "title": "Test Profile",
            "ratio": 16,
            "bloomEnabled": True,
            "bloomRatio": 2,
            "bloomDuration": 30,
            "bloomTemperature": 96,
            "ssPulsesEnabled": True,
            "ssPulsesNumber": 3,
            "ssPulsesInterval": 23,
            "ssPulseTemperatures": [96, 97, 98],
            "batchPulsesEnabled": True,
            "batchPulsesNumber": 2,
            "batchPulsesInterval": 30,
            "batchPulseTemperatures": [96, 97]
        }
        res = aiden.create_profile(data)
        self.assertEqual(res, {'id': 'test_profile_id'})

    @patch.object(FellowAiden, 'SESSION')
    def test_delete_profile_success(self, mock_session):
        mock_auth_res = MagicMock()
        mock_auth_res.content = json.dumps({
            'accessToken': 'test_access_token',
            'refreshToken': 'test_refresh_token'
        }).encode('utf-8')

        mock_device_res = MagicMock()
        mock_device_res.content = json.dumps([{
            'id': 'test_brewer_id',
            'profiles': [],
            'displayName': 'Test Brewer'
        }]).encode('utf-8')

        mock_session.post.return_value = mock_auth_res
        mock_session.get.return_value = mock_device_res

        aiden = FellowAiden(self.email, self.password)
        aiden._profiles = [{'id': 'test_profile_id'}]
        aiden.delete_profile_by_id('test_profile_id')
        mock_session.delete.assert_called_once()

if __name__ == '__main__':
    unittest.main()

