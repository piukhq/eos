import logging

from django.conf import settings
from django.db import transaction

import rq
from app.agents.amex import MerchantRegApi
from redis import Redis

from mids.models import BatchItem, BatchItemAction, BatchItemStatus

logger = logging.getLogger(__name__)

redis = Redis.from_url(
    settings.REDIS_URL,
    socket_connect_timeout=3,
    socket_keepalive=True,
    retry_on_timeout=False,
)

task_queue = rq.Queue("amex", connection=redis)


def process_item(item_id: int) -> None:
    with transaction.atomic():
        try:
            item = BatchItem.objects.get(id=item_id, status=BatchItemStatus.QUEUED)
        except BatchItem.DoesNotExist:
            logger.warning("PENDING BatchItem ({}) does not exist".format(item_id))
            return

        api = MerchantRegApi()
        if item.action == BatchItemAction.ADD:
            response, request_timestamp = api.add_merchant(item.mid, item.merchant_slug, item.start_date, item.end_date)
        elif item.action == BatchItemAction.DELETE:
            response, request_timestamp = api.delete_merchant(item.mid, item.merchant_slug)
        else:
            logger.warning("Item with id {} has unrecognised action ({})item. Skipping...".format(item.id, item.action))
            item.status = BatchItemStatus.ERROR
            item.save(update_fields=["status"])
            return

        item.response = data = response.json()
        item.request_timestamp = request_timestamp
        if "error_code" in data:
            fields = ["error_code", "error_type", "error_description"]
            for f in fields:
                setattr(item, f, data[f])
            item.status = BatchItemStatus.ERROR
        else:
            fields = []
            item.status = BatchItemStatus.DONE
        item.save(update_fields=fields + ["status", "response", "request_timestamp"])
