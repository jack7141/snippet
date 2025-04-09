import redis
import ast


class RedisCache(redis.StrictRedis):
    def set(self, name, value, ex=None, px=None, nx=False, xx=False, keepttl=False):
        if isinstance(value, dict):
            value = str(value)
        return super().set(
            name=name, value=value, ex=ex, px=px, nx=nx, xx=xx, keepttl=keepttl
        )

    def get(self, name) -> dict or str:
        value = super().get(name=name)
        if isinstance(value, bytes):
            value = value.decode()
        try:
            value = ast.literal_eval(value)
            return value
        except ValueError:
            return value
