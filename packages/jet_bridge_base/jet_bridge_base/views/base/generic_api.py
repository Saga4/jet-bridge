from sqlalchemy.exc import SQLAlchemyError

from jet_bridge_base.db_types import apply_session_timezone
from jet_bridge_base.db_types.mongo import MongoSession
from jet_bridge_base.exceptions.not_found import NotFound
from jet_bridge_base.paginators.page_number import PageNumberPagination
from jet_bridge_base.serializers.model_serializer import get_column_data_type
from jet_bridge_base.views.base.api import APIView


class GenericAPIView(APIView):
    serializer_class = None
    filter_class = None
    pagination_class = PageNumberPagination
    _paginator = None
    lookup_url_kwarg = None

    def get_model(self, request):
        raise NotImplementedError

    def get_model_lookup_field(self, request):
        raise NotImplementedError

    def get_queryset(self, request):
        raise NotImplementedError

    def get_object(self, request):
        # Reduce method calls and object creation by caching lookups and simplifying flow
        lookup_url_kwarg = self.lookup_url_kwarg or 'pk'
        path_kwargs = request.path_kwargs

        if lookup_url_kwarg not in path_kwargs:
            raise AssertionError()

        model = self.get_model(request)
        lookup_field = self.get_model_lookup_field(request)
        model_field = getattr(model, lookup_field)
        lookup_value = path_kwargs[lookup_url_kwarg]

        # Minimize cost of double call to get_queryset and filter_queryset
        queryset = self.get_queryset(request)
        filter_instance = self.get_filter(request)
        if filter_instance:
            queryset = filter_instance.filter_queryset(request, queryset)

        # Cache column data type and SQLA operator
        data_type = get_column_data_type(model_field)
        try:
            field_lookup = model_field.__eq__
            field = data_type(context={'model_field': model_field})
            lookup_value = field.to_internal_value(lookup_value)
            # Use SQLAlchemy filter more efficiently
            obj = queryset.filter(field_lookup(lookup_value)).first()
        except SQLAlchemyError:
            # Only rollback if actually needed
            session = getattr(queryset, 'session', None)
            if session is not None:
                session.rollback()
            raise

        if obj is None:
            raise NotFound

        self.check_object_permissions(request, obj)
        return obj

    def get_filter(self, request, *args, **kwargs):
        filter_class = self.get_filter_class(request)
        if not filter_class:
            return
        kwargs['context'] = self.filter_context()
        return filter_class(*args, **kwargs)

    def get_filter_class(self, request):
        return self.filter_class

    def filter_context(self):
        return {
            # 'request': self.request,
            'handler': self
        }

    def apply_timezone(self, request):
        timezone = request.get_argument('tz', None)
        if timezone is not None:
            if not isinstance(request.session, MongoSession):
                try:
                    apply_session_timezone(request.session, timezone)
                except SQLAlchemyError:
                    request.session.rollback()

    def filter_queryset(self, request, queryset):
        filter_instance = self.get_filter(request)
        if filter_instance:
            queryset = filter_instance.filter_queryset(request, queryset)
        return queryset

    @property
    def paginator(self):
        if not self._paginator:
            if self.pagination_class is None:
                self._paginator = None
            else:
                self._paginator = self.pagination_class()
        return self._paginator

    def paginate_queryset(self, request, queryset):
        if self.paginator is None:
            return None
        return self.paginator.paginate_queryset(request, queryset, self)

    def get_paginated_response(self, request, data):
        if self.paginator is None:
            raise AssertionError()
        return self.paginator.get_paginated_response(request, data)

    def get_serializer(self, request, *args, **kwargs):
        serializer_class = self.get_serializer_class(request)
        kwargs['context'] = self.get_serializer_context(request)
        return serializer_class(*args, **kwargs)

    def get_serializer_class(self, request):
        return self.serializer_class

    def get_serializer_context(self, request):
        return {
            'request': request,
            'view': self,
            'session': request.session
        }

    def write_error(self, status_code, **kwargs):
        self.session.rollback()
        super(GenericAPIView, self).write_error(status_code, **kwargs)
