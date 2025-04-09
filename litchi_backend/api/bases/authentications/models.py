import uuid
import random

from django.db import models
from django.conf import settings
from fernet_fields import EncryptedCharField, EncryptedTextField
from api.bases.authentications.choices import AuthenticationChoices, Words


class Auth(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    cert_type = models.CharField(max_length=1, choices=AuthenticationChoices.AUTH_TYPES, null=False, blank=False)
    code = models.CharField(max_length=6, help_text="인증코드")
    is_verified = models.BooleanField(default=False, help_text="인증여부")
    is_expired = models.BooleanField(default=False, help_text="만료여부")

    # etc 필드는 Auth 모델 생성시 자유롭게 사용하기 위한 용도
    etc_1 = models.CharField(max_length=128, null=True, blank=True)
    etc_2 = models.CharField(max_length=128, null=True, blank=True)
    etc_3 = models.CharField(max_length=128, null=True, blank=True)
    etc_encrypted_1 = EncryptedCharField(max_length=128, null=True, blank=True)
    etc_encrypted_2 = EncryptedCharField(max_length=128, null=True, blank=True)
    etc_encrypted_3 = EncryptedCharField(max_length=128, null=True, blank=True)
    etc_entrypted_text_1 = EncryptedTextField(null=True, blank=True)
    etc_entrypted_text_2 = EncryptedTextField(null=True, blank=True)
    etc_entrypted_text_3 = EncryptedTextField(null=True, blank=True)

    created_date = models.DateTimeField(auto_now_add=True, help_text="인증요청 일시")

    class Meta:
        ordering = ('-created_date',)

    def __init__(self, *args, **kwargs):
        super(Auth, self).__init__(*args, **kwargs)

        if not self.code:
            if self.cert_type == '1':
                self.generate_numeric_code()
            elif self.cert_type == '2':
                self.generate_word_code()

    def __str__(self):
        return self.id.__str__()

    def generate_numeric_code(self, digit=6):
        _format = "{:0X}".replace('X', str(digit))
        self.code = _format.format(random.randrange(0, int("9" * digit)))
        return self.code

    def generate_word_code(self):
        self.code = random.choice(Words.WORDS_PREV) + random.choice(Words.WORDS)
        return self.code
