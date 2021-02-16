from django.contrib.admin.apps import AdminConfig


class EosAdminConfig(AdminConfig):
    default_site = "app.admin.EosAdminSite"
