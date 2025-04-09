import uritemplate
import coreschema
import re

from rest_framework import exceptions, serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.renderers import CoreJSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_swagger.views import renderers
from rest_framework.schemas import field_to_schema, get_pk_description
from rest_framework.fields import IntegerField, URLField, JSONField
from rest_framework.pagination import PageNumberPagination, CursorPagination, LimitOffsetPagination
from rest_framework.utils import formatting

from django.utils.encoding import force_text, smart_text
from django.db import models
from django.views.decorators.cache import never_cache

from coreapi import Field, Link

from drf_openapi.codec import _get_parameters
from drf_openapi.entities import OpenApiSchemaGenerator, VersionedSerializers
from .codec import OpenAPIRenderer, _get_parameters

header_regex = re.compile('^[a-zA-Z][0-9A-Za-z_]*:')


def is_list_view(path, method, view):
    """
    Return True if the given path/method appears to represent a list view.
    """
    if hasattr(view, 'action'):
        # Viewsets have an explicitly defined action, which we can inspect.
        return view.action.endswith('list')

    if method.lower() != 'get':
        return False
    path_components = path.strip('/').split('/')
    if path_components and '{' in path_components[-1]:
        return False
    return True


class OpenApiLink(Link):
    """OpenAPI-compliant Link provides:
    - Schema to the response
    """

    def __init__(self, response_schema, error_status_codes,
                 success_status_code=None, url=None, action=None, encoding=None, transform=None, title=None,
                 description=None, fields=None):
        super(OpenApiLink, self).__init__(
            url=url,
            action=action,
            encoding=encoding,
            transform=transform,
            title=title,
            description=description,
            fields=fields
        )
        self._success_status_code = success_status_code
        self._response_schema = response_schema
        self._error_status_codes = error_status_codes

    @property
    def response_schema(self):
        return self._response_schema

    @property
    def error_status_codes(self):
        return self._error_status_codes

    @property
    def status_code(self):
        if not self._success_status_code:
            if self.action.lower() == 'post':
                self._success_status_code = status.HTTP_201_CREATED
            elif self.action.lower() == 'delete':
                self._success_status_code = status.HTTP_204_NO_CONTENT
            else:
                self._success_status_code = status.HTTP_200_OK
        return self._success_status_code


class FountSchemaGenerator(OpenApiSchemaGenerator):
    def get_serializer_fields(self, path, method, view, version=None):
        """
        Return a list of `coreapi.Field` instances corresponding to any
        request body input, as determined by the serializer class.
        """
        if method not in ('PUT', 'PATCH', 'POST', 'DELETE'):
            return []
        elif method == 'DELETE':
            method_func = getattr(view, getattr(view, 'action', method.lower()), None)
            request_serializer_class = getattr(method_func, 'request_serializer', None)

            if not request_serializer_class:
                return []

        if not hasattr(view, 'serializer_class') and not hasattr(view, 'get_serializer_class'):
            return []

        serializer_class = view.get_serializer_class() if hasattr(view, 'get_serializer_class') \
            else view.serializer_class
        serializer = serializer_class()

        if isinstance(serializer, serializers.ListSerializer):
            return [
                Field(
                    name='data',
                    location='body',
                    required=True,
                    schema=coreschema.Array()
                )
            ]

        if not isinstance(serializer, serializers.Serializer):
            return []

        fields = []
        for field in serializer.fields.values():
            if field.read_only or isinstance(field, serializers.HiddenField):
                continue

            required = field.required and method != 'PATCH'
            field = Field(
                name=field.field_name,
                location='form',
                required=required,
                schema=field_to_schema(field),
                description=str(field.help_text) if field.help_text else '',
                example=field.get_initial()
            )
            fields.append(field)

        return fields

    def get_response_object(self, response_serializer_class, description):

        fields = []
        serializer = response_serializer_class()
        nested_obj = {}

        for field in serializer.fields.values():
            # If field is a serializer, attempt to get its schema.
            if isinstance(field, serializers.Serializer):
                subfield_schema = self.get_response_object(field.__class__, None)[0].get('schema')

                # If the schema exists, use it as the nested_obj
                if subfield_schema is not None:
                    nested_obj[field.field_name] = subfield_schema
                    nested_obj[field.field_name]['description'] = str(field.help_text) if field.help_text else ''
                    continue

            # Otherwise, carry-on and use the field's schema.
            if not field.write_only:
                fields.append(Field(
                    name=field.field_name,
                    location='form',
                    required=field.required,
                    schema=field_to_schema(field)
                ))

        res = _get_parameters(Link(fields=fields), None)

        error_status_codes = {}

        response_meta = getattr(response_serializer_class, 'Meta', None)

        success_status_code = getattr(response_meta, 'success_status_code', None)

        for status_code, description in getattr(response_meta, 'error_status_codes', {}).items():
            error_status_codes[status_code] = {'description': description}

        if not res:
            if nested_obj:
                return {
                           'description': description,
                           'schema': {
                               'type': 'object',
                               'properties': nested_obj
                           }
                       }, success_status_code, error_status_codes
            else:
                return {}, success_status_code, error_status_codes

        schema = res[0]['schema']
        schema['properties'].update(nested_obj)
        response_schema = {
            'description': description,
            'schema': schema
        }

        return response_schema, success_status_code, error_status_codes

    def get_paginator_serializer(self, view, child_serializer_class):
        class BaseFakeListSerializer(serializers.Serializer):
            data = child_serializer_class(many=True)

        class FakeLinkSerializer(serializers.Serializer):
            next = URLField()
            previous = URLField()

        class FakePrevNextListSerializer(BaseFakeListSerializer):
            link = FakeLinkSerializer(help_text='')

        pager = view.pagination_class
        if hasattr(pager, 'default_pager'):
            # Must be a ProxyPagination
            pager = pager.default_pager

        if issubclass(pager, (PageNumberPagination, LimitOffsetPagination)):
            class FakeListSerializer(FakePrevNextListSerializer):
                count = IntegerField()
                page_current = IntegerField()
                page_size = IntegerField()
                page_count = IntegerField()

            return FakeListSerializer
        elif issubclass(pager, CursorPagination):
            return FakePrevNextListSerializer

        return BaseFakeListSerializer

    def get_path_fields(self, path, method, view):
        """
        Return a list of `coreapi.Field` instances corresponding to any
        templated path variables.
        """
        model = getattr(getattr(view, 'queryset', None), 'model', None)
        fields = []

        for variable in uritemplate.variables(path):

            if variable == 'version':
                continue

            title = ''
            description = ''
            schema_cls = coreschema.String
            kwargs = {}
            if model is not None:
                # Attempt to infer a field description if possible.
                try:
                    model_field = model._meta.get_field(variable)
                except:
                    model_field = None

                if model_field is not None and model_field.verbose_name:
                    try:
                        title = force_text(model_field.verbose_name)
                    except:
                        title = str(model_field.verbose_name)

                if model_field is not None and model_field.help_text:
                    description = force_text(model_field.help_text)
                elif model_field is not None and model_field.primary_key:
                    description = get_pk_description(model, model_field)

                if hasattr(view, 'lookup_value_regex') and view.lookup_field == variable:
                    kwargs['pattern'] = view.lookup_value_regex
                elif isinstance(model_field, models.AutoField):
                    schema_cls = coreschema.Integer

            field = Field(
                name=variable,
                location='path',
                required=True,
                schema=schema_cls(title=title, description=description, **kwargs)
            )
            fields.append(field)

        return fields

    def get_filter_fields(self, path, method, view):
        if not is_list_view(path, method, view) and not hasattr(view, 'filter_class'):
            return []

        if not getattr(view, 'filter_backends', None):
            return []

        fields = []
        for filter_backend in view.filter_backends:
            fields += filter_backend().get_schema_fields(view)
        return fields

    def get_description(self, path, method, view):
        """
        Determine a link description.

        This will be based on the method docstring if one exists,
        or else the class docstring.
        """
        method_name = getattr(view, 'action', method.lower())
        method_docstring = getattr(view, method_name, None).__doc__
        if method_docstring:
            # An explicit docstring on the method or action.
            return formatting.dedent(smart_text(method_docstring))

        description = view.get_view_description()
        lines = [line.rstrip() for line in description.splitlines()]
        current_section = ''
        sections = {'': ''}

        for line in lines:
            if header_regex.match(line):
                current_section, seperator, lead = line.partition(':')
                sections[current_section] = lead.strip()
            else:
                sections[current_section] += '\n' + line

        header = getattr(view, 'action', method.lower())
        if header in sections:
            return sections[header].strip()
        if header in self.coerce_method_names:
            if self.coerce_method_names[header] in sections:
                return sections[self.coerce_method_names[header]].strip()
        return sections[''].strip()

    def get_link(self, path, method, view, version=None):
        fields = self.get_path_fields(path, method, view)
        fields += self.get_serializer_fields(path, method, view, version=version)
        fields += self.get_pagination_fields(path, method, view)
        fields += self.get_filter_fields(path, method, view)

        if fields and any([field.location in ('form', 'body') for field in fields]):
            encoding = self.get_encoding(path, method, view)
        else:
            encoding = None

        description = self.get_description(path, method, view)

        method_name = getattr(view, 'action', method.lower())
        method_func = getattr(view, method_name, None)

        request_serializer_class = getattr(method_func, 'request_serializer', None)
        if request_serializer_class and issubclass(request_serializer_class, VersionedSerializers):
            request_doc = self.get_serializer_doc(request_serializer_class)
            if request_doc:
                description = description + '\n\n**Request Description:**\n' + request_doc

        response_serializer_class = getattr(method_func, 'response_serializer', None)
        if response_serializer_class and issubclass(response_serializer_class, VersionedSerializers):
            res_doc = self.get_serializer_doc(response_serializer_class)
            if res_doc:
                description = description + '\n\n**Response Description:**\n' + res_doc
            response_serializer_class = response_serializer_class.get(version)

        if not response_serializer_class and method_name not in ('destroy',):
            if hasattr(view, 'get_serializer_class'):
                response_serializer_class = view.get_serializer_class()
            elif hasattr(view, 'serializer_class'):
                response_serializer_class = view.serializer_class
            if response_serializer_class and method_name == 'list':
                response_serializer_class = self.get_paginator_serializer(
                    view, response_serializer_class)
        response_schema, success_status_code, error_status_codes = self.get_response_object(
            response_serializer_class, method_func.__doc__) if response_serializer_class else ({}, None, {})

        return OpenApiLink(
            response_schema=response_schema,
            success_status_code=success_status_code,
            error_status_codes=error_status_codes,
            url=path.replace('{version}', self.version),  # can't use format because there may be other param
            action=method.lower(),
            encoding=encoding,
            fields=fields,
            description=description
        )


def get_swagger_view(title=None, url=None, patterns=None, urlconf=None, version=''):
    """
    Returns schema view which renders Swagger/OpenAPI.
    """

    class SwaggerSchemaView(APIView):
        _ignore_model_permissions = True
        exclude_from_schema = True
        permission_classes = [AllowAny]
        renderer_classes = [
            CoreJSONRenderer,
            OpenAPIRenderer,
            renderers.SwaggerUIRenderer
        ]

        def get(self, request):
            generator = FountSchemaGenerator(
                title=title,
                url=url,
                patterns=patterns,
                urlconf=urlconf,
                version=version
            )
            schema = generator.get_schema(request=request)

            if not schema:
                raise exceptions.ValidationError(
                    'The schema generator did not return a schema Document'
                )

            return Response(schema)

    return never_cache(SwaggerSchemaView.as_view())
