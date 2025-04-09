from functools import wraps


def cached_property(method):
    prop_name = '_{}'.format(method.__name__)

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
        if kwargs.get('raw'):
            return
        signal_handler(*args, **kwargs)

    return wrapper


def skip_signal():
    def _skip_signal(signal_func):
        @wraps(signal_func)
        def _decorator(sender, instance, **kwargs):
            if hasattr(instance, 'skip_signal'):
                return None
            return signal_func(sender, instance, **kwargs)

        return _decorator

    return _skip_signal
