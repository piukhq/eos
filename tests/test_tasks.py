from datetime import date
from unittest import mock

import responses
from django.test import TestCase, override_settings
from django.utils import timezone

from app import tasks
from mids.models import Batch, BatchItem, BatchItemAction, BatchItemStatus

AMEX_API_HOST = "http://localhost"
AMEX_CLIENT_SECRET = "shhhh"
AMEX_CLIENT_ID = "client_id"


@override_settings(AMEX_API_HOST=AMEX_API_HOST, AMEX_CLIENT_SECRET=AMEX_CLIENT_SECRET, AMEX_CLIENT_ID=AMEX_CLIENT_ID)
class TestTasks(TestCase):
    def setUp(self) -> None:
        self.batch = Batch.objects.create(file_name="mids.csv")
        self.start = date(2021, 2, 15)
        self.end = date(2021, 2, 16)
        self.item = BatchItem.objects.create(
            batch=self.batch,
            mid="123456789",
            start_date=self.start,
            end_date=self.end,
            merchant_slug="wasabi-club",
            provider_slug="amex",
            action=BatchItemAction.ADD,
            status=BatchItemStatus.QUEUED,
        )

    @responses.activate
    def test_process_item_not_status_queued(self) -> None:
        BatchItem.objects.filter(id=self.item.id).update(status=BatchItemStatus.PENDING)
        with mock.patch("app.tasks.MerchantRegApi") as mock_amex:
            tasks.process_item(self.item.id)
            mock_amex.add_merchant.assert_not_called()

    class MockResponse:
        def __init__(self, json: dict) -> None:
            self._json = json

        def json(self) -> dict:
            return self._json

    def test_process_item(self) -> None:
        with mock.patch("app.tasks.MerchantRegApi") as mock_api_cls:
            mock_api = mock_api_cls.return_value
            mock_api.add_merchant.return_value = (self.MockResponse({"some": "json"}), timezone.now())
            tasks.process_item(self.item.id)
            mock_api.add_merchant.assert_called_with("123456789", "wasabi-club", self.start, self.end)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, BatchItemStatus.DONE)
        self.assertEqual(self.item.response, {"some": "json"})

    def test_process_item_error(self) -> None:
        with mock.patch("app.tasks.MerchantRegApi") as mock_api_cls:
            mock_api = mock_api_cls.return_value
            canned_json = {
                "error_code": "1040012",
                "error_type": "Invalid request",
                "error_description": "Merchant ID already registered, updated, or deleted.",
                "correlationId": "5bd5af1f-c456-4edd-8ec6-ec33a5d0f731",
            }
            mock_api.add_merchant.return_value = (
                self.MockResponse(canned_json),
                timezone.now(),
            )
            tasks.process_item(self.item.id)
            mock_api.add_merchant.assert_called_with("123456789", "wasabi-club", self.start, self.end)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, BatchItemStatus.ERROR)
        self.assertEqual(self.item.error_code, "1040012")
        self.assertEqual(self.item.error_type, "Invalid request")
        self.assertEqual(self.item.error_description, "Merchant ID already registered, updated, or deleted.")
