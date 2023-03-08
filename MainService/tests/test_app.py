# import pytest
# from app import app
#
#
# @pytest.fixture
# def client():
#     app.config['TESTING'] = True
#     with app.test_client() as client:
#         yield client


# def test_homepage(client):
#     response = client.get('/')
#     assert response.status_code == 200
#     assert b"Welcome to my app" in response.data

# import unittest
# import pytest
#
#
# class MyTestCase(unittest.TestCase):
#     def test_something(self):
#         self.assertEqual(True, False)  # add assertion here
#
#
# if __name__ == '__main__':
#     unittest.main()
