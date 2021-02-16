import csv
import io
import logging
import typing as t

import rq

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.db import transaction
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.urls.resolvers import URLPattern
from django.utils.html import format_html
from django.utils.http import urlencode
from django.utils.safestring import SafeText
from redis.exceptions import RedisError

from eos import tasks
from mids.models import Batch, BatchItem, BatchItemAction, BatchItemStatus

logger = logging.getLogger(__name__)


class FileUploadForm(forms.Form):
    instance = None
    input_file = forms.FileField(
        label="Select MID batch file",
    )


def queue_batches(batches: QuerySet) -> t.Tuple[t.List[int], t.List[int]]:
    queued, errors = [], []
    for batch in batches:
        with transaction.atomic():
            logger.info(f"Queuing items from batch {batch.file_name}")
            for item in batch.batchitem_set.select_for_update().filter(status=BatchItemStatus.PENDING):
                try:
                    tasks.task_queue.enqueue(tasks.process_item, item.id, retry=rq.Retry(max=1, interval=[10, 30, 60]))
                    queued.append(item.id)
                except RedisError:
                    errors.append(item.id)
            batch.batchitem_set.filter(id__in=queued).update(status=BatchItemStatus.QUEUED)
        logger.info(f"Queued {len(queued)} items from batch {batch.file_name}")
    return queued, errors


def queue_batches_action(modeladmin: admin.ModelAdmin, request: HttpRequest, queryset: QuerySet) -> None:
    queued, errors = queue_batches(queryset)
    if queued:
        messages.info(request, "Queued {} items".format(len(queued)))
    else:
        messages.warning(request, "No items queued. Perhaps none in the batch were PENDING")
    if errors:
        messages.warning(request, "{} items were not queued due to an error with redis".format(len(errors)))


queue_batches_action.short_description = "Process batches"  # type:ignore


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ["batch_filter_link", "time_uploaded", "export_link", "processed"]
    fields = ["input_file"]
    actions = [queue_batches_action]

    # def user_email(self, obj: Batch) -> str:
    # return obj.user.email

    def get_urls(self) -> t.List[URLPattern]:
        return [
            path("<int:batch_id>/export/", admin.site.admin_view(self.export_as_csv), name="export_as_csv")
        ] + super().get_urls()

    def export_as_csv(self, request: HttpRequest, batch_id: int) -> StreamingHttpResponse:
        field_names = [
            "mid",
            "start_date",
            "end_date",
            "merchant_slug",
            "provider_slug",
            "status",
            "action",
            "created",
            "updated",
            "error_code",
            "error_type",
            "error_description",
        ]
        dt_format = "%d/%m/%Y %H:%M:%S"
        conv_map = {
            "status": lambda item, field: BatchItemStatus(getattr(item, field)).label,
            "action": lambda item, field: BatchItemAction(getattr(item, field)).label,
            "created": lambda item, field: getattr(item, field).strftime(dt_format),
            "updated": lambda item, field: getattr(item, field).strftime(dt_format),
        }

        def stream() -> t.Generator[str, None, None]:
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["batch_file_name"] + field_names)
            batch = Batch.objects.prefetch_related("batchitem_set").get(id=batch_id)
            for item in batch.batchitem_set.all():
                writer.writerow(
                    [batch.file_name] + [conv_map.get(field, getattr)(item, field) for field in field_names]
                )
                buffer.seek(0)
                data = buffer.read()
                buffer.seek(0)
                buffer.truncate()
                yield data

        response = StreamingHttpResponse(stream(), content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=mid_export.csv"
        return response

    def processed(self, obj: Batch) -> bool:
        return (
            not BatchItem.objects.filter(batch__id=obj.id)
            .filter(status__in=(BatchItemStatus.PENDING, BatchItemStatus.QUEUED))
            .exists()
        )

    processed.boolean = True  # type:ignore

    def batch_filter_link(self, obj: Batch) -> SafeText:
        url = reverse("admin:mids_batchitem_changelist") + "?" + urlencode({"batch__id": f"{obj.id}"})
        return format_html('<a href="{}">{}</a>', url, obj.file_name)

    def export_link(self, obj: Batch) -> SafeText:
        url = reverse("admin:export_as_csv", args=[obj.id])
        return format_html('<a href="{}">Export</a>', url)

    ACTION_MAP = {"A": BatchItemAction.ADD, "D": BatchItemAction.DELETE}

    def add_view(
        self, request: HttpRequest, form_url: str = "", extra_context: t.Optional[t.Dict] = None
    ) -> HttpResponse:
        if request.method == "POST":
            form = FileUploadForm(request.POST, request.FILES)
            # mid,start_date,end_date,merchant_slug,provider_slug,action
            # 12345,2021-01-01,2999-12-31,wasabi-club,amex,A
            if form.is_valid():
                with transaction.atomic():
                    file = request.FILES["input_file"]
                    reader = csv.DictReader(file.read().decode().splitlines())
                    batch = Batch.objects.create(file_name=file.name)
                    BatchItem.objects.bulk_create(
                        [
                            BatchItem(
                                batch=batch,
                                mid=row["mid"],
                                start_date=row["start_date"],
                                end_date=row["end_date"],
                                merchant_slug=row["merchant_slug"],
                                provider_slug=row["provider_slug"],
                                action=self.ACTION_MAP[row["action"].upper()],
                                status=BatchItemStatus.PENDING,
                            )
                            for row in reader
                        ]
                    )

                messages.success(request, "Batch imported")
                return redirect(reverse("admin:mids_batch_changelist"))
        else:
            form = FileUploadForm()
        return TemplateResponse(
            request, "admin/upload.html", {"form": form, "title": "Upload batch", "site_header": settings.SITE_HEADER}
        )


@admin.register(BatchItem)
class BatchItemAdmin(admin.ModelAdmin):
    list_display = [
        "batch_file_name",
        "mid",
        "start_date",
        "end_date",
        "merchant_slug",
        "provider_slug",
        "status",
        "error_type",
        "action",
        "created",
        "updated",
    ]
    list_filter = ["status", "error_type", "action", "merchant_slug"]
    search_fields = ["mid"]
    raw_id_fields = ["batch"]

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).select_related("batch")

    def batch_file_name(self, obj: BatchItem) -> str:
        return obj.batch.file_name
