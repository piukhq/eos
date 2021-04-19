import csv
import io
import logging
import typing as t
from datetime import date, datetime

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

from app import tasks
from mids.models import Batch, BatchItem, BatchItemAction, BatchItemStatus

logger = logging.getLogger(__name__)


class FileUploadForm(forms.Form):
    input_file = forms.FileField(
        label="Select MID batch file",
    )

    def clean_input_file(self) -> t.Any:
        file = self.cleaned_data["input_file"]
        if not file.name.lower().endswith(".csv"):
            raise forms.ValidationError(".csv files only")
        return file


def queue_batches(batches: QuerySet, user_name: str) -> t.Tuple[t.List[int], t.List[int]]:
    queued, errors = [], []
    for batch in batches:
        with transaction.atomic():
            batch.sender_name = user_name
            batch.date_sent = datetime.now()
            logger.info(f"Queuing items from batch {batch.file_name}")
            for item in batch.batchitem_set.select_for_update().filter(status=BatchItemStatus.PENDING):
                try:
                    tasks.task_queue.enqueue(tasks.process_item, item.id, retry=rq.Retry(max=1, interval=[10, 30, 60]))
                    queued.append(item.id)
                except RedisError:
                    errors.append(item.id)
            batch.batchitem_set.filter(id__in=queued).update(status=BatchItemStatus.QUEUED)
            batch.save()
        logger.info(f"Queued {len(queued)} items from batch {batch.file_name}")
    return queued, errors


def queue_batches_action(modeladmin: admin.ModelAdmin, request: HttpRequest, queryset: QuerySet) -> None:
    queued, errors = queue_batches(queryset, request.user.get_username())
    if queued:
        messages.info(request, "Queued {} items".format(len(queued)))
    else:
        messages.warning(request, "No items queued. Perhaps none in the batch were PENDING")
    if errors:
        messages.warning(request, "{} items were not queued due to an error with redis".format(len(errors)))


queue_batches_action.short_description = "Process batches"  # type:ignore


class TypedRow(t.TypedDict):
    mid: t.Optional[str]
    start_date: t.Optional[date]
    end_date: t.Optional[date]
    merchant_slug: t.Optional[str]
    provider_slug: t.Optional[str]
    action: t.Optional[BatchItemAction]


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ["batch_filter_link", "time_uploaded", "export_link", "processed", "sender_name", "date_sent"]
    fields = readonly_fields = ["file_name", "time_uploaded"]
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

    REQUIRED_COLUMNS = ["mid", "start_date", "end_date", "merchant_slug", "provider_slug", "action"]
    PROVIDERS = ["amex"]

    def validate_headers(
        self, request: HttpRequest, fieldnames: t.Set[str]
    ) -> t.Tuple[t.Optional[t.List], t.Optional[t.List]]:
        required_columns = set(self.REQUIRED_COLUMNS)
        extra = list(fieldnames - required_columns) or None
        missing = list(required_columns - fieldnames) or None
        return extra, missing

    def _validate_action(self, row: t.Dict[str, str], typed_row: TypedRow) -> t.List[str]:
        errors = []

        try:
            typed_row["action"] = BatchItemAction(row["action"].strip().upper())
        except ValueError:
            errors.append(f"Unrecognised action value: {row['action'].strip()}")
        else:
            if typed_row["action"] == BatchItemAction.ADD:
                for field in ("start_date", "end_date"):
                    try:
                        typed_row[field] = datetime.strptime(row[field].strip(), "%Y-%m-%d")  # type: ignore
                    except ValueError:
                        errors.append(f"Invalid {field}: {row[field].strip() or '<empty>'}")
            else:
                typed_row["start_date"] = typed_row["end_date"] = None
        return errors

    def _validate_row(self, row: t.Dict[str, str]) -> t.Tuple[t.Optional[TypedRow], t.List[str]]:
        errors = []
        if any(row.get(field) is None for field in self.REQUIRED_COLUMNS):
            errors.append("Missing row values")
            return None, errors

        typed_row = TypedRow(
            mid=row["mid"].strip(),
            start_date=None,
            end_date=None,
            merchant_slug=row["merchant_slug"].strip(),
            provider_slug=row["provider_slug"].strip(),
            action=None,
        )

        required_text_fields = ("mid", "merchant_slug", "provider_slug")
        for field in required_text_fields:
            if not typed_row[field]:  # type: ignore
                errors.append(f"Missing row value for field: {field}")
                return None, errors

        if typed_row["provider_slug"] not in self.PROVIDERS:
            errors.append(f"Invalid provider: {typed_row['provider_slug']}")

        errors.extend(self._validate_action(row, typed_row))
        if (
            typed_row["start_date"] is not None
            and typed_row["end_date"] is not None
            and typed_row["start_date"] >= typed_row["end_date"]
        ):
            errors.append(f"Start date ({row['start_date']}) >= end date ({row['end_date']})")
        return typed_row, errors

    def _process_rows(self, reader: csv.DictReader) -> t.Tuple[t.List[TypedRow], t.Dict[str, t.List[str]]]:
        errors = {}
        typed_rows: t.List[TypedRow] = []
        for row in reader:
            typed_row, row_errors = self._validate_row(row)
            if row_errors:
                errors[row["mid"]] = row_errors
            elif typed_row:
                typed_rows.append(typed_row)
        return typed_rows, errors

    def add_view(
        self, request: HttpRequest, form_url: str = "", extra_context: t.Optional[t.Dict] = None
    ) -> HttpResponse:
        errors = None
        if request.method == "POST":
            form = FileUploadForm(request.POST, request.FILES)
            if form.is_valid():
                file = request.FILES["input_file"]
                try:
                    reader = csv.DictReader(file.read().decode().splitlines())
                except UnicodeDecodeError:
                    messages.error(request, "Invalid file format")
                    return redirect(reverse("admin:mids_batch_add"))

                extra, missing = self.validate_headers(request, set(reader.fieldnames or []))
                if extra or missing:
                    messages.error(request, f"Required column headers: {', '.join(self.REQUIRED_COLUMNS)}")
                    return redirect(reverse("admin:mids_batch_add"))

                typed_rows, errors = self._process_rows(reader)

                if not errors:
                    with transaction.atomic():
                        batch = Batch.objects.create(file_name=file.name)
                        BatchItem.objects.bulk_create(
                            [BatchItem(batch=batch, status=BatchItemStatus.PENDING, **row) for row in typed_rows]
                        )

                    messages.success(request, "Batch imported")
                    return redirect(reverse("admin:mids_batch_changelist"))
                else:
                    messages.error(request, "Invalid file contents. Please see below")
        else:
            form = FileUploadForm()
        return TemplateResponse(
            request,
            "admin/upload.html",
            {"form": form, "file_errors": errors, "title": "Upload batch", "site_header": settings.SITE_HEADER},
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
        "error_code",
        "error_type",
        "error_description",
        "action",
        "created",
        "updated",
        "request_timestamp",
        "response",
    ]
    list_filter = ["status", "error_type", "action", "merchant_slug"]
    search_fields = ["mid"]
    raw_id_fields = ["batch"]
    fields = readonly_fields = list_display

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).select_related("batch")

    def batch_file_name(self, obj: BatchItem) -> str:
        return obj.batch.file_name
