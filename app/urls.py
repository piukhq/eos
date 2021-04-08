"""eos URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.urls import path, re_path
from django.views.static import serve
from .views import livez, oauth_login, oauth_callback

urlpatterns = [
    path("livez", view=livez, name="livez"),
    re_path(r"^eos/static/(?P<path>.*)$", serve, kwargs={"document_root": settings.STATIC_ROOT}),
]
if settings.SSO_ENABLED:
    urlpatterns.extend([
        path("eos/admin/login/", oauth_login),
        path("eos/admin/oidc/callback/", oauth_callback),
    ])

# this must be last to allow the admin/login override to work
urlpatterns.append(path("eos/admin/", admin.site.urls))
