from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.contrib.auth.models import User
from django.urls import reverse

from mids.models import Batch, BatchItem, BatchItemStatus


class TestMidsAdmin(TestCase):
    def setUp(self) -> None:
        User.objects.create_superuser("admin", "admin@bink.com", "!Potato12345!")
        self.client = Client()

    def test_upload(self) -> None:
        file_content = b"""mid,start_date,end_date,merchant_slug,provider_slug,action
4548436161,2021-01-01,2999-12-31,bink_test_merchant,amex,a
9999999999,2021-01-01,2999-12-31,bink_test_merchant,amex,a
"""
        batch_file = SimpleUploadedFile("mids.csv", file_content, content_type="text/csv")
        self.client.login(username="admin", password="!Potato12345!")
        response = self.client.post(reverse("admin:mids_batch_add"), {"input_file": batch_file}, follow=True)
        self.assertContains(response, "Batch imported")
        self.assertEqual(1, Batch.objects.count())
        batch = Batch.objects.get()
        self.assertEqual("mids.csv", batch.file_name)
        self.assertEqual(2, BatchItem.objects.filter(status=BatchItemStatus.PENDING).count())
