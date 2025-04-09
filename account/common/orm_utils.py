import datetime

from django.db import models

def bulk_create_or_update(model_class, objs, match_field_names, update_field_names=None, exclude_field_names=None):
    def _get_filter_query(objs):
        return models.Q(
            *(
                models.Q(**{match_field.name: getattr(obj, match_field.name) for match_field in match_fields}) for obj in objs
            ),
            _connector=models.Q.OR,
        )
    def _get_match_values_by_obj(obj):

        ret = list()
        for match_field in match_fields:
            value = match_field.value_from_object(obj)
            if type(value) == datetime.datetime:
                value = value.date()

            if type(value) == datetime.date:
                value = str(value)

            ret.append(value)
        return tuple(ret)

    if model_class is None:
        raise ValueError()

    if update_field_names is None and exclude_field_names is None:
        raise ValueError()

    if len(objs) == 0:
        return 0, 0

    if exclude_field_names is not None:
        update_field_names = [entry.name for entry in model_class._meta.get_fields() if entry.name not in exclude_field_names]

    match_fields = [model_class._meta.get_field(name) for name in match_field_names]
    update_objs = model_class.objects.filter(_get_filter_query(objs))
    obj_map = {_get_match_values_by_obj(obj): obj for obj in objs}

    for entry in update_objs:
        obj = obj_map[_get_match_values_by_obj(entry)]
        for update_field in update_field_names:
            setattr(entry, update_field, getattr(obj, update_field))

        del obj_map[_get_match_values_by_obj(entry)]

    created_objs = []
    for obj in obj_map.values():
        created_objs.append(obj)

    model_class.objects.bulk_update(update_objs, update_field_names)
    model_class.objects.bulk_create(created_objs)
    return len(created_objs), len(update_objs)
