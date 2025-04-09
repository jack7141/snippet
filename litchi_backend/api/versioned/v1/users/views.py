import logging

from cryptography.fernet import Fernet, InvalidToken

from rest_framework import parsers, filters, viewsets, generics
from rest_framework.serializers import Serializer
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_200_OK, HTTP_201_CREATED
from rest_framework.exceptions import ParseError, NotAcceptable
from rest_framework.generics import get_object_or_404
from rest_framework.throttling import ScopedRateThrottle

from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.signals import user_logged_in
from django.contrib.sites.shortcuts import get_current_site
from django.views.decorators.cache import never_cache
from django.template.response import TemplateResponse

from axes.utils import reset as axes_reset
from drf_openapi.utils import view_config

from api.bases.users.models import ActivationLog, Profile, Tendency, VendorTendency, ExpiringToken, Image
from api.bases.contracts.adapters import fep_adapter
from api.bases.contracts.models import get_contract_status
from common.permissions import IsOwnerOrAdminUser, IsOwner
from common.viewsets import MappingViewSetMixin
from common.exceptions import PreconditionFailed
from common.utils import DotDict

from .serializers import (
    ActivationLogSerializer,
    UserSerializer,
    UserCreateSerializer,
    UserLoginSerializer,
    UserRetrieveSerializer,
    UserDuplicateSerializer,
    UserUpdateSerializer,
    UserPasswordChangeSerializer,
    PasswordResetSerializer,
    ProfileSerializer,
    ProfileRetrieveSerializer,
    ProfileNicknameDuplicateSerializer,
    TendencySerializer,
    ValidationEmailSerializer,
    VendorTendencySerializer,
    VendorTendencyCreateSerializer,
    VendorTendencySubmitSerializer,
    RefreshTokenSerializer,
    ImageSerializer
)

logger = logging.getLogger('django.server')


class UserViewSet(viewsets.ModelViewSet):
    """    
    list:[유저 목록 조회]
    유저 목록을 조회합니다. 조회시 email을 기준으로 검색도 가능합니다.

    create:[유저 생성]
    유저를 생성한다.

    retrieve:[유저 상세 조회]
    유저의 상세 정보를 조회합니다.

    partial_update:[유저 정보 업데이트]
    유저 정보를 업데이트 합니다.

    destroy:[유저 삭제]
    유저를 삭제합니다. 삭제시 해당 유저에 관련된 모든 데이터가 삭제 됩니다.

    health_check:[유저 토큰 상태 체크]
    현재 유저의 토큰 상태를 확인하고, 토큰의 만료시간을 연장합니다.

    logout:[유저 로그아웃]
    유저를 로그아웃 처리합니다.
    """

    queryset = get_user_model().objects.all().prefetch_related('groups', 'user_permissions')
    serializer_class = UserSerializer
    filter_backends = (filters.SearchFilter,)
    search_fields = ('^email',)

    serializer_action_map = {
        'retrieve': UserRetrieveSerializer,
        'partial_update': UserUpdateSerializer,
        'create': UserCreateSerializer,
        'health_check': Serializer,
        'logout': Serializer
    }
    permission_classes = [IsOwner]
    permission_classes_map = {
        'create': [AllowAny],
        'destroy': [IsOwnerOrAdminUser],
        'health_check': [IsAuthenticated],
        'logout': [IsAuthenticated]
    }

    def get_permissions(self):
        permission_classes = self.permission_classes
        if self.permission_classes_map.get(self.action, None):
            permission_classes = self.permission_classes_map[self.action]

        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.serializer_action_map.get(self.action, None):
            return self.serializer_action_map[self.action]
        return self.serializer_class

    def perform_create(self, serializer):
        serializer.save()
        axes_reset(username=serializer.data.get('email'))

    @never_cache
    def health_check(self, request, *args, **kwargs):
        return Response(status=HTTP_200_OK)

    @never_cache
    def logout(self, request, *args, **kwargs):
        logout(request)
        return Response(status=HTTP_200_OK)

    def perform_destroy(self, instance):
        """
        해지된 계약의 유무에 따라 회원 탈퇴 처리를 결정합니다.
        :param instance:
        :return:
        """
        if instance.contract_set.filter(is_canceled=False).exists():
            raise NotAcceptable(detail='contracts are not canceled')
        instance.is_active = False
        instance.deactivated_at = timezone.now()
        instance.save()


class UserProfileViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOwnerOrAdminUser]
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    owner_field = 'user'


class UserProfileImageViewSet(MappingViewSetMixin, viewsets.ModelViewSet):
    """
    created: [유저 프로파일 아바타 생성]
    """
    serializer_class = ImageSerializer
    parser_classes = (parsers.MultiPartParser, parsers.JSONParser)
    queryset = Image.objects.all()

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def get_object(self):
        return self.get_queryset().get()


class UserProfileOnwerViewSet(MappingViewSetMixin, viewsets.ModelViewSet):
    """
    retrieve:[유저 프로파일 조회]

    ** 이동통신사(mobile_carrier) 코드 정의 **

    | **mobile_carrier** | **정의**
    |:------:|:----------
    |01| SKT
    |02| KT
    |03| LG U+
    |04| 알뜰폰 - SKT
    |05| 알뜰폰 - KT
    |06| 알뜰폰 - LG U+

    partial_update: [유저 프로파일 업데이트]

    ** 이동통신사(mobile_carrier) 코드 정의 ** : [유저 프로파일 조회] 참조

    ci필드의 경우 설정된 값이 있으면 조회만 가능합니다.
    """
    serializer_class = ProfileSerializer
    queryset = Profile.objects.all()
    serializer_action_map = {
        'retrieve': ProfileRetrieveSerializer
    }

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def get_object(self):
        return self.get_queryset().get()


class UserPasswordChangeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOwnerOrAdminUser]
    queryset = get_user_model().objects.all()
    serializer_class = UserPasswordChangeSerializer


class UserLoginTokenViewSet(viewsets.GenericViewSet):
    """
    create:[로그인]
    일정 횟수(**기본:5회**)만큼 연속 로그인 실패시 계정이 잠깁니다.<br>
    잠긴 계정은 일정 시간(**기본:30분**) 기준으로 잠김 해제됩니다.<br>
    토큰의 만료 시점은 서버에서 관리되며, 토큰 만료시 권한이 필요한 API를 호출하는 경우 status 403이 전달됩니다.<br>
    중복 로그인 허용됩니다.<br>
    force_login 사용시 기존 발급 토큰은 삭제됩니다. (중복 로그인 방지 효과)<br>

    **로그인 실패시(401)에 대한 코드 정의**
    * authentication_failed : 아이디/비밀번호 오류
    * not_authenticated : 비활성화 유저
    """
    permission_classes = [AllowAny]
    serializer_class = UserLoginSerializer

    def get_serializer_context(self):
        return {
            'request': self.request,
            'view': self,
            '_request': self._request
        }

    def dispatch(self, request, *args, **kwargs):
        self._request = request
        return super(UserLoginTokenViewSet, self).dispatch(request, *args, **kwargs)

    @never_cache
    def create(self, request, *args, **kwargs):
        encrypt = 'encrypted' in request.query_params

        if encrypt:
            _key = getattr(settings, 'ENCRYPT_KEY', str(Fernet.generate_key()))
            _f = Fernet(_key.encode())
            try:
                request.data.update({'password': _f.decrypt(request.data.get('password').encode()).decode('utf-8')})
            except InvalidToken:
                raise ParseError('Token parse error')

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            user = serializer.data.get('user')
            axes_reset(username=user.get('email'))

            data = serializer.data
            site = get_current_site(request)

            _user = get_user_model().objects.get(is_active=True, email=user.get('email'), site=site)

            user_logged_in.send(sender=_user.__class__, request=request, user=_user)

            return Response(data)
        return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)


class ProfileNicknameDuplicateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    duplicate:[별명 중복 검사]
    별명 중복 여부를 확인합니다.
    """
    serializer_class = ProfileNicknameDuplicateSerializer

    def duplicate(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(status=HTTP_200_OK)


class UserDuplicateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    duplicate:[유저 중복 검사]
    email 기준으로 유저의 중복여부를 확인합니다.
    """
    permission_classes = [AllowAny]
    serializer_class = UserDuplicateSerializer

    def duplicate(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(status=HTTP_200_OK)


class ActivationLogViewSet(viewsets.ModelViewSet):
    """
    retrieve:[인증 처리]
    인증 타입 별 Activation Log를 조회 합니다.
    """
    queryset = ActivationLog.objects.all()
    serializer_class = ActivationLogSerializer
    lookup_field = 'activation_key'


class UserConfirmedViewSet(viewsets.ModelViewSet):
    """
    retrieve:[인증 처리]
    인증 메일에 포함된 링크를 통해 인증 종류에 맞는 페이지를 전달합니다.

    create:[인증 확인]
    비밀번호 변경 인증메일을 받은 경우 사용되며, 결과값으로 페이지가 전달됩니다.
    """
    permission_classes = [AllowAny]
    serializer_class = Serializer
    queryset = ActivationLog.objects.all()
    lookup_field = 'activation_key'

    template_map = {
        'signup': 'member_join.html',
        'password_reset': 'password_reset_confirm.html',
        'validate_email': 'validate_email_confirm.html'
    }

    parser_classes = (parsers.JSONParser, parsers.FormParser,)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        valid_link = False
        context = {}
        template_name = self.template_map.get(instance.confirm_type)

        if timezone.now() <= instance.expires:
            valid_link = not instance.is_confirmed
            try:
                if instance.confirm_type == 'signup':
                    instance.is_confirmed = True
                    instance.save()
                    if instance.user.is_active:
                        raise ValueError()
                    instance.user.is_active = True
                    instance.user.save()
                elif instance.confirm_type == 'validate_email':
                    instance.is_confirmed = True
                    instance.save()
                else:
                    user = instance.user
                    form = SetPasswordForm(user)
                    context.update({'form': form})
            except:
                valid_link = False
        else:
            if instance.confirm_type == 'validate_email':
                template_name = 'validate_email_expires.html'


        context.update({'user': instance.user, 'valid_link': valid_link})
        return TemplateResponse(request, template_name, context=context)

    def create(self, request, *args, **kwargs):
        instance = self.get_object()
        user = instance.user
        form = SetPasswordForm(user, request.POST)
        valid_link = not instance.is_confirmed
        error_code = None

        if valid_link and form.is_valid():
            form.save()
            instance.is_confirmed = True
            instance.save()
            axes_reset(username=user.email)
            return TemplateResponse(request, 'password_reset_complete.html')
        else:
            errors = form.errors['new_password2']

            for error in errors.data:
                if error.code in ('password_already_used', 'password_mismatch'):
                    error_code = error.code

        context = {
            'valid_link': valid_link,
            'form': form,
            'error_code': error_code
        }

        return TemplateResponse(request, 'password_reset_confirm.html', context)


class PasswordResetEmailSendViewSet(viewsets.ModelViewSet):
    """
    create:[비밀번호 변경 요청]
    비밀번호를 분실하였을때 비밀번호 변경을 하기 위한 인증 메일 요청을 하기위해 사용됩니다.
    """
    permission_classes = [AllowAny]
    serializer_class = PasswordResetSerializer


class ValidationEmailSendViewSet(viewsets.ModelViewSet):
    """
    create:[이메일 변경 요청]
    이메일을 변경하기 위해 이메일을 발송요청 합니다.
    """
    serializer_class = ValidationEmailSerializer
    throttle_classes_map = {
        'create': (ScopedRateThrottle,),
    }
    throttle_scope = 'validate_email'


class TendencyViewSet(viewsets.ModelViewSet):
    """
    retrieve: [성향분석 결과 조회]

    ** 투자성향 분석 기준 **

    | **항목(Index)** | **항목 명** | **배점 기준** | ** 예시값 ** | ** 비고 **
    |:------:|:----------:|:----------:|:----------:
    |0| 소득상태 | 1:1, 2:3, 3:5 | 2 |-
    |1| 투자자금의 비중 | 1:1, 2:2, 3:3, 4:4, 5:5 | 4 | -
    |2| 3-1 상품종류 Array | 6 | [1,2,3,4] | 3-(1~3)중복응답인 경우 가장 높은 점수로 배점
    |3| 3-1 투자경험 | 1:1, 2:3, 3:5 | 2 ||
    |4| 3-2 상품종류 Array | 3 | [1,2,3,4,5,6] ||
    |5| 3-2 투자경험 | 1:1, 2:3, 3:5 | 2 ||
    |6| 3-3 상품종류 Array| 1 | [1,2,3] ||
    |7| 3-3 투자경험 | 1:1, 2:3, 3:5 | 2 ||
    |8| 투자경험 여부 | 0:True, 1:False | 0| 입력값이 1인경우 3-(1~3) 결과값 무시
    |9| 투자 수익 및 위험에 대한 태도 | 1:1, 2:3, 3:5 | 2 | -
    |10| 기대수익률 및 손실감내도 | 1:1, 2:3, 3:4, 3:5 | 3 | -
    |11| 금융지식 수준/이해도 | 1:1, 2:2, 3:3, 4:4 | 3 | -

    ** 투자성향 분류 **

    | **투자성향 분류 조건** | **투자성향**
    |:------:|:----------:
    |10점 이하| 안정형(0)
    |11점 이상 ~ 15점 이하| 안정추구형(1)
    |16점 이상 ~ 20점 이하| 위험중립형(2)
    |21점 이상 ~ 25점 이하| 적극투자형(3)
    |26점 이상| 공격투자형(4)

    partial_update: [성향분석 결과 저장]
    """
    queryset = Tendency.objects.all()
    serializer_class = TendencySerializer

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def get_object(self):
        try:
            return self.get_queryset().get()
        except:
            raise generics.Http404

    def update(self, request, *args, **kwargs):
        try:
            self.get_object()
            return super().update(request, *args, **kwargs)
        except generics.Http404 as e:
            return self.create(request, *args, **kwargs)


class VendorTendencyViewSet(MappingViewSetMixin,
                            viewsets.ModelViewSet):
    """
    list:[추가 투자성햔분석 목록 조회]

    retrieve:[추가 투자성향분석 상세 조회]

    create:[추가 투자성향분석 생성]

    **API 사용 사전 조건**
    - 기본 투자성향 분석정보 있어야함.
    - vendor는 vendor code를 부여 받은 상태여야함.

    기본 질문 이외의 증권사별로 추가 투자성향분석 정보가 필요한 경우 증권사별 추가 질문에 대한 답변을 저장합니다. </br>
    저장 시점에 증권사로 답변 정보가 전달됩니다. </br>
    저장된 정보는 유저 Profile의 risk\_type에 영향이 없습니다.(Score 계산 X) </br>

    ** KB ** ([참조](https://stage-fep-api.mkfount.com/api/v1/swagger/#/kb/kb_customer_tendency_create))

    | **항목(Index)** | **항목명** | **타입** | **범위** | **예시값**
    |:--------------:|:--------:|:-------:|:------:|:----------:
    |0| 투자경험이 있는 금융투자상품 | Integer | 1~5 | 1
    |1| 금융투자상품 투자경험기간 | Integer | 1~5 | 5
    |2| 투자하는 자금의 투자예정기간 | Integer | 1~5 | 3
    |3| 재산 현황 - 여유자금 | Integer | 1~5 | 2
    |4| 총 금융자산대비 총 투자상품의 비중 | Integer | 1~5 | 4
    |5| 재산 상황 - 월소득 | Integer | 1~5 | 1
    |6| 연령 | Integer | 1~5 | 2

    partial_update:[추가 투자성향분석 수정]

    submit:[투자성향분석 결과 제출]

    성향분석 결과를 업체에 전달합니다. 업체에 제3자 제공동의가 되어있어야 합니다. (주문대리인 등록시 자동 등록됨) </br>
    응답값의 **response** 필드는 업체측 응답값입니다. </br>
    정상 제출된 경우 forwarded_at 값이 갱신됩니다.

    ** KB 응답결과값 ** ([참조](https://stage-fep-api.mkfount.com/api/v1/swagger/#/kb/kb_customer_tendency_create))
    """
    queryset = VendorTendency.objects.select_related('user', 'vendor').all().order_by('-created_at')
    serializer_class = VendorTendencySerializer

    serializer_action_map = {
        'create': VendorTendencyCreateSerializer,
        'submit': Serializer
    }

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        try:
            instance = serializer.instance
            vendor = instance.vendor

            # KB인 경우에만 처리
            if vendor.vendor_props.code == 'kb':
                self.forward_to_vendor(tendency_response=instance, vendor_code=vendor.vendor_props.code)
        except Exception:
            pass

        return Response(serializer.data, status=HTTP_201_CREATED, headers=headers)

    @view_config(response_serializer=VendorTendencySubmitSerializer)
    def submit(self, request, *args, **kwargs):
        instance = self.get_object()
        vendor = instance.vendor

        resp = self.forward_to_vendor(tendency_response=instance, vendor_code=vendor.vendor_props.code)
        return Response(resp)

    @staticmethod
    def forward_to_vendor(tendency_response, vendor_code):
        ci = tendency_response.user.profile.ci

        # 제3자 정보제공동의 처리(계약 등록 시점에 동의 받은걸로 취급하나, 전송 시점에 동의처리후 전송)
        fep_adapter.register_third_party_agreement(vendor_code, ci)
        resp = fep_adapter.get_access_token(vendor_code, ci)

        # FEP 시스템 응답 오류인경우 처리
        if not resp:
            raise PreconditionFailed(detail={
                'status': 9999,
                'message': 'fep system error fail to issue access_token'
            })

        access_data = DotDict(resp.json())

        # KB 시스템 오류인경우
        if not access_data.dataBody.access_token:
            raise PreconditionFailed(detail={
                'status': get_contract_status(type='vendor_auth_fail').name,
                'message': 'request authentication token failed.',
                'response': access_data.dataHeader
            })

        resp_result = tendency_response.result
        endpoint = 'customer/tendency'
        data = {
            "ci_valu": ci,
            "access_token": access_data.dataBody.access_token,
        }
        extra = {}
        if len(resp_result) == 15 and all([type(resp_result[idx]) == list for idx in [4, 5, 7]]):
            endpoint = 'customer/invest-tendency'
            invest_exp = max(resp_result[5]) - 1
            birth_date = tendency_response.user.profile.birth_date
            # 한국나이로 계산(만 나이 X)
            age = timezone.now().year - birth_date.year + 1
            age_flag = 1
            # 19세 이하 = 1
            # 20세 ~ 40세 = 2
            # 41세 ~ 50세 = 3
            # 51세 ~ 64세 = 4
            # 65세 이상 = 5
            if 20 <= age <= 40:
                age_flag = 2
            elif 41 <= age <= 50:
                age_flag = 3
            elif 51 <= age <= 64:
                age_flag = 4
            elif age >= 65:
                age_flag = 5
            extra = {
                "age_flag": age_flag,
                "invest_period_flag": resp_result[0],  # index 0
                "expected_income_flag": resp_result[1],  # index 1
                "income_flag": resp_result[2],  # index 2
                "financial_asset_per_capital_flag": resp_result[3],  # index 3
                "insurance_per_financial_asset": resp_result[4][0],  # index 4[0] 보장성
                "invest_per_financial_asset": resp_result[4][1],  # index 4[1] 투자성
                "loan_per_financial_asset": resp_result[4][2],  # index 4[2] 대출성
                "etc_per_financial_asset": resp_result[4][3],  # index 4[3] 기타
                "invest_experience_flag": None if invest_exp == 0 else invest_exp,
                "invest_experience_period_flag": resp_result[6],  # index 6
                "derivative_invest_period_year": resp_result[7][0],  # index 7[0]
                "derivative_invest_period_month": resp_result[7][1],  # index 7[1]
                "invest_object_flag": resp_result[8],  # index 8
                "acquisition_object_flag": resp_result[9],  # index 9
                # "acquisition_etc_object": "string",         # if index 9 == 6 -> empty string
                "financial_knowledge_flag": resp_result[10],  # index 10
                "expected_return_flag": resp_result[11],  # index 11
                "loss_level_flag": resp_result[12],  # index 12
                "weak_finance_customer_flag": resp_result[13] - 1,
                "investor_info_check_flag": resp_result[14],  # index 14
            }
        else:
            extra = {
                "investor_recommend_flag": 0,
                "answers": tendency_response.user.tendency.result,
                "extra_answers": tendency_response.result
            }

        resp = fep_adapter.request(f'/api/v1/{vendor_code}/{endpoint}', dict(data, **extra))
        if not resp:
            raise PreconditionFailed(detail=resp.json())

        # 전송 완료시점 저장
        tendency_response.forwarded_at = timezone.now()
        tendency_response.save()
        tendency_response.response = resp.json()
        serializer = VendorTendencySubmitSerializer(tendency_response)
        return serializer.data


class RefreshTokenViewSet(viewsets.ModelViewSet):
    queryset = ExpiringToken.objects.all()
    serializer_class = RefreshTokenSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return ExpiringToken.objects.filter(user__site=get_current_site(self.request))

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        obj = get_object_or_404(queryset, **self.request.data)
        return obj
