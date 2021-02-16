from django.db import models

# from django.contrib import auth


class Batch(models.Model):
    file_name = models.CharField(max_length=250, help_text="The name of the uploaded file")
    time_uploaded = models.DateTimeField(auto_now_add=True)
    # user = auth.models.User()

    class Meta:
        verbose_name_plural = "Batches"
        ordering = ["-time_uploaded"]


class BatchItemAction(models.TextChoices):
    ADD = "A", "Add"
    DELETE = "D", "Delete"
    UPDATE = "U", "Update"


class BatchItemStatus(models.IntegerChoices):
    PENDING = 1, "Pending"
    QUEUED = 2, "Queued"
    DONE = 3, "Done"
    ERROR = 4, "Error"


class BatchItem(models.Model):
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE)
    mid = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    merchant_slug = models.CharField(max_length=50)
    provider_slug = models.CharField(max_length=50)
    status = models.IntegerField(choices=BatchItemStatus.choices)
    action = models.CharField(choices=BatchItemAction.choices, max_length=1)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    error_code = models.CharField(max_length=7, blank=True)
    error_type = models.CharField(max_length=15, blank=True)
    error_description = models.CharField(max_length=100, blank=True)
    request_timestamp = models.DateTimeField(null=True, blank=True)
    response = models.JSONField(null=True, blank=True)  # type:ignore
