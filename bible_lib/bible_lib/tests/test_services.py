from unittest import TestCase

from bible_lib.services import Services


class TestServices(TestCase):
    def test_single_api_client(self):
        """" Because we do not want every new client to begin its own cache
        and disrupt other caches, the services to let every one who wants
        to share a client."""
        cache_api_1 = Services().api_client
        cache_api_2 = Services().api_client

        cache_api_1.temp_var = 1
        cache_api_2.temp_var = 2

        self.assertEqual(cache_api_1.temp_var, cache_api_2.temp_var)
