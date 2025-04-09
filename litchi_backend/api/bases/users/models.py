import ast
import hashlib
import logging
import shortuuid
import uuid
import random

from datetime import datetime
from collections import OrderedDict
from urllib.parse import ParseResult

from django.conf import settings
from django.contrib.auth.models import (
    BaseUserManager, AbstractBaseUser, PermissionsMixin
)
from django.db import models, utils
from django.apps import apps
from django.contrib.sites.models import Site
from django.contrib.sites.shortcuts import get_current_site
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.template.loader import render_to_string
from django.template import Template as DjangoTemplate, Context
from django.urls import reverse

from rest_framework.authtoken.models import Token
from rest_framework.validators import ValidationError
from fernet_fields import EncryptedCharField
from auditlog.registry import auditlog

from common.models import JSONField, ListField
from common.algorithms.seed_cbc import SeedCBC

from api.bases.users.tasks import send_mass_email_html
from api.bases.users.choices import (
    ProfileChoices,
    VendorPropertyChoices,
    ActivationLogChoices
)
from api.bases.tendencies.utils import TENDENCY_SCORE_TABLE

SEED_IV = settings.SEED_IV

logger = logging.getLogger('django.server')


class UserManager(BaseUserManager):
    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)

    def get_by_natural_key(self, username, request=None):
        if request and apps.is_installed('django.contrib.sites'):
            return self.get(
                **{'is_active': True, self.model.USERNAME_FIELD: username, 'site': get_current_site(request)})
        else:
            return self.get(**{'is_active': True, self.model.USERNAME_FIELD: username})

    def get_by_ci(self, ci, request=None):
        ci_hash = hashlib.sha256(ci.encode('utf-8')).hexdigest()
        if request and apps.is_installed('django.contrib.sites'):
            return self.get(**{'is_active': True, 'profile__ci_hash': ci_hash, 'site': get_current_site(request)})
        else:
            return self.get(**{'is_active': True, 'profile__ci_hash': ci_hash})


def get_default_site():
    try:
        return Site.objects.first().id
    except Exception as e:
        return None


def generate_referral_code():
    short = shortuuid.ShortUUID(alphabet='23456789ABCDEFGHJKLMNPQRSTUVWXYZ')
    length = 10
    referral_code = short.random(length=length)
    try:
        while User.objects.filter(referral_code=referral_code).exists():
            referral_code = short.random(length=length)
    except Exception as e:
        logger.error(e)

    return referral_code


class User(AbstractBaseUser, PermissionsMixin):
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
    site = models.ForeignKey(Site, default=get_default_site, on_delete=models.CASCADE, blank=True, null=True)
    referral_code = models.CharField(max_length=10, editable=False, blank=False, null=False,
                                     default=generate_referral_code,
                                     help_text='추천인 코드')
    deactivated_at = models.DateTimeField(null=True, blank=True, help_text='탈퇴일', editable=False)
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

    def get_random_digit(self):
        """
        :return: 1~5
        """
        return (hash(self.id) % 5) + 1

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'
        unique_together = (('email', 'site', 'referral_code'),)
        ordering = ['email']

    def get_websocket_groups(self):
        websocket_groups = [str(self.id)]

        for channel in self.join_mock_channel_user_set.all():
            websocket_groups.append(str(channel.id))

        if self.is_staff:
            websocket_groups.append(settings.ADMINISTRATOR_CHANNEL_NAME)

        return websocket_groups

    def set_password(self, raw_password):
        super(User, self).set_password(raw_password)
        self.last_password_change = timezone.now()

    def send_activation_email(self, request, confirm_type='signup', send_to=None):
        subject = None
        html_message = None
        message = ''
        if not send_to:
            send_to = str(self.email)

        log_instance = ActivationLog(user=self)

        activation_key, expires = log_instance.generate_activation_key(confirm_type)

        activation_url = self.get_absolute_confirmed_url(request, activation_key, confirm_type)

        context = {
            'user': str(self.email),
            'activation_url': activation_url
        }

        if confirm_type == 'signup' and self.site.settings.send_wc_email:
            html_message = DjangoTemplate(self.site.settings.wc_template).render(Context(context))
            subject = '[파운트] 파운트 서비스 회원가입을 환영합니다.'
        elif confirm_type == 'password_reset':
            html_message = render_to_string('password_reset.html', context)
            subject = '[파운트] 비밀번호 재설정 인증 메일입니다.'
        elif confirm_type == 'validate_email':
            context.update({
                'name': self.profile.name
            })
            html_message = render_to_string('validate_email.html', context)
            subject = '[파운트] 이메일 재설정 인증 메일입니다.'

        if subject and html_message:
            datatuple = (subject, message, html_message, settings.EMAIL_MAIN, [send_to]),
            send_mass_email_html(datatuple, is_async=False)

        log_instance.save()
        return log_instance

    def get_absolute_confirmed_url(self, request, activation_key, confirm_type):
        return request.build_absolute_uri(
            reverse('email_confirmed',
                    kwargs={'activation_key': activation_key, 'confirm_type': confirm_type}))


class Image(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, auto_created=True, unique=True, primary_key=True,
                          help_text='자원 고유 ID')
    file = models.ImageField(upload_to='avatars', null=True, blank=True, help_text='이미지',
                             width_field='width', height_field='height')
    width = models.PositiveIntegerField(blank=True, null=True, help_text='이미지 넓이')
    height = models.PositiveIntegerField(blank=True, null=True, help_text='이미지 높이')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.file)

    @staticmethod
    def default_image(digit):
        filename = 'profile_{}.png'.format(digit)
        path = 'litchi/media/avatars/{}'.format(filename)

        file = ParseResult(scheme='https',
                           netloc='cdn.fount.co',
                           path=path, params='', query='', fragment='').geturl()
        return {
            'file': file,
            'width': '360',
            'height': '360',
        }


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    avatar = models.ForeignKey(Image, on_delete=models.SET_NULL, null=True, blank=True, related_name='avatar')
    name = models.CharField(_('name'), max_length=30, blank=True, help_text='이름')
    nickname = models.CharField(max_length=30, null=True, blank=True, help_text='별명')
    phone = models.CharField(max_length=20, null=True, blank=True, help_text='휴대폰 번호')
    mobile_carrier = models.CharField(max_length=2, choices=ProfileChoices.MOBILE_CARRIER, null=True, blank=True,
                                      help_text='휴대폰 통신사')
    address = models.CharField(max_length=120, null=True, blank=True, help_text='주소')
    birth_date = models.DateField(null=True, blank=True, help_text='생년월일')
    gender_code = models.PositiveSmallIntegerField(choices=ProfileChoices.GENDER_TYPE, null=True, blank=True,
                                                   help_text='성별')
    risk_type = models.IntegerField(null=True, blank=True, help_text='위험 성향')
    personal_type = models.IntegerField(null=True, blank=True, help_text='개인 성향')
    config = JSONField(null=True, blank=True, default={}, help_text='기타 설정')
    ci = EncryptedCharField(max_length=128, blank=True, null=True, help_text='고유식별번호')
    ci_hash = models.CharField(max_length=64, blank=True, null=True, help_text='고유 식별번호 Hash값', editable=False)
    funnels = models.CharField(max_length=128, blank=True, null=True, help_text='유입경로')
    tendency_response = ListField(null=True, blank=True, help_text="투자성향 응답결과(하위호환)")

    class Meta:
        db_table = 'users_user_profile'

    def __str__(self):
        return str(self.user_id)

    def save(self, **kwargs):
        if self.ci:
            ci_hash = self.user.get_hash(self.ci.encode('utf-8'))
            if self.ci_hash != ci_hash:
                self.ci_hash = ci_hash
        super().save(**kwargs)

    @property
    def is_contracted(self):
        try:
            return self.user.contract_set.filter(is_canceled=False).exists()
        except:
            return False

    @property
    def hpin(self):
        try:
            return ast.literal_eval(str(self.config)).get('hpin')
        except:
            return None

    def get_encrypted_ci(self):
        if self.ci_hash:
            encryptor = SeedCBC(self.ci_hash, SEED_IV)
            return encryptor.encrypt(self.ci)
        return self.ci

    def is_validated_user(self, birth_date, gender_code):
        year_prefix = 19
        if gender_code in ['0', '9']:
            year_prefix -= 1
        elif gender_code in ['3', '4', '7', '8']:
            year_prefix += 1
        birth_date = datetime.strptime(str(year_prefix) + birth_date, '%Y%m%d').date()
        return bool(self.birth_date == birth_date and (self.gender_code % 2) == (int(gender_code) % 2))

    @property
    def last_tendency_response(self):
        try:
            return self.user.tendency_responses.order_by('-created_at')[0]
        except:
            return self.user.tendency_responses.latest('created_at')


class VendorProperty(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True,
                                related_name='vendor_props')
    type = models.CharField(max_length=12, null=False, blank=False, choices=VendorPropertyChoices.TYPE)
    company_name = models.CharField(max_length=30, null=False, blank=False, help_text='회사명')
    code = models.CharField(max_length=8, null=False, blank=False, help_text='관리코드')
    terminate_msg = models.CharField(max_length=128, null=False, blank=False, help_text='해지용 메시지')
    restrict_start = models.DateTimeField(null=True, blank=True, help_text='장애처리 시작시간')
    restrict_end = models.DateTimeField(null=True, blank=True, help_text='장애처리 종료시간')

    class Meta:
        db_table = 'users_vendor_property'
        verbose_name_plural = 'vendor properties'

    def is_restrict(self):

        if self.code == 'kb':
            # KB증권의 경우 09:00~09:10까지 데이터 오류가 있으나, 앞/뒤 버퍼 1분씩 두고 적용
            # Todo. 추후 서버 배포없이 관리 가능하도록 개선작업 필요.
            now = timezone.localtime()
            kb_from = timezone.localtime().replace(hour=8, minute=59, second=0, microsecond=0)
            kb_to = timezone.localtime().replace(hour=9, minute=11, second=0, microsecond=0)

            return kb_from <= now <= kb_to

        # 장애처리 시간대 포함여부 체크
        if not self.restrict_start and not self.restrict_end:
            return False

        now = timezone.now()

        if not self.restrict_start:
            return now <= self.restrict_end
        elif not self.restrict_end:
            return self.restrict_start <= now
        else:
            return self.restrict_start <= now <= self.restrict_end


class ActivationLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.SET_NULL, related_name='actionvation_logs', null=True)
    activation_key = models.CharField(max_length=255, primary_key=True)
    expires = models.DateTimeField(null=True, blank=True)
    confirm_type = models.CharField(max_length=30, choices=ActivationLogChoices.EMAIL_CONFIRM_TYPE, default='signup')
    is_confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def generate_activation_key(self, confirm_type):
        short_hash = hashlib.sha1(str(random.random()).encode('utf-8')).hexdigest()[:5]
        base = str(self.user.email).split('@')[0]

        activation_key = hashlib.sha1(str(short_hash + base).encode('utf-8')).hexdigest()

        expires_map = OrderedDict(ActivationLogChoices.EXPIRE_CONFIRM_TYPE)

        num, period = expires_map.get(confirm_type).split('/')

        expires = timezone.now() + timezone.timedelta(**{period: int(num)})

        self.activation_key = activation_key
        self.expires = expires
        self.confirm_type = confirm_type

        return activation_key, expires


class ExpiringToken(Token):
    """Extend Token to add an expired method."""
    updated = models.DateTimeField(auto_now=True)

    def expired(self):
        """Return boolean indicating token expiration."""
        now = timezone.now()

        if self.user.is_active and self.expiry and self.updated < now - timezone.timedelta(seconds=self.expiry):
            return True
        return False

    @property
    def expiry(self):
        if self.user.is_vendor or self.user.is_staff:
            return None

        return settings.EXPIRING_TOKEN_LIFESPAN


def validate_file_extension(value):
    import os
    from django.core.exceptions import ValidationError
    ext = os.path.splitext(value.name)[1]  # [0] returns path+filename
    valid_extensions = ['.pdf', '.doc', '.docx', '.jpg', '.png']
    if not ext.lower() in valid_extensions:
        raise ValidationError(u'Unsupported file extension.')


class Tendency(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    result = ListField(blank=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Tendencies'

    @staticmethod
    def validate_score(data):
        score_table = TENDENCY_SCORE_TABLE
        score = 0
        section = 0
        errors = {}

        for idx, value in enumerate(data):
            try:
                sc = score_table[idx]

                if idx in [2, 3, 4, 5, 6, 7]:
                    if value \
                            and section is 0 \
                            and idx in [2, 4, 6] \
                            and list(filter(lambda x: x > 0, value)):
                        section = (sc + score_table[idx + 1][data[idx + 1] - 1])
                        score += section
                    else:
                        continue
                elif idx == 8 and value:
                    score -= section
                else:
                    if isinstance(sc, list):
                        if value - 1 >= 0:
                            score += sc[value - 1]
                        else:
                            raise IndexError('list index out of range')
            except IndexError as e:
                if len(score_table) > idx:
                    errors[idx] = '{} - allow range 1 to {}'.format(str(e), len(score_table[idx]))
                else:
                    errors[idx] = e
            except Exception as e:
                errors[idx] = e

        if errors:
            raise ValidationError({'result': errors})

        return score

    def get_score(self):
        return self.validate_score(self.result)

    def get_risk_type(self):
        score = self.get_score()

        if score <= 10:
            return 0
        elif 11 <= score <= 15:
            return 1
        elif 16 <= score <= 20:
            return 2
        elif 21 <= score <= 25:
            return 3
        elif 26 <= score:
            return 4


class VendorTendency(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    vendor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, help_text='증권사',
                               related_name='vendor_tendencies')
    result = ListField(blank=False, null=False, help_text='응답 결과')
    forwarded_at = models.DateTimeField(blank=True, null=True, help_text='전달 일시')
    created_at = models.DateTimeField(auto_now_add=True, help_text='생성일')
    updated_at = models.DateTimeField(auto_now=True, help_text='수정일')

    class Meta:
        unique_together = (('user', 'vendor'),)


class Invite(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, auto_created=True, unique=True, primary_key=True)
    inviter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='invites')
    joiner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name='joiners', null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (('inviter', 'joiner'),)


class SiteSettings(models.Model):
    site = models.OneToOneField(Site, on_delete=models.CASCADE, to_field='domain', related_name='settings')
    send_wc_email = models.BooleanField(default=True, help_text='회원가입시 이메일 발송여부')
    wc_template = models.TextField(blank=True, null=True, help_text='회원가입 이메일 템플릿')


auditlog.register(Profile)
