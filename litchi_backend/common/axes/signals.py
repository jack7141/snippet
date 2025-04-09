import logging
from django.dispatch import receiver
from django.contrib.auth.signals import user_login_failed
from django.core.cache import cache
from django.utils import timezone

from axes.conf import settings
from axes.models import AccessAttempt
from axes.utils import get_client_str, get_ip, query2str
from axes.signals import user_locked_out

from common.axes.attempts import get_cache_key, get_cache_timeout, get_user_attempts, is_user_lockable, ip_in_whitelist

log = logging.getLogger('django.server')


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    """ Create an AccessAttempt record if the login wasn't successful
    """
    ip_address = get_ip(request)
    username = credentials['username']
    user_agent = request.META.get('HTTP_USER_AGENT', '<unknown>')[:255]
    path_info = request.META.get('PATH_INFO', '<unknown>')[:255]
    http_accept = request.META.get('HTTP_ACCEPT', '<unknown>')[:1025]

    if settings.AXES_NEVER_LOCKOUT_WHITELIST and ip_in_whitelist(ip_address):
        return

    failures = 0
    attempts = get_user_attempts(request)
    cache_hash_key = get_cache_key(request)
    cache_timeout = get_cache_timeout()

    failures_cached = cache.get(cache_hash_key)
    if failures_cached is not None:
        failures = failures_cached
    else:
        for attempt in attempts:
            failures = max(failures, attempt.failures_since_start)

    # add a failed attempt for this user
    failures += 1
    cache.set(cache_hash_key, failures, cache_timeout)

    # has already attempted, update the info
    if len(attempts):
        for attempt in attempts:
            attempt.get_data = '%s\n---------\n%s' % (
                attempt.get_data,
                query2str(request.GET),
            )
            attempt.post_data = '%s\n---------\n%s' % (
                attempt.post_data,
                query2str(request.POST)
            )
            attempt.http_accept = http_accept
            attempt.path_info = path_info
            attempt.failures_since_start = failures
            attempt.attempt_time = timezone.now()
            attempt.save()

            fail_msg = 'AXES: Repeated login failure by {0}.'.format(
                get_client_str(username, ip_address, user_agent, path_info)
            )
            count_msg = 'Count = {0} of {1}'.format(
                failures, settings.AXES_FAILURE_LIMIT
            )
            log.info('{0} {1}'.format(fail_msg, count_msg))
    else:
        # Record failed attempt. Whether or not the IP address or user agent is
        # used in counting failures is handled elsewhere, so we just record
        # everything here.
        AccessAttempt.objects.create(
            user_agent=user_agent,
            ip_address=ip_address,
            username=username,
            get_data=query2str(request.GET),
            post_data=query2str(request.POST),
            http_accept=http_accept,
            path_info=path_info,
            failures_since_start=failures,
        )

        log.info(
            'AXES: New login failure by {0}. Creating access record.'.format(
                get_client_str(username, ip_address, user_agent, path_info)
            )
        )

    # no matter what, we want to lock them out if they're past the number of
    # attempts allowed, unless the user is set to notlockable
    if (
            failures >= settings.AXES_FAILURE_LIMIT and
            settings.AXES_LOCK_OUT_AT_FAILURE and
            is_user_lockable(request)
    ):
        log.warning('AXES: locked out {0} after repeated login attempts.'.format(
            get_client_str(username, ip_address, user_agent, path_info)
        ))

        # send signal when someone is locked out.
        user_locked_out.send(
            'axes', request=request, username=username, ip_address=ip_address
        )
