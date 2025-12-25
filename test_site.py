import unittest
import requests

class WebSiteTest(unittest.TestCase):
    def test_google_access(self):
        """구글 접속 테스트: 상태 코드가 200이어야 함"""
        print(">> [Test] 구글 접속 시도 중...")
        response = requests.get("https://www.google.com")
        self.assertEqual(response.status_code, 200)

    def test_github_access(self):
        """깃허브 접속 테스트: 상태 코드가 200이어야 함"""
        print(">> [Test] 깃허브 접속 시도 중...")
        response = requests.get("https://www.github.com")
        self.assertEqual(response.status_code, 200)