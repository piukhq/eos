from authlib.integrations.django_client import OAuth
from django.contrib.auth import authenticate, login
from django.http import HttpResponse
from django.shortcuts import redirect
from django.conf import settings
from django.http import HttpRequest, JsonResponse

TENANT_ID = settings.OAUTH_TENANT_ID
oauth = OAuth()
oauth.register(
    "eos",
    client_id=settings.OAUTH_CLIENT_ID,
    client_secret=settings.OAUTH_CLIENT_SECRET,
    server_metadata_url=f"https://login.microsoftonline.com/{TENANT_ID}/v2.0/.well-known/openid-configuration",
    client_kwargs={"scope": "openid profile email"},
    redirect_uri=settings.OAUTH_REDIRECT_URI,
)


def oauth_login(request: HttpRequest) -> HttpResponse:
    """
    /admin/login/ handler - redirects to Azure OAuth flow.
    """
    return oauth.eos.authorize_redirect(request, settings.OAUTH_REDIRECT_URI)


def oauth_callback(request: HttpRequest) -> HttpResponse:
    """
    /admin/oidc/callback/ handler - attempts to authenticate & log the user in.
    """
    token = oauth.eos.authorize_access_token(request)
    userinfo = oauth.eos.parse_id_token(request, token)
    user = authenticate(request, username=userinfo["email"])

    if not user:
        # should probably redirect to an error page explaining that the user
        # does not have permission to be here.
        return HttpResponse("<h1>authentication failed</h1>", status_code=401)

    login(request, user)
    return redirect("admin:index")


def livez(request: HttpRequest) -> HttpResponse:
    return JsonResponse({}, status=204)
