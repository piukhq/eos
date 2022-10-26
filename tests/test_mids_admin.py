from datetime import date

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http.response import HttpResponse
from django.test import Client, TestCase
from django.urls import reverse

from app.tasks import task_queue
from mids.models import Batch, BatchItem, BatchItemAction, BatchItemStatus


class TestMidsAdmin(TestCase):
    def setUp(self) -> None:
        User.objects.create_superuser("admin", "admin@bink.com", "!Potato12345!")
        self.client = Client()

    def upload_file(self, file_content: bytes, file_name: str = "mids.csv") -> HttpResponse:
        batch_file = SimpleUploadedFile(file_name, file_content, content_type="text/csv")
        self.client.login(username="admin", password="!Potato12345!")
        response = self.client.post(reverse("admin:mids_batch_add"), {"input_file": batch_file}, follow=True)
        return response  # type: ignore

    def test_file_ext(self) -> None:
        file_content = b"""mid,start_date,end_date,merchant_slug,provider_slug,action
4548436161,2021-01-01,2999-12-31,bink_test_merchant,amex,a
"""
        response = self.upload_file(file_content, file_name="mids.junk")
        self.assertContains(response, ".csv files only")
        self.assertEqual(0, BatchItem.objects.count())

    def test_upload(self) -> None:
        file_content = b"""mid,start_date,end_date,merchant_slug,provider_slug,action
4548436161,2021-01-01,2999-12-31,bink_test_merchant,amex,a
9999999999,2021-01-01,2999-12-31,bink_test_merchant,amex,a
"""
        response = self.upload_file(file_content)
        self.assertContains(response, "Batch imported")
        self.assertEqual(1, Batch.objects.count())
        batch = Batch.objects.get()
        self.assertEqual("mids.csv", batch.file_name)
        self.assertEqual(2, BatchItem.objects.filter(status=BatchItemStatus.PENDING).count())

    def test_upload_wrong_format(self) -> None:
        file_content = b"""mid,start_date,end_date,merchant_slug,provider_slug,action
4548436161,2021-01-01
"""
        response = self.upload_file(file_content)
        self.assertContains(response, "Missing row values")
        self.assertEqual(0, BatchItem.objects.count())

    def test_csv_validation_invalid_dates_action_delete(self) -> None:
        file_content = b"""mid,start_date,end_date,merchant_slug,provider_slug,action
4548436161,,,bink_test_merchant,amex,d
4548436162,JUNK,JUNK,bink_test_merchant,amex,d
"""
        self.assertEqual(0, BatchItem.objects.count())
        response = self.upload_file(file_content)
        self.assertContains(response, "Batch imported")
        self.assertEqual(2, BatchItem.objects.count())

    def test_csv_validation_invalid_dates_action_add(self) -> None:
        file_content = b"""mid,start_date,end_date,merchant_slug,provider_slug,action
4548436161,,,bink_test_merchant,amex,a
4548436162,JUNK,JUNK,bink_test_merchant,amex,a
"""
        response = self.upload_file(file_content)
        self.assertContains(response, "Invalid start_date: &lt;empty&gt;")
        self.assertContains(response, "Invalid end_date: &lt;empty&gt;")
        self.assertContains(response, "Invalid start_date: JUNK")
        self.assertContains(response, "Invalid end_date: JUNK")
        self.assertEqual(0, BatchItem.objects.count())

    def test_csv_validation_start_date_after_end_date_add(self) -> None:
        file_content = b"""mid,start_date,end_date,merchant_slug,provider_slug,action
4548436161,2021-12-31,2020-12-31,bink_test_merchant,amex,a
"""
        response = self.upload_file(file_content)
        self.assertContains(response, "Start date (2021-12-31) &gt;= end date (2020-12-31)")
        self.assertEqual(0, BatchItem.objects.count())

    def test_csv_validation_provider_not_amex(self) -> None:
        file_content = b"""mid,start_date,end_date,merchant_slug,provider_slug,action
4548436161,2020-12-31,2021-12-31,bink_test_merchant,visa,a
"""
        response = self.upload_file(file_content)
        self.assertContains(response, "Invalid provider: visa")

    def test_csv_validation_missing_mid(self) -> None:
        file_content = b"""mid,start_date,end_date,merchant_slug,provider_slug,action
,2020-12-31,2021-12-31,bink_test_merchant,amex,a
"""
        response = self.upload_file(file_content)
        self.assertEqual(0, BatchItem.objects.count())
        self.assertContains(response, "Missing row value for field: mid")

    def test_csv_validation_missing_merchant_slug(self) -> None:
        file_content = b"""mid,start_date,end_date,merchant_slug,provider_slug,action
4548436161,2020-12-31,2021-12-31,,amex,a
"""
        response = self.upload_file(file_content)
        self.assertEqual(0, BatchItem.objects.count())
        self.assertContains(response, "Missing row value for field: merchant_slug")

    def test_invalid_format(self) -> None:
        file_content = (
            b"\x89PNG\r\n\xce\x98\xce\xb5\xce\xac \xcf\x84\xce\xb7" b"\xcf\x82 \xce\x91\xcf\x85\xce\xb3\xce\xae\xcf\x82"
        )
        response = self.upload_file(file_content)
        self.assertContains(response, "Invalid file format")

    def test_process_batches_action(self) -> None:
        self.client.login(username="admin", password="!Potato12345!")
        batch = Batch.objects.create(file_name="test.csv")
        fields = dict(
            batch=batch,
            mid="12345",
            start_date=date.today(),
            end_date=date.today(),
            merchant_slug="test",
            provider_slug="amex",
            action=BatchItemAction.ADD,
        )
        for status in BatchItemStatus.values:
            BatchItem.objects.create(status=status, **fields)

        pending_item_id = BatchItem.objects.get(status=BatchItemStatus.PENDING).id

        task_queue.empty()
        self.assertEqual(0, len(task_queue))

        response = self.client.post(
            reverse("admin:mids_batch_changelist"),
            {"action": "queue_batches_action", "_selected_action": batch.id},
            follow=True,
        )
        self.assertEqual(BatchItemStatus.QUEUED, BatchItem.objects.get(id=pending_item_id).status)
        self.assertContains(response, "Queued 1 items")
        self.assertEqual(1, len(task_queue))
        job = task_queue.fetch_job(task_queue.job_ids[0])
        self.assertEqual(pending_item_id, job.args[0])
        self.assertEqual("app.tasks.process_item", job.func_name)
