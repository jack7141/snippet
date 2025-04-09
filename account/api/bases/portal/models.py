import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from rest_framework.authtoken.models import Token


class User(AbstractBaseUser):
    id = models.UUIDField(default=uuid.uuid4, editable=False, auto_created=True, unique=True, primary_key=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    email = models.EmailField('email address', unique=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        managed = False
        db_table = 'users_user'


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    name = models.CharField(_('name'), max_length=30, blank=True, help_text='이름')
    phone = models.CharField(max_length=20, null=True, blank=True, help_text='휴대폰 번호')

    class Meta:
        managed = False
        db_table = 'users_user_profile'

    def __str__(self):
        return str(self.user_id)


class ExpiringToken(Token):
    user = models.OneToOneField(User, related_name='auth_token', on_delete=models.CASCADE, verbose_name="User")
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'users_expringtoken'

    def expired(self):
        now = timezone.now()

        if self.expiry and self.updated < now - timezone.timedelta(seconds=self.expiry):
            return True
        return False

    @property
    def expiry(self):
        if self.user.is_staff:
            return None

        return settings.EXPIRING_TOKEN_LIFESPAN
