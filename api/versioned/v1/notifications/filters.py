import django_filters
from django_filters.widgets import RangeWidget, SuffixedMultiWidget
from django.contrib.auth import get_user_model

from api.bases.notifications.models import Subscribe, Topic


class SubscribeFilter(django_filters.FilterSet):
    user = django_filters.UUIDFilter(field_name='user', help_text='유저명', required=True)

    class Meta:
        model = Subscribe
        fields = ['user']
