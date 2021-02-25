from django.test import Client, TestCase
from django.urls import reverse


class TestAppViews(TestCase):
    def test_livez(self) -> None:
        # for the sake of coverage alone
        response = Client().get(reverse("livez"))
        self.assertEqual(204, response.status_code)
        self.assertEqual(b"", response.content)
