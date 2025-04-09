from django_filters import FilterSet as django_filterset
from django_filters.constants import STRICTNESS
from rest_framework.exceptions import ValidationError
from django.utils import six


class FilterSet(django_filterset):
    @property
    def qs(self):
        if not hasattr(self, '_qs'):
            if not self.is_bound:
                self._qs = self.queryset.all()
                return self._qs

            if not self.form.is_valid():
                if self.strict == STRICTNESS.RAISE_VALIDATION_ERROR:
                    raise ValidationError(self.form.errors)
                elif self.strict == STRICTNESS.RETURN_NO_RESULTS:
                    self._qs = self.queryset.none()
                    return self._qs

            qs = self.queryset.all()
            for name, filter_ in six.iteritems(self.filters):
                value = self.form.cleaned_data.get(name)

                if value is not None:  # valid & clean data
                    qs = filter_.filter(qs, value)

            self._qs = qs

        return self._qs
