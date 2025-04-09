from celery.five import monotonic
from contextlib import contextmanager
from django.core.cache import cache

LOCK_EXPIRE = 60 * 10


@contextmanager
def memcache_lock(lock_id, oid, exp=LOCK_EXPIRE):
    timeout_at = monotonic() + exp - 3
    # cache.add fails if the key already exists
    status = cache.add(lock_id, oid, exp)
    try:
        yield status
    finally:
        # memcache delete is very slow, but we have to use it to take
        # advantage of using add() for atomic locking
        if monotonic() < timeout_at and status:
            # don't release the lock if we exceeded the timeout
            # to lessen the chance of releasing an expired lock
            # owned by someone else
            # also don't release the lock if we didn't acquire it
            # print('cache delete!!')
            cache.delete(lock_id)
