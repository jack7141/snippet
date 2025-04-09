import uuid
import hashlib

from django.conf import settings
from django.contrib.auth.models import (
    BaseUserManager, AbstractBaseUser, PermissionsMixin
)
from django.db import models
from django.apps import apps
from django.contrib.sites.models import Site as defaultSite
from django.contrib.sites.shortcuts import get_current_site
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from model_utils import Choices
from rest_framework.authtoken.models import Token


class UserManager(BaseUserManager):
    def get_by_natural_key(self, username, request=None, site=None):
        if request and apps.is_installed('django.contrib.sites'):
            return self.get(**{self.model.USERNAME_FIELD: username, 'site': get_current_site(request)})
        elif site:
            return self.get(**{self.model.USERNAME_FIELD: username, 'site': site})
        else:
            return self.get(**{self.model.USERNAME_FIELD: username})

    def get_by_ci(self, ci, request=None, site=None):
        ci_hash = hashlib.sha256(ci.encode('utf-8')).hexdigest()
        if request and apps.is_installed('django.contrib.sites'):
            return self.get(**{'profile__ci_hash': ci_hash, 'site': get_current_site(request)})
        elif site:
            return self.get(**{'profile__ci_hash': ci_hash, 'site': site})
        else:
            return self.get(**{'profile__ci_hash': ci_hash})


class Site(models.Model):
    domain = models.CharField(
            _('domain name'),
            max_length=100,
            unique=True,
    )
    name = models.CharField(_('display name'), max_length=50)

    class Meta:
        db_table = 'django_site'
        managed = False


def get_default_site():
    try:
        return Site.objects.first().id
    except Exception as e:
        return None


class User(AbstractBaseUser):
    id = models.UUIDField(default=uuid.uuid4, editable=False, auto_created=True, unique=True, primary_key=True)
    email = models.EmailField(_('email address'))
    is_staff = models.BooleanField(
            _('staff status'),
            default=False,
            help_text=_('Designates whether the user can log into this admin site.'),
    )
    is_active = models.BooleanField(
            _('active'),
            default=True,
            help_text=_(
                    'Designates whether this user should be treated as active. '
                    'Unselect this instead of deleting accounts.'
            ),
    )
    is_vendor = models.BooleanField(
            _('vendor status'),
            default=False,
    )
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)
    is_online = models.PositiveSmallIntegerField(default=0)
    last_password_change = models.DateTimeField(default=timezone.now, blank=True, null=True)
    site = models.ForeignKey(Site, default=get_default_site, on_delete=models.CASCADE, blank=True, null=True,
                             related_name='litchi_sites')

    objects = UserManager()

    USERNAME_FIELD = 'email'

    def get_full_name(self):
        return self.email

    def get_short_name(self):
        return self.email

    def __str__(self):
        return self.email

    @staticmethod
    def get_hash(value):
        return hashlib.sha256(value).hexdigest()

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'
        unique_together = (('email', 'site'),)
        db_table = 'users_user'
        ordering = ['email']
        managed = False


class Profile(models.Model):
    MOBILE_CARRIER = Choices(
            ('01', 'skt', 'SKT'),
            ('02', 'kt', 'KT'),
            ('03', 'lg', 'LG U+'),
            ('알뜰폰', [
                ('04', 'r_skt', 'SKT'),
                ('05', 'r_kt', 'KT'),
                ('06', 'r_lg', 'LG U+')
            ]),
    )

    GENDER_TYPE = Choices(
            ('내국인', [
                (1, 'l1', '남(1)'),
                (2, 'l2', '여(2)'),
                (3, 'l3', '남(3)'),
                (4, 'l4', '여(4)'),
                (9, 'l9', '남(9)'),
                (0, 'l0', '여(10)'),
            ]),
            ('외국인', [
                (5, 'f5', '남(5)'),
                (6, 'f6', '여(6)'),
                (7, 'f7', '남(7)'),
                (8, 'f8', '여(8)'),
            ])
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    name = models.CharField(_('name'), max_length=30, blank=True, help_text='이름')
    phone = models.CharField(max_length=20, null=True, blank=True, help_text='휴대폰 번호')
    ci_hash = models.CharField(max_length=64, blank=True, null=True, help_text='고유 식별번호 Hash값', editable=False)

    class Meta:
        db_table = 'users_user_profile'
        managed = False

    def __str__(self):
        return str(self.user_id)


class ExpiringToken(Token):
    """Extend Token to add an expired method."""
    user = models.OneToOneField(User, related_name='auth_token', on_delete=models.CASCADE, verbose_name="User")
    updated = models.DateTimeField(auto_now=True)

    def expired(self):
        """Return boolean indicating token expiration."""
        now = timezone.now()

        if self.expiry and self.updated < now - timezone.timedelta(seconds=self.expiry):
            return True
        return False

    @property
    def expiry(self):
        if self.user.is_staff:
            return None

        return settings.EXPIRING_TOKEN_LIFESPAN

    class Meta:
        db_table = 'users_expiringtoken'
        managed = False
