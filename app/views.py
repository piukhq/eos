import json

from django.http import HttpRequest, JsonResponse, HttpResponseRedirect
from authlib.integrations.django_client import OAuth
from django.shortcuts import redirect, render
from django.urls import reverse

TENANT_ID = "a6e2367a-92ea-4e5a-b565-723830bcc095"
oauth = OAuth()
oauth.register(
    "eos",
    client_id="bbcb94ca-d25f-4a77-949a-c4a7da6a19f0",
    client_secret="7~PF_wKl33M6Ed9w1.kW-stIzgbt~yP_It",
    server_metadata_url=f"https://login.microsoftonline.com/{TENANT_ID}/v2.0/.well-known/openid-configuration",
    client_kwargs={"scope": "openid"},
)


def livez(request: HttpRequest) -> JsonResponse:
    return JsonResponse({}, status=204)

def home(request):
    redirect_uri = request.session.get('oidc_login_next', reverse("admin:index"))
    return HttpResponseRedirect(redirect_uri)


def login(request):
    redirect_uri = request.build_absolute_uri(reverse('auth'))
    return oauth.eos.authorize_redirect(request, redirect_uri)


def auth(request):
    token = oauth.eos.authorize_access_token(request)
    user = oauth.eos.parse_id_token(request, token)
    request.session['user'] = user
    return redirect('/eos/admin/')


def logout(request):
    request.session.pop('user', None)
    return redirect('/')
