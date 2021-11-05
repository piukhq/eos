import logging
import typing as t

import rq
from django.core.management.base import BaseCommand

from app.tasks import redis, task_queue

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Consume MID on/off-boarding tasks from the queue"

    def handle(self, *args: t.List[t.Any], **options: t.Dict[str, t.Any]) -> None:
        logger.info(f"Watching queue: {task_queue.name}")
        try:
            worker = rq.Worker([task_queue], connection=redis)
            worker.work()
        except KeyboardInterrupt:
            logger.info("Shutting down.")
