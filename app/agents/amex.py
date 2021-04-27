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
from azure.core.exceptions import ServiceRequestError
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
from tempfile import NamedTemporaryFile

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

    def _write_tmp_files(self, key: str, cert: str) -> t.Tuple[str, ...]:
        paths = []
        for data in (key, cert):
            file = NamedTemporaryFile(delete=False)
            paths.append(file.name)
            file.write(data.encode())
            file.close()
        return tuple(paths)

    def client_id_and_secret(self) -> t.Tuple[str, str]:
        if settings.TESTING or settings.TEST_RUNNER_SET:
            client_id = settings.AMEX_CLIENT_ID
            client_secret = settings.AMEX_CLIENT_SECRET
        else:
            client = self.connect_to_vault()
            client_id = json.loads(client.get_secret("amex-clientId").value)["value"]
            client_secret = json.loads(client.get_secret("amex-clientSecret").value)["value"]
        return client_id, client_secret

    def _make_headers(self, httpmethod: str, resource_uri: str, payload: str) -> dict:
        current_time_ms = str(round(time.time() * 1000))
        nonce = str(uuid.uuid4())
        client_id, client_secret = self.client_id_and_secret()

        bodyhash = base64.b64encode(
            hmac.new(client_secret.encode(), payload.encode(), digestmod=hashlib.sha256).digest()
        ).decode()

        hash_key_secret = (
            f"{current_time_ms}\n{nonce}\n{httpmethod.upper()}\n"
            f"{resource_uri}\n{urlsplit(settings.AMEX_API_HOST).netloc}\n443\n{bodyhash}\n"
        )
        mac = base64.b64encode(
            hmac.new(client_secret.encode(), hash_key_secret.encode(), digestmod=hashlib.sha256).digest()
        ).decode()

        return {
            "Content-Type": "application/json",
            "X-AMEX-API-KEY": client_id,
            "Authorization": f'MAC id="{client_id}",ts="{current_time_ms}"'
            f',nonce="{nonce}",bodyhash="{bodyhash}",mac="{mac}"',
        }

    def _call_api(
        self, method: str, resource_uri: str, data: dict = None
    ) -> t.Tuple[requests.Response, datetime.datetime]:
        client = self.connect_to_vault()
        client_cert_path = None
        client_priv_path = None
        try:
            client_priv_path, client_cert_path = self._write_tmp_files(
                json.loads(client.get_secret("amex-cert").value)["key"],
                json.loads(client.get_secret("amex-cert").value)["cert"],
            )
        except ServiceRequestError:
            logger.error("Could not retrieve cert/key data from vault")
        payload = json.dumps(data)
        headers = self._make_headers(method, resource_uri, payload)
        timestamp = timezone.now()
        response = getattr(self.session, method.lower())(
            settings.AMEX_API_HOST + resource_uri,
            cert=(client_cert_path, client_priv_path),
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

    def connect_to_vault(self) -> SecretClient:
        if settings.KEY_VAULT is None:
            raise Exception("Vault Error: settings.KEY_VAULT not set")

        return SecretClient(vault_url=settings.KEY_VAULT, credential=DefaultAzureCredential())
