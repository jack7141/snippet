import json
import ast

from django.db import models
from django.core.serializers.json import DjangoJSONEncoder


class JSONField(models.TextField):
    def to_python(self, value):
        if value == "":
            return None

        try:
            if isinstance(value, str):
                return json.loads(value)
        except json.JSONDecodeError:
            return json.loads(value.replace('"', '\\"').replace("'", '"'))
        except ValueError:
            pass
        return value

    def from_db_value(self, value, *args):
        return self.to_python(value)

    def get_db_prep_save(self, value, *args, **kwargs):
        if value == "":
            return None
        if isinstance(value, dict):
            value = json.dumps(value, cls=DjangoJSONEncoder)
        return value


class ListField(models.TextField):

    def to_python(self, value):
        if not value:
            value = []

        if isinstance(value, list):
            return value

        try:
            return ast.literal_eval(value)
        except ValueError:
            return json.loads(value)

    def from_db_value(self, value, *args):
        return self.to_python(value)

    def get_db_prep_save(self, value, *args, **kwargs):
        if value == "":
            return None
        if isinstance(value, list):
            value = json.dumps(value, cls=DjangoJSONEncoder)
        return value

    def value_to_string(self, obj):
        value = self._get_val_from_obj(obj)
        return self.get_prep_value(value)
