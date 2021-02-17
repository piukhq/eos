import base64
import datetime
import hashlib
import hmac
import json
import logging
import time
import typing as t
import uuid

import requests

from django.conf import settings
from django.utils import timezone

from requests.adapters import HTTPAdapter
from urllib.parse import urlsplit
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class RetryAdapter(HTTPAdapter):
    def __init__(self, *args: t.List[t.Any], **kwargs: t.Dict[t.Any, t.Any]) -> None:
        retries: int = 3
        status_forcelist: t.Tuple = (500, 503, 504)
        retry = Retry(
            total=3,
            read=3,
            connect=retries,
            backoff_factor=0.3,
            status_forcelist=status_forcelist,
            raise_on_status=False,
        )
        kwargs["max_retries"] = retry
        super().__init__(*args, **kwargs)


BASE_URI = "/marketing/v4/smartoffers/offers/merchants"


class MerchantRegApi:
    COMMON_PARAMS = {
        "APIVersion": "5.0",
        "merchantType": "nonoffer",
        "partnerId": "AADP0050",
    }
    DATE_FORMAT = "%m/%d/%Y"

    def __init__(self, *args: t.List[t.Any], **kwargs: t.Dict[str, t.Any]) -> None:
        self.session = requests.Session()
        self.session.mount(settings.AMEX_API_HOST, RetryAdapter())

    @staticmethod
    def _make_headers(httpmethod: str, resource_uri: str, payload: str) -> dict:
        current_time_ms = str(round(time.time() * 1000))
        nonce = str(uuid.uuid4())

        bodyhash = base64.b64encode(
            hmac.new(settings.AMEX_CLIENT_SECRET.encode(), payload.encode(), digestmod=hashlib.sha256).digest()
        ).decode()

        hash_key_secret = (
            f"{current_time_ms}\n{nonce}\n{httpmethod.upper()}\n"
            f"{resource_uri}\n{urlsplit(settings.AMEX_API_HOST).netloc}\n443\n{bodyhash}\n"
        )
        mac = base64.b64encode(
            hmac.new(settings.AMEX_CLIENT_SECRET.encode(), hash_key_secret.encode(), digestmod=hashlib.sha256).digest()
        ).decode()

        return {
            "Content-Type": "application/json",
            "X-AMEX-API-KEY": settings.AMEX_CLIENT_ID,
            "Authorization": f'MAC id="{settings.AMEX_CLIENT_ID}",ts="{current_time_ms}"'
            f',nonce="{nonce}",bodyhash="{bodyhash}",mac="{mac}"',
        }

    def _call_api(
        self, method: str, resource_uri: str, data: dict = None
    ) -> t.Tuple[requests.Response, datetime.datetime]:
        payload = json.dumps(data)
        headers = self._make_headers(method, resource_uri, payload)
        timestamp = timezone.now()
        response = getattr(self.session, method.lower())(
            settings.AMEX_API_HOST + resource_uri,
            cert=(settings.AMEX_CLIENT_CERT_PATH, settings.AMEX_CLIENT_PRIV_KEY_PATH),
            headers=headers,
            data=payload,
            timeout=(3.05, 10),
        )
        return response, timestamp

    def add_merchant(
        self, mid: str, merchant_slug: str, start_date: datetime.date, end_date: datetime.date
    ) -> t.Tuple[requests.Response, datetime.datetime]:
        data = self.COMMON_PARAMS.copy()
        data.update(
            {
                "msgId": str(uuid.uuid4()),
                "actionCode": "A",
                "merchantId": mid,
                "partnerMerchantRefId": merchant_slug,
                # "sellerId": "",
                # "submittingSe": "",
                "merchantStartDt": start_date.strftime(self.DATE_FORMAT),
                "merchantEndDt": end_date.strftime(self.DATE_FORMAT),
                # "offerId": "",
            }
        )
        return self._call_api("POST", BASE_URI, data)

    def delete_merchant(self, mid: str, merchant_slug: str) -> t.Tuple[requests.Response, datetime.datetime]:
        data = self.COMMON_PARAMS.copy()
        data.update(
            {
                "msgId": str(uuid.uuid4()),
                "actionCode": "D",
                "merchantId": mid,
                "partnerMerchantRefId": merchant_slug,
            }
        )
        return self._call_api("DELETE", f"{BASE_URI}/{mid}", data)
