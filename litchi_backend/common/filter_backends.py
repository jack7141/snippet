from django_filters.rest_framework.backends import DjangoFilterBackend


class MappingDjangoFilterBackend(DjangoFilterBackend):
    def get_filter_class(self, view, queryset=None):
        filter_action_map = getattr(view, 'filter_action_map', {})
        filter_fields_action_map = getattr(view, 'filter_fields_action_map', {})
        filter_class = filter_action_map.get(view.action, None)
        filter_fields = filter_fields_action_map.get(view.action, None)

        if filter_class:
            filter_model = filter_class.Meta.model

            assert issubclass(queryset.model, filter_model), \
                'FilterSet model %s does not match queryset model %s' % \
                (filter_model, queryset.model)

            return filter_class

        if filter_fields:
            MetaBase = getattr(self.default_filter_set, 'Meta', object)

            class AutoFilterSet(self.default_filter_set):
                class Meta(MetaBase):
                    model = queryset.model
                    fields = filter_fields

            return AutoFilterSet

        return None
