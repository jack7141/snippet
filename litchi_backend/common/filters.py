import operator
from functools import reduce
import django_filters

from rest_framework import filters
from rest_framework.settings import api_settings
from rest_framework.compat import (
    coreapi, coreschema, distinct
)

from django import forms
from django.db import models
from django.utils import six
from django.utils.encoding import force_text
from .filterset import FilterSet
from .widgets import NullBooleanSelect


class MultipleSearchFilter(filters.SearchFilter):

    def __initialize(self, view):
        setattr(self, 'search_param', getattr(view, 'search_param', api_settings.SEARCH_PARAM))
        setattr(self, 'search_required', getattr(view, 'search_required', False))

    def filter_queryset(self, request, queryset, view):
        self.__initialize(view)
        search_fields = getattr(view, 'search_fields', None)
        search_terms = self.get_search_terms(request)

        if not search_fields or not search_terms:
            return queryset

        orm_lookups = [
            self.construct_search(six.text_type(search_field))
            for search_field in search_fields
        ]

        base = queryset
        conditions = []
        for search_term in search_terms:
            queries = [
                models.Q(**{orm_lookup: search_term})
                for orm_lookup in orm_lookups
            ]
            conditions.append(reduce(operator.or_, queries))
        queryset = queryset.filter(reduce(operator.or_, conditions))

        if self.must_call_distinct(queryset, search_fields):
            queryset = distinct(queryset, base)
        return queryset

    def get_schema_fields(self, view):
        self.__initialize(view)
        assert coreapi is not None, 'coreapi must be installed to use `get_schema_fields()`'
        assert coreschema is not None, 'coreschema must be installed to use `get_schema_fields()`'
        return [
            coreapi.Field(
                name=self.search_param,
                required=self.search_required,
                location='query',
                schema=coreschema.String(
                    title=force_text(self.search_title),
                    description=force_text(self.search_description)
                )
            )
        ]


class FakeFilterMixin(object):
    """
    문서화에 포함되어야 하는 필터지만, 필터 내에서 실제 필터링 작업은 하지 않고 넘기는 용도.
    """

    def filter(self, qs, value):
        return qs


class FakeDateTimeFilter(FakeFilterMixin, django_filters.DateTimeFilter):
    pass


class FakeBaseInFilter(FakeFilterMixin, django_filters.BaseInFilter):
    pass


class FakeChoiceFilter(FakeFilterMixin, django_filters.ChoiceFilter):
    pass


class FakeNumberFilter(FakeFilterMixin, django_filters.NumberFilter):
    pass


class FakeCharFilter(FakeFilterMixin, django_filters.CharFilter):
    pass


class NullBooleanField(forms.NullBooleanField):
    widget = NullBooleanSelect


class FakeBooleanFilter(FakeFilterMixin, django_filters.BooleanFilter):
    field_class = NullBooleanField
