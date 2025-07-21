from jet_bridge_base.db_types import inspect_uniform, queryset_search
from jet_bridge_base.filters.char_filter import CharFilter
from jet_bridge_base.filters.filter import EMPTY_VALUES


def get_model_search_filter(Model):
    if Model in _model_filter_class_cache:
        return _model_filter_class_cache[Model]

    # Only process if not already in cache
    mapper = inspect_uniform(Model)

    class ModelSearchFilter(CharFilter):
        def filter(self, qs, value):
            if value in EMPTY_VALUES:
                return qs
            value = self.clean_value(value)
            return queryset_search(qs, mapper, value)

    _model_filter_class_cache[Model] = ModelSearchFilter
    return ModelSearchFilter

_model_filter_class_cache = {}
