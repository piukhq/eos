import secrets

from django.contrib.auth import get_user_model, models
from django.contrib.auth.backends import ModelBackend
from django.http import HttpRequest


class AutoUserCreationBackend(ModelBackend):
    def authenticate(
        self, request: HttpRequest, username: str
    ) -> models.User:  # type:ignore
        User = get_user_model()

        try:
            # attempt to find an existing user
            return User.objects.get(username=username)
        except User.DoesNotExist:
            # create a user with a random password
            pw = secrets.token_hex(32)
            return User.objects.create_superuser(username, email=username, password=pw)
