import reversion
from functools import wraps


def cached_property(method):
    prop_name = "_{}".format(method.__name__)

    def wrapped_func(self, *args, **kwargs):
        if not hasattr(self, prop_name):
            try:
                setattr(self, prop_name, method(self, *args, **kwargs))
            except:
                setattr(self, prop_name, None)
        return getattr(self, prop_name)

    return property(wrapped_func)


def disable_for_loaddata(signal_handler):
    """
    Decorator that turns off signal handlers when loading fixture data.
    """

    @wraps(signal_handler)
    def wrapper(*args, **kwargs):
        if kwargs.get("raw"):
            return
        signal_handler(*args, **kwargs)

    return wrapper


def get_diffs(instance):
    diffs = []
    for k, prev_v in instance._init_fields.items():
        v = getattr(instance, k)
        if v != prev_v:
            diffs.append(f"{k}: {prev_v}->{v}")
    if diffs:
        return "\n".join(diffs)
    else:
        return "no changes"


def reversion_diff(func):
    def wrapped_func(instance, *args, **kwargs):
        with reversion.create_revision():
            if instance._state.adding:
                msg = "created"
            else:
                msg = get_diffs(instance=instance)
            reversion.set_comment(msg)
            return func(instance, *args, **kwargs)

    return wrapped_func
