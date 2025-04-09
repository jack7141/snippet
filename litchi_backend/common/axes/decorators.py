import json
from datetime import timedelta

from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import render

from axes.conf import settings
from axes.utils import iso8601

from common.axes.attempts import get_username


def lockout_context(request):
    context = {
        'failure_limit': settings.AXES_FAILURE_LIMIT,
        'username': get_username(request)
    }

    cool_off = settings.AXES_COOLOFF_TIME
    if cool_off:
        if (isinstance(cool_off, int) or isinstance(cool_off, float)):
            cool_off = timedelta(hours=cool_off)

        context.update({
            'cooloff_time': iso8601(cool_off)
        })

    return context


def lockout_response(request):
    context = {
        'failure_limit': settings.AXES_FAILURE_LIMIT,
        'username': get_username(request)
    }

    cool_off = settings.AXES_COOLOFF_TIME
    if cool_off:
        if (isinstance(cool_off, int) or isinstance(cool_off, float)):
            cool_off = timedelta(hours=cool_off)

        context.update({
            'cooloff_time': iso8601(cool_off)
        })

    if request.is_ajax():
        return HttpResponse(
            json.dumps(context),
            content_type='application/json',
            status=403,
        )

    elif settings.AXES_LOCKOUT_TEMPLATE:
        return render(
            request, settings.AXES_LOCKOUT_TEMPLATE, context, status=403
        )

    elif settings.AXES_LOCKOUT_URL:
        return HttpResponseRedirect(settings.AXES_LOCKOUT_URL)

    else:
        msg = 'Account locked: too many login attempts. {0}'
        if settings.AXES_COOLOFF_TIME:
            msg = msg.format('Please try again later.')
        else:
            msg = msg.format('Contact an admin to unlock your account.')

        return HttpResponse(msg, status=403)
