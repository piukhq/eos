import secrets

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class AutoUserCreationBackend(ModelBackend):
    def authenticate(self, request, username):
        User = get_user_model()

        try:
            # attempt to find an existing user
            return User.objects.get(username=username)
        except User.DoesNotExist:
            # create a user with a random password
            pw = secrets.token_hex(32)
            return User.objects.create_superuser(username, password=pw)
