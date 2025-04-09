import logging
from django.db.models.signals import post_save, post_init
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from axes.signals import log_user_login_failed as axes_log_user_login_failed

from api.bases.agreements.models import Agreement, Type
from api.bases.tendencies.models import Type as TendencyType, Response, Answer
from api.bases.tendencies.utils import validate_score
from .models import User, Profile, Tendency, VendorProperty, VendorTendency
from common.decorators import disable_for_loaddata, skip_signal
from common.axes.signals import log_user_login_failed

log = logging.getLogger('django.server')


@receiver(post_save, sender=User)
@disable_for_loaddata
def create_user_info(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)
        if instance.is_staff or instance.is_vendor:
            pass
        else:
            for _agree_type in Type.objects.filter(code__in=['third_party', 'privacy_collect']):
                Agreement.objects.get_or_create(user=instance, type=_agree_type)
                Agreement.objects.get_or_create(user=instance, type=_agree_type)


@receiver(user_logged_in)
def online_user_logged_in(sender, request, user, **kwargs):
    user.is_online = True
    user.save()


@receiver(user_logged_out)
def offline_user_logged_out(sender, request, user, **kwargs):
    user.is_online = False
    user.save()
    try:
        user.auth_token.delete()
    except:
        pass


def insert_tendency(user, answers):
    t_instance = None

    if len(answers) == 10:
        # Note. fount current tendency
        t_instance = TendencyType.objects.get(code='fount')
    elif len(answers) == 7:
        # Note. fount v2 tendency
        t_instance = TendencyType.objects.get(code='fount_v2')
    elif len(answers) == 15:
        # Note. fount v1 tendency
        t_instance = TendencyType.objects.get(code='fount_v1')
        score, answers = validate_score(answers)

    if t_instance:
        questions = t_instance.questions.all().order_by('order')
        errors = []

        for item in questions:
            if not item.check_answer(answers[item.order], answer_type='index'):
                errors.append({
                    'answer_no': int(item.order),
                    'question': item.text,
                    'available_choices': item.choices,
                    'answer': answers[item.order]
                })

        if not errors:
            instance = Response.objects.create(user=user, type=t_instance)
            try:
                Answer.objects.bulk_create(
                    [Answer(
                        question=question,
                        answer=question.get_answer(answers[question.order], answer_type='index'),
                        score=question.get_score(answers[question.order], answer_type='index'),
                        response=instance) for question in
                        questions
                    ])
                instance.update_score()

                return instance
            except Exception as e:
                instance.delete()
                log.error(e)
                return None


@receiver(post_save, sender=Tendency)
@skip_signal()
def update_risk_type(sender, instance, created, **kwargs):
    try:
        # Note. fount_v1 tendency
        # 투자성향분석값(v1) 신규 저장 및 수정될때마다 응답값 별도 적재 처리
        tendency_instance = insert_tendency(instance.user, instance.result)

        profile = instance.user.profile
        if not profile.tendency_response:
            if tendency_instance:
                profile.risk_type = tendency_instance.risk_type
            else:
                profile.risk_type = instance.get_risk_type()
            profile.save(update_fields=['risk_type'])
    except Exception as e:
        log.error(e)


@receiver(post_save, sender=VendorProperty)
def update_is_vendor_status(sender, instance, created, **kwargs):
    try:
        if created:
            instance.user.is_vendor = True
            instance.user.save(update_fields=['is_vendor'])
    except Exception as e:
        log.error(e)


@receiver(post_init, sender=Profile)
def pre_auto_migrate_tendency_response(instance, *args, **kwargs):
    # Note. origin 투성분값 메모리 저장
    instance._tendency_response = instance.tendency_response


@receiver(post_save, sender=Profile)
@skip_signal()
def post_auto_migrate_tendency_response(sender, instance, created, **kwargs):
    try:
        # Note. 응답값이 변경된 경우 투자성향분석값 적재 처리
        if instance._tendency_response != instance.tendency_response:
            answers = instance.tendency_response
            tendency_instance = insert_tendency(instance.user, answers)

            if tendency_instance:
                instance.risk_type = tendency_instance.risk_type
                instance.skip_signal = True
                instance.save(update_fields=['risk_type'])

    except Exception as e:
        log.error(e)


@receiver(post_save, sender=Response)
def post_auto_migrate_response_risk_type(sender, instance, created, **kwargs):
    try:
        if instance.risk_type is not None:
            answers = list(instance.answers.values_list('answer', flat=True))

            profile = instance.user.profile
            profile.risk_type = instance.risk_type
            profile.tendency_response = answers
            profile.skip_signal = True
            profile.save(update_fields=['risk_type', 'tendency_response'])

            tendency = instance.user.tendency
            tendency.result = answers
            tendency.skip_signal = True
            tendency.save(update_fields=['result'])
    except Exception as e:
        log.error(e)


user_login_failed.disconnect(axes_log_user_login_failed)
