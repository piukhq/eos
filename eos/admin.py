from django.conf import settings
from django.contrib import admin


class EosAdminSite(admin.AdminSite):
    site_header = settings.SITE_HEADER
