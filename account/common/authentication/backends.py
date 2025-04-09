from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

UserModel = get_user_model()


class UserModelBackend(ModelBackend):

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        try:
            user = UserModel._default_manager.get_by_natural_key(username, request=request)
        except UserModel.DoesNotExist:
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a non-existing user (#20760).
            UserModel().set_password(password)
        else:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user

    def user_can_authenticate(self, user):
        return True if user else False


class UserModelByCiBackend(ModelBackend):

    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            if username != UserModel().get_hash(password.encode('utf-8')):
                raise UserModel.DoesNotExist()
            user = UserModel._default_manager.get_by_ci(password, request=request)
        except UserModel.DoesNotExist:
            UserModel().set_password(password)
        else:
            if user.profile.ci == password and self.user_can_authenticate(user):
                return user

    def user_can_authenticate(self, user):
        return True if user else False
