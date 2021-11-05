import json
import uuid
from datetime import date, timedelta
from unittest import mock

import responses
from django.test import TestCase, override_settings

from app.agents.amex import BASE_URI, MerchantRegApi

AMEX_API_HOST = "http://localhost"
AMEX_CLIENT_SECRET = "shhhhhh"
AMEX_CLIENT_ID = "client-id"


@override_settings(AMEX_API_HOST=AMEX_API_HOST, AMEX_CLIENT_SECRET=AMEX_CLIENT_SECRET, AMEX_CLIENT_ID=AMEX_CLIENT_ID)
class TestAmexAgent(TestCase):
    def setUp(self) -> None:
        self.amex = MerchantRegApi()
        self.mid = "4548436161"

    @mock.patch("uuid.uuid4", new=lambda: uuid.UUID("{12345678-1234-5678-1234-567812345678}"))
    @mock.patch("time.time", new=lambda: 1613218482.810827)
    def test__make_headers(self) -> None:
        headers = MerchantRegApi()._make_headers("POST", "/a/test/uri", '{"payload": "data"}')
        self.assertEqual(
            headers,
            {
                "Content-Type": "application/json",
                "X-AMEX-API-KEY": "client-id",
                "Authorization": 'MAC id="client-id",ts="1613218482811",'
                'nonce="12345678-1234-5678-1234-567812345678",'
                'bodyhash="17q3v+i090m9dz29fi4AOMGa0SLL5G6WP3cnoe3MXt8=",'
                'mac="jUSmdKGuA85BJ8TQZzXIcxSdImaOHaqIn0v5Ipdm7sU="',
            },
        )

    @mock.patch("uuid.uuid4", new=lambda: uuid.UUID("{12345678-1234-5678-1234-567812345678}"))
    @responses.activate
    def test_add_merchant(self) -> None:
        responses.add(
            responses.POST,
            AMEX_API_HOST + BASE_URI,
            json={
                "merchantId": self.mid,
                "merchantName": "wasabi-club",
                "merchantSubmTypeCd": "B",
                "merchantAdLine1": "30 LAVENDER DR",
                "merchantAdLine2": "",
                "merchantAdLine3": "",
                "merchantAdLine4": "",
                "merchantAdLine5": "",
                "merchantAdRgnAreaCd": "NJ",
                "merchantAdRgnAreaNm": "NEW JERSEY",
                "merchantAdPostTownNm": "SEWELL",
                "merchantAdPostlCd": "08080",
                "merchantAdCtryNm": "US",
                "merchantPhoneNo": "2158035154",
                "correlationId": "e204f94c-f3a8-4e07-956a-88ae817535f0",
            },
            status=200,
            content_type="application/json",
        )
        today = date.today()
        tomorrow = today + timedelta(days=1)
        response, _ = self.amex.add_merchant(self.mid, "wasabi-club", today, tomorrow)
        self.assertTrue("X-AMEX-API-KEY" in response.request.headers)
        self.assertTrue("Authorization" in response.request.headers)
        self.assertEqual(
            json.loads(response.request.body or ""),
            {
                "APIVersion": "5.0",
                "merchantType": "nonoffer",
                "partnerId": "AADP0050",
                "msgId": "12345678-1234-5678-1234-567812345678",
                "actionCode": "A",
                "merchantId": self.mid,
                "partnerMerchantRefId": "wasabi-club",
                # "sellerId": "",
                # "submittingSe": "",
                "merchantStartDt": today.strftime("%m/%d/%Y"),
                "merchantEndDt": tomorrow.strftime("%m/%d/%Y"),
                # "offerId": "",
            },
        )

    @mock.patch("uuid.uuid4", new=lambda: uuid.UUID("{12345678-1234-5678-1234-567812345678}"))
    @responses.activate
    def test_delete_merchant(self) -> None:
        responses.add(
            responses.DELETE,
            AMEX_API_HOST + BASE_URI + f"/{self.mid}",
            json={"correlationId": "52b0666f-3dfa-4e8f-b16f-d6737aa3efe8", "merchantId": self.mid},
            status=200,
            content_type="application/json",
        )
        response, _ = self.amex.delete_merchant(self.mid, "wasabi-club")
        self.assertTrue("X-AMEX-API-KEY" in response.request.headers)
        self.assertTrue("Authorization" in response.request.headers)
        self.assertEqual(
            json.loads(response.request.body or ""),
            {
                "APIVersion": "5.0",
                "merchantType": "nonoffer",
                "partnerId": "AADP0050",
                "msgId": "12345678-1234-5678-1234-567812345678",
                "actionCode": "D",
                "merchantId": self.mid,
                "partnerMerchantRefId": "wasabi-club",
            },
        )
