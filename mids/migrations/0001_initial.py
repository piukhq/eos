# Generated by Django 3.1.6 on 2021-02-15 15:54

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Batch",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file_name", models.CharField(help_text="The name of the uploaded file", max_length=250)),
                ("time_uploaded", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name_plural": "Batches",
                "ordering": ["-time_uploaded"],
            },
        ),
        migrations.CreateModel(
            name="BatchItem",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("mid", models.CharField(max_length=50)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("merchant_slug", models.CharField(max_length=50)),
                ("provider_slug", models.CharField(max_length=50)),
                ("status", models.IntegerField(choices=[(1, "Pending"), (2, "Queued"), (3, "Done"), (4, "Error")])),
                ("action", models.CharField(choices=[("A", "Add"), ("D", "Delete"), ("U", "Update")], max_length=1)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("error_code", models.CharField(blank=True, max_length=7)),
                ("error_type", models.CharField(blank=True, max_length=15)),
                ("error_description", models.CharField(blank=True, max_length=100)),
                ("request_timestamp", models.DateTimeField(null=True)),
                ("response", models.JSONField(null=True)),
                ("batch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="mids.batch")),
            ],
        ),
    ]
