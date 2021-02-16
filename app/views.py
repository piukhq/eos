from django.http import HttpRequest, JsonResponse


def livez(request: HttpRequest) -> JsonResponse:
    return JsonResponse({}, status=204)
