from importlib import import_module
import logging

from django.conf import settings
from django.contrib.auth import get_user_model, authenticate, password_validation as validators
from django.core.exceptions import ValidationError as django_validation_error

from rest_framework import serializers, status
from rest_framework.validators import ValidationError
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated, NotFound

from common.axes.attempts import get_site
from common.exceptions import ConflictException, PreconditionFailed
from common.utils import DotDict

from api.bases.users.models import (
    Profile, ActivationLog, ExpiringToken, Tendency, VendorTendency, Invite, User, Image, VendorProperty
)
from api.bases.notifications.models import Topic, Subscribe
from api.bases.notifications.choices import NotificationChoices

from api.versioned.v1.tendencies.serializers import ResponseSerializer
from api.versioned.v1.users.tendency_maps import KBTendencyMaps, SHTendencyMaps

SEED_IV = settings.SEED_IV
logger = logging.getLogger('django.server')

try:
    DEFAULT_TOPIC = Topic.objects.get(name='notification')
except:
    DEFAULT_TOPIC = None


def get_username_field():
    try:
        username_field = get_user_model().USERNAME_FIELD
    except:
        username_field = 'username'

    return username_field


class ImageSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    width = serializers.IntegerField(read_only=True, help_text='이미지 넓이')
    height = serializers.IntegerField(read_only=True, help_text='이미지 높이')

    class Meta:
        model = Image
        fields = '__all__'

    def create(self, validated_data):
        model = self.Meta.model
        instance = model.objects.create(file=validated_data['file'])
        user = validated_data['user']
        try:
            user.profile.avatar = instance
            user.profile.save()
        except Exception as e:
            logger.error(e)

        return instance


class ProfileSerializer(serializers.ModelSerializer):
    config = serializers.JSONField(required=False)
    email = serializers.EmailField(source='user.email', read_only=True)
    is_contracted = serializers.BooleanField(read_only=True)
    gender = serializers.SerializerMethodField(read_only=True)
    ci = serializers.CharField(write_only=True, required=False)
    tendency_response = serializers.ListField(required=False)
    referral_code = serializers.CharField(read_only=True, source='user.referral_code')
    hpin = serializers.CharField(read_only=True)
    avatar = serializers.SerializerMethodField(read_only=True)
    last_tendency_response = ResponseSerializer(read_only=True)

    class Meta:
        model = Profile
        fields = '__all__'
        lockable_fields = ('ci',)
        extra_kwargs = {
            'user': {'read_only': True}
        }

    def get_fields(self):
        fields = super().get_fields()

        if self.instance:
            for field_name in self.Meta.lockable_fields:
                try:
                    fields[field_name].read_only = bool(getattr(self.instance, field_name))
                except:
                    pass

        return fields

    def get_gender(self, obj):
        if obj.gender_code is not None:
            return "male" if obj.gender_code % 2 else "female"
        return obj.gender_code

    def get_avatar(self, instance):
        if hasattr(instance, 'avatar') and hasattr(instance.avatar, 'file'):
            return ImageSerializer(instance.avatar).data

        return Image.default_image(instance.user.get_random_digit())


class ProfileRetrieveSerializer(ProfileSerializer):
    ci = serializers.CharField(read_only=True)
    ci_encrypted = serializers.CharField(read_only=True, source='get_encrypted_ci')


class UserSerializer(serializers.ModelSerializer):
    is_online = serializers.BooleanField(read_only=True)
    name = serializers.CharField(read_only=True, source='profile.name')
    email = serializers.EmailField(read_only=True)

    class Meta:
        model = get_user_model()
        exclude = ('password',)


class InviteSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='joiner.email')
    name = serializers.CharField(source='joiner.profile.name')

    class Meta:
        model = Invite
        fields = ('joiner', 'email', 'name', 'created_at')


class InviteCreateSerializer(serializers.ModelSerializer):
    referral_code = serializers.SlugRelatedField(slug_field='referral_code',
                                                 queryset=User.objects.all(),
                                                 source='inviter', help_text='추천인 코드')

    class Meta:
        model = Invite
        fields = ('referral_code',)


class TopicCreateSerialzier(serializers.ModelSerializer):
    name = serializers.CharField()

    class Meta:
        model = Topic
        fields = ('name',)
        lookup_field = 'name'


class SubscribeCreateSerializer(serializers.ModelSerializer):
    """
    Input Format
    ...,
    ...,
    "subscribes": {
        "topics": [
            {"name": "marketing"}
        ]
    }
    """
    topics = TopicCreateSerialzier(many=True)

    class Meta:
        model = Subscribe
        fields = ('topics',)


class UserCreateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, required=False)
    profile = ProfileSerializer(required=False)
    invite = InviteCreateSerializer(required=False)
    subscribes = SubscribeCreateSerializer(write_only=True, required=False)

    class Meta:
        model = get_user_model()
        fields = ('email', 'password', 'id', 'profile', 'invite', 'referral_code', 'subscribes')

    def validate(self, attrs):
        password = attrs.get('password')
        ci = attrs.get('profile', {}).get('ci')

        if not (password or ci):
            raise serializers.ValidationError("Either Password or Profile's secret field is required.")

        return attrs

    def create(self, validated_data):
        password = validated_data.get('password')
        try:
            if password:
                validators.validate_password(password)
        except django_validation_error as e:
            raise ValidationError({"password": e.messages})

        model = self.Meta.model
        site = get_site(self.context.get('request'))
        instance, is_create = model.objects.get_or_create(is_active=True,
                                                          email=validated_data['email'],
                                                          site=site)

        if not is_create and instance.is_active:
            raise ConflictException({'email': 'user with this email address already exists. '})

        if password:
            instance.set_password(validated_data['password'])
            instance.save()

        if validated_data.get('profile'):
            try:
                for k, v in validated_data['profile'].items():
                    setattr(instance.profile, k, v)
                instance.profile.save()
            except Exception as e:
                logger.error(e)

        if validated_data.get('invite'):
            try:
                Invite.objects.create(**dict({'joiner': instance}, **validated_data.get('invite')))
            except Exception as e:
                logger.error(e)

        if validated_data.get('subscribes') and validated_data.get('subscribes').get('topics'):
            try:
                for protocol in [NotificationChoices.PROTOCOLS.sms,
                                 NotificationChoices.PROTOCOLS.email,
                                 NotificationChoices.PROTOCOLS.push,
                                 NotificationChoices.PROTOCOLS.app]:
                    sub_instance, _ = Subscribe.objects.get_or_create(
                        user=instance,
                        type=protocol
                    )

                    for topic in validated_data.get('subscribes').get('topics'):
                        sub_instance.topics.add(Topic.objects.get(**topic))

            except Topic.DoesNotExist as e:
                raise ValidationError({"topic_name": e})
            except Exception as e:
                logger.error(e)

        return instance

    def save(self, **kwargs):
        instance = super(UserCreateSerializer, self).save(**kwargs)

        try:
            instance.send_activation_email(self.context.get('request'))
        except Exception as e:
            logger.error(e)

        return instance


class UserRetrieveSerializer(UserSerializer):
    profile = ProfileSerializer()
    password = serializers.CharField(write_only=True)
    invites = serializers.IntegerField(source='invites.count', read_only=True)

    class Meta:
        model = get_user_model()
        fields = '__all__'

    def update(self, instance, validated_data):
        info = serializers.model_meta.get_field_info(instance)

        for attr, value in validated_data.items():
            if attr in info.relations and info.relations[attr].to_many:
                serializers.set_many(instance, attr, value)
            elif isinstance(validated_data[attr], dict):
                nested_instance = getattr(instance, attr)
                [setattr(nested_instance, _attr, _value) for _attr, _value in validated_data[attr].items()]
                nested_instance.save()
            else:
                if attr != 'password':
                    setattr(instance, attr, value)
                else:
                    try:
                        validators.validate_password(value, user=instance)
                    except django_validation_error as e:
                        raise ValidationError({"password": e.messages})
                    instance.set_password(value)
        instance.save()

        return instance


class UserUpdateSerializer(UserSerializer):
    profile = ProfileSerializer()
    password = serializers.CharField(write_only=True)
    invites = serializers.IntegerField(source='invites.count', read_only=True)
    email = serializers.EmailField(write_only=True)

    class Meta:
        model = get_user_model()
        fields = '__all__'

    def update(self, instance, validated_data):
        info = serializers.model_meta.get_field_info(instance)

        for attr, value in validated_data.items():
            if attr in info.relations and info.relations[attr].to_many:
                serializers.set_many(instance, attr, value)
            elif isinstance(validated_data[attr], dict):
                nested_instance = getattr(instance, attr)
                [setattr(nested_instance, _attr, _value) for _attr, _value in validated_data[attr].items()]
                nested_instance.save()
            else:
                if attr != 'password':
                    setattr(instance, attr, value)
                else:
                    try:
                        validators.validate_password(value, user=instance)
                    except django_validation_error as e:
                        raise ValidationError({"password": e.messages})
                    instance.set_password(value)
        instance.save()

        return instance


class UserPasswordChangeSerializer(UserRetrieveSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = get_user_model()
        fields = ('password',)


class PayLoadSerializer(serializers.Serializer):
    token = serializers.CharField()
    expiry = serializers.IntegerField()


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(write_only=True, required=False)
    password = serializers.CharField(write_only=True)
    force_login = serializers.BooleanField(write_only=True, required=False, default=False)
    user = UserSerializer(read_only=True)
    payload = PayLoadSerializer(read_only=True)

    class Meta:
        error_status_codes = {
            status.HTTP_400_BAD_REQUEST: None,
            status.HTTP_401_UNAUTHORIZED: None,
            status.HTTP_403_FORBIDDEN: None,
            status.HTTP_409_CONFLICT: None
        }

    def __init__(self, *args, **kwargs):
        engine = import_module(settings.SESSION_ENGINE)
        self.SessionStore = engine.SessionStore
        super(UserLoginSerializer, self).__init__(*args, **kwargs)

    @property
    def username_field(self):
        return get_username_field()

    def get_credentials(self, attrs):
        return {
            'username': attrs.get(self.username_field) or User.get_hash(attrs.get('password').encode('utf-8')),
            'password': attrs.get('password')
        }

    def validate(self, attrs):
        credentials = self.get_credentials(attrs)

        request = self.context.get('_request')
        force_login = attrs.get('force_login')
        try:
            user = authenticate(**credentials, request=request)
        except User.MultipleObjectsReturned:
            raise ConflictException(ConflictException(code='DuplicateAccount').get_full_details())

        if user:
            if not user.is_active:
                raise NotAuthenticated(NotAuthenticated().get_full_details())

            token, is_new = ExpiringToken.objects.get_or_create(user=user)

            # 1. 토큰이 만료된경우는 재접속으로 판단.
            # 2. 강제 토큰 갱신의 경우도 재접속으로 판단.
            # 3. 만료되지 않았는데 유저가 접속중이면 동시접속으로 판단 - 제거(주석 처리)
            if token.expired() or force_login:
                token.delete()
                token = ExpiringToken.objects.create(user=user)
            # elif user.is_online:
            #     raise ConflictException(ConflictException(code='AlreadyOnline').get_full_details())

            return {
                'payload': {'token': token.key, 'expiry': token.expiry},
                'user': user
            }
        else:
            raise AuthenticationFailed(AuthenticationFailed().get_full_details())

        return attrs


class UserLoginByCISerializer(UserLoginSerializer):
    email = serializers.HiddenField(required=False, default=None)
    password = serializers.CharField(write_only=True)
    force_login = serializers.BooleanField(write_only=True, required=False, default=False)
    user = UserSerializer(read_only=True)
    payload = PayLoadSerializer(read_only=True)

    def get_credentials(self, attrs):
        return {
            'username': attrs.get('password'),
            'password': attrs.get('password')
        }


class ProfileNicknameDuplicateSerializer(serializers.Serializer):
    nickname = serializers.CharField(required=True)

    class Meta:
        fields = '__all__'
        error_status_codes = {
            status.HTTP_409_CONFLICT: None
        }

    def is_valid(self, raise_exception=False):
        if super(ProfileNicknameDuplicateSerializer, self).is_valid(raise_exception=raise_exception):
            model = get_user_model()
            site = get_site(self.context.get('request'))
            nickname = self.validated_data.get('nickname')

            try:
                model.objects.get(profile__nickname=nickname, site=site, is_active=True)
                if raise_exception:
                    raise ConflictException()
            except model.DoesNotExist:
                return True
            except model.MultipleObjectsReturned:
                raise ConflictException()
            return False
        else:
            return False


class UserDuplicateSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    ci = serializers.CharField(required=False)

    class Meta:
        fields = '__all__'
        error_status_codes = {
            status.HTTP_409_CONFLICT: None
        }

    def validate(self, attrs):

        if not attrs:
            error = 'Either ' + ' or '.join(self.fields.fields.keys()) + ' field is required.'
            raise serializers.ValidationError(error)

        return attrs

    def is_valid(self, raise_exception=False):
        if super(UserDuplicateSerializer, self).is_valid(raise_exception=raise_exception):
            model = get_user_model()
            site = get_site(self.context.get('request'))

            ci = self.validated_data.get('ci')
            email = self.validated_data.get('email')

            try:
                if ci:
                    model.objects.get_by_ci(ci=ci, request=self.context.get('request'))
                if email:
                    model.objects.get(email=email, site=site, is_active=True)
                if raise_exception:
                    raise ConflictException()
            except model.DoesNotExist:
                return True
            except model.MultipleObjectsReturned:
                raise ConflictException()
            return False
        else:
            return False


class UserActivationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivationLog
        fields = '__all__'


class ValidationEmailSerializer(serializers.Serializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    email = serializers.EmailField(required=True)
    activation_key = serializers.CharField(read_only=True)

    def is_valid(self, raise_exception=False):
        if super(ValidationEmailSerializer, self).is_valid(raise_exception=raise_exception):
            model = get_user_model()
            site = get_site(self.context.get('request'))
            try:
                instance = model.objects.get(email=self.validated_data.get('email'),
                                             is_active=True,
                                             site=site)
                if instance:
                    raise ValidationError({'email': 'already email address registered.'})
            except model.DoesNotExist:
                return True
        else:
            return False

    def save(self, *args, **kwargs):
        instance = self.validated_data.get('user')
        log_instance = instance.send_activation_email(self.context.get('request'),
                                                      confirm_type='validate_email',
                                                      send_to=self.validated_data.get('email'))
        self.validated_data['activation_key'] = log_instance.activation_key
        return instance


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def is_valid(self, raise_exception=False):
        if super(PasswordResetSerializer, self).is_valid(raise_exception=raise_exception):
            model = get_user_model()
            site = get_site(self.context.get('request'))
            try:
                instance = model.objects.get(email=self.validated_data.get('email'),
                                             is_active=True,
                                             site=site)
                self.validated_data.update({'user': instance})
                return True
            except:
                raise ValidationError({'email': 'unregistered email address.'})
        else:
            return False

    def save(self, *args, **kwargs):
        instance = self.validated_data.get('user')
        instance.send_activation_email(self.context.get('request'), confirm_type='password_reset')
        return instance


class TendencySerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    result = serializers.ListField()
    score = serializers.IntegerField(source='get_score', read_only=True)
    risk_type = serializers.IntegerField(source='get_risk_type', read_only=True)

    def is_valid(self, raise_exception=False):
        if super().is_valid(raise_exception=raise_exception):
            self.Meta.model.validate_score(self.validated_data.get('result'))
            return True
        else:
            return False

    class Meta:
        model = Tendency
        fields = '__all__'

    def save(self, **kwargs):
        instance = super().save(**kwargs)

        try:
            vendor_shinhan = VendorProperty.objects.get(code='shinhan').user
            qs = VendorTendency.objects.filter(user=instance.user, vendor=vendor_shinhan)
            if qs.exists():
                qs.update(result=instance.result)
            else:
                vendor_tendency = VendorTendency(user=instance.user, vendor=vendor_shinhan, result=instance.result)
                vendor_tendency.save()
        except Exception as e:
            logger.error(e)


class VendorTendencyMappingSerializer(serializers.Serializer):
    mapper_class_dic = {
        'kb': KBTendencyMaps,
        'shinhan': SHTendencyMaps
    }
    fount_tendency_response = serializers.ListField(help_text="파운트 투자성향 응답값")
    vendor_tendency_response = serializers.ListField(help_text="Vendor Tendency 응답 값")
    vendor_code = serializers.ChoiceField(help_text="Vendor 코드",
                                          choices=(("kb", "KB증권"), ("shinhan", "신한금융투자")))
    mapped_tendency_response = serializers.HiddenField(help_text="투자성향 응답 매핑 결과", default=[])

    def is_valid(self, raise_exception=False):
        super().is_valid(raise_exception=raise_exception)
        vendor_code = self.validated_data['vendor_code']
        vendor_mapper = self.mapper_class_dic[vendor_code]
        if vendor_mapper.INPUT_LENGTH != len(self.validated_data['vendor_tendency_response']):
            self._errors = {
                "detail": f"{vendor_code} tendency_response length diff, expected({vendor_mapper.INPUT_LENGTH}) "
                          f"!= input({len(self.validated_data['vendor_tendency_response'])})"}
            if raise_exception:
                raise ValidationError(self._errors)
            return False

    def to_representation(self, instance):
        vendor_code = instance['vendor_code']
        representation = super().to_representation(instance)
        answers = DotDict({'fount': instance['fount_tendency_response'],
                           vendor_code: instance['vendor_tendency_response']})
        representation['mapped_tendency_response'] = self.mapper_class_dic[vendor_code].do_mapping(answers)
        return representation


class VendorTendencySerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    result = serializers.ListField(help_text='응답 결과')
    vendor_code = serializers.CharField(help_text="vendor 코드", required=False, write_only=True)

    class Meta:
        model = VendorTendency
        fields = '__all__'

    def get_validators(self):
        return []

    def set_exist_instance_to_update(self):
        queryset = VendorTendency.objects.filter(user=self.validated_data['user'], vendor=self.validated_data['vendor'])
        counts = queryset.count()
        if counts == 0:
            pass
        elif counts == 1:
            self.instance = queryset.get()
        else:
            raise PreconditionFailed({'reason': 'violate unique together(user&vendor) constraint'})

    def save(self, **kwargs):
        # 3.0 기준 Tendency 응답값 여부 확인
        user = self.validated_data.get('user', None)
        if user is None:
            raise PreconditionFailed({'reason': "user must be defined"})

        if self.instance is None:
            self.set_exist_instance_to_update()

        if user.profile.tendency_response:
            vendor_tendency_mapping_serializer = VendorTendencyMappingSerializer(data={
                "vendor_code": self.validated_data['vendor'].vendor_props.code,
                "fount_tendency_response": user.profile.tendency_response,
                "vendor_tendency_response": self.validated_data['result'],
            })
            if vendor_tendency_mapping_serializer.is_valid():
                kwargs['result'] = vendor_tendency_mapping_serializer.data['mapped_tendency_response']
            else:
                logger.warning(f"Fail to mapping tendency: {vendor_tendency_mapping_serializer.errors}")
        instance = super().save(**kwargs)
        self.update_legacy_tendency(instance)

    def update_legacy_tendency(self, instance):
        _vendor = self.validated_data['vendor']
        vendor_code = _vendor.vendor_props.code

        if vendor_code == 'shinhan':
            _result = self.validated_data['result']
            _user = self.validated_data['user']

            qs = Tendency.objects.filter(user=instance.user)
            if qs.exists():
                qs.update(result=instance.result)
            else:
                legacy_tendency = Tendency(user=instance.user, result=instance.result)
                legacy_tendency.save()

    def is_valid(self, raise_exception=False):
        vendor = self.initial_data.get('vendor')
        vendor_code = self.initial_data.get('vendor_code')

        if vendor:
            pass
        elif vendor_code:
            self.initial_data['vendor'] = VendorProperty.objects.get(code=vendor_code).pk
        else:
            raise ValidationError({"error": "vendor or vendor code must be set"})
        self.initial_data.pop('vendor_code', None)

        if super().is_valid(raise_exception=raise_exception):
            vendor = self.instance.vendor if self.instance else self.validated_data.get('vendor')

            if not (vendor.is_vendor and vendor.vendor_props and vendor.vendor_props.code):
                raise ValidationError({'vendor': 'invalid vendor'})
            return True
        return False


class VendorTendencyCreateSerializer(VendorTendencySerializer):
    class Meta:
        model = VendorTendency
        exclude = ['forwarded_at']


class VendorTendencySubmitSerializer(VendorTendencySerializer):
    response = serializers.DictField(help_text='증권사 응답값', read_only=True)


class RefreshTokenSerializer(serializers.ModelSerializer):
    key = serializers.CharField()
    expiry = serializers.IntegerField(read_only=True)

    class Meta:
        model = ExpiringToken
        fields = ('key', 'expiry')

    def validate(self, attrs):
        attrs['key'] = self.instance.generate_key()
        return super().validate(attrs)

    def update(self, instance, validated_data):
        user = instance.user
        instance.delete()
        self.instance = ExpiringToken.objects.create(user=user)
        return self.instance


class ActivationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivationLog
        fields = '__all__'
