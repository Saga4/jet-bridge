import time

from jet_bridge_base.configuration import configuration
from jet_bridge_base.db import connections, pending_connections
from jet_bridge_base.db_types import inspect_uniform
from jet_bridge_base.permissions import AdministratorPermissions
from jet_bridge_base.responses.json import JSONResponse
from jet_bridge_base.sentry import sentry_controller
from jet_bridge_base.utils.classes import issubclass_safe
from jet_bridge_base.utils.common import format_size
from jet_bridge_base.utils.graphql import ModelFiltersType, ModelFiltersFieldType, ModelFiltersRelationshipType, \
    ModelLookupsType, ModelLookupsFieldType, ModelLookupsRelationshipType, ModelSortType, ModelAttrsType
from jet_bridge_base.utils.process import get_memory_usage
from jet_bridge_base.views.base.api import BaseAPIView


class StatusView(BaseAPIView):
    permission_classes = (AdministratorPermissions,)

    def map_connection_graphql_schema(self, schema):
        if not schema:
            return {'status': 'no_schema'}

        # Unpack relevant fields to locals for small speedup
        instance = schema.get('instance')
        tables_processed = schema.get('tables_processed', 0)
        tables_total = schema.get('tables_total')

        if not instance:
            return {
                'status': 'pending',
                'tables_processed': tables_processed,
                'tables_total': tables_total
            }

        # Collect all fields upfront
        get_schema_time = schema.get('get_schema_time')
        memory_usage_approx = schema.get('memory_usage_approx')

        type_map_values = list(instance._type_map.values())

        # Bind frequently-used functions and types locally
        _issubclass_safe = issubclass_safe
        _hasattr = hasattr

        # Prepare tuple of (type, counter_name) for mapping
        _type_predicates = (
            (ModelFiltersType, 'filters_count'),
            (ModelFiltersFieldType, 'filters_fields_count'),
            (ModelFiltersRelationshipType, 'filters_relationships_count'),
            (ModelLookupsType, 'lookups_count'),
            (ModelLookupsFieldType, 'lookups_fields_count'),
            (ModelLookupsRelationshipType, 'lookups_relationships_count'),
            (ModelSortType, 'sort_count'),
            (ModelAttrsType, 'attrs_count')
        )
        counter_names = [name for _, name in _type_predicates]
        counts = dict.fromkeys(counter_names, 0)

        # Cache subclass results per graphene_type to reduce issubclass_safe calls
        subclass_cache = {}

        for item in type_map_values:
            # Optimize check -- skip lacking graphene_type
            if not _hasattr(item, 'graphene_type'):
                continue
            gtype = item.graphene_type
            if gtype in subclass_cache:
                cache_val = subclass_cache[gtype]
            else:
                # Find first predicate matched, in order (preserving logic)
                cache_val = None
                for predicate, name in _type_predicates:
                    if _issubclass_safe(gtype, predicate):
                        cache_val = name
                        break
                subclass_cache[gtype] = cache_val
            if cache_val:
                counts[cache_val] += 1

        types_count = len(type_map_values)

        return {
            'status': 'ok',
            'tables_processed': tables_processed,
            'tables_total': tables_total,
            'types': types_count,
            'filters': counts['filters_count'],
            'filters_fields': counts['filters_fields_count'],
            'filters_relationships': counts['filters_relationships_count'],
            'lookups': counts['lookups_count'],
            'lookups_fields': counts['lookups_fields_count'],
            'lookups_relationships': counts['lookups_relationships_count'],
            'sort': counts['sort_count'],
            'attrs': counts['attrs_count'],
            'get_schema_time': get_schema_time,
            'memory_usage_approx': memory_usage_approx,
            'memory_usage_approx_str': format_size(memory_usage_approx) if memory_usage_approx else None
        }

    def map_tunnel(self, tunnel):
        if not tunnel:
            return

        return {
            'is_active': tunnel.is_active,
            'local_address': '{}:{}'.format(tunnel.local_bind_host, tunnel.local_bind_port),
            'remote_address': '{}:{}'.format(tunnel.ssh_host, tunnel.ssh_port)
        }

    def map_connection(self, connection):
        cache = connection['cache']
        MappedBase = connection['MappedBase']
        column_count = 0
        relationships_count = 0

        for Model in MappedBase.classes:
            try:
                mapper = inspect_uniform(Model)
                column_count += len(mapper.columns)
                relationships_count += len(mapper.relationships)
            except Exception as e:
                sentry_controller.capture_exception(e)

        graphql_schema = self.map_connection_graphql_schema(cache.get('graphql_schema'))
        graphql_schema_draft = self.map_connection_graphql_schema(cache.get('graphql_schema_draft'))
        graphql_schema_base62 = self.map_connection_graphql_schema(cache.get('graphql_schema_base62'))
        graphql_schema_base62_draft = self.map_connection_graphql_schema(cache.get('graphql_schema_base62_draft'))
        tunnel = self.map_tunnel(connection.get('tunnel'))
        last_request = connection.get('last_request')
        default_timezone_updated = connection.get('default_timezone_updated')

        reflect_memory_usage_approx = connection.get('reflect_memory_usage_approx')

        return {
            'id': connection['id'],
            'name': connection['name'],
            'params_id': connection['params_id'],
            'project': connection.get('project'),
            'token': connection.get('token'),
            'tables': len(MappedBase.classes),
            'columns': column_count,
            'relationships': relationships_count,
            'graphql_schema': graphql_schema,
            'graphql_schema_draft': graphql_schema_draft,
            'graphql_schema_base62': graphql_schema_base62,
            'graphql_schema_base62_draft': graphql_schema_base62_draft,
            'init_start': connection.get('init_start'),
            'connect_time': connection.get('connect_time'),
            'reflect_time': connection.get('reflect_time'),
            'reflect_memory_usage_approx': reflect_memory_usage_approx,
            'reflect_memory_usage_approx_str': format_size(reflect_memory_usage_approx) if reflect_memory_usage_approx else None,
            'reflect_metadata_dump': connection.get('reflect_metadata_dump'),
            'default_timezone': str(connection['default_timezone']) if connection.get('default_timezone') else None,
            'default_timezone_updated': default_timezone_updated.isoformat() if default_timezone_updated else None,
            'tunnel': tunnel,
            'last_request': last_request.isoformat() if last_request else None
        }

    def map_pending_connection(self, pending_connection):
        tunnel = self.map_tunnel(pending_connection.get('tunnel'))

        return {
            'id': pending_connection['id'],
            'name': pending_connection['name'],
            'project': pending_connection.get('project'),
            'token': pending_connection.get('token'),
            'init_start': pending_connection.get('init_start'),
            'tables_processed': pending_connection.get('tables_processed', 0),
            'tables_total': pending_connection.get('tables_total'),
            'tunnel': tunnel
        }

    def get(self, request, *args, **kwargs):
        now = time.time()
        uptime = round(now - configuration.init_time)
        memory_used = get_memory_usage()

        active_connections = []
        schema_generating_connections = []

        for connection in connections.values():
            cache = connection['cache']
            graphql_schema = cache.get('graphql_schema')
            graphql_schema_draft = cache.get('graphql_schema_draft')
            graphql_schema_base62 = cache.get('graphql_schema_base62')
            graphql_schema_base62_draft = cache.get('graphql_schema_base62_draft')

            if graphql_schema and not graphql_schema.get('instance'):
                schema_generating_connections.append(connection)
            elif graphql_schema_draft and not graphql_schema_draft.get('instance'):
                schema_generating_connections.append(connection)
            elif graphql_schema_base62 and not graphql_schema_base62.get('instance'):
                schema_generating_connections.append(connection)
            elif graphql_schema_base62_draft and not graphql_schema_base62_draft.get('instance'):
                schema_generating_connections.append(connection)
            else:
                active_connections.append(connection)

        return JSONResponse({
            'total_pending_connections': len(pending_connections.keys()),
            'total_schema_generating_connections': len(schema_generating_connections),
            'total_active_connections': len(active_connections),
            'pending_connections': map(lambda x: self.map_pending_connection(x), pending_connections.values()),
            'schema_generating_connections': map(lambda x: self.map_connection(x), schema_generating_connections),
            'active_connections': map(lambda x: self.map_connection(x), active_connections),
            'memory_used': memory_used,
            'memory_used_str': format_size(memory_used),
            'uptime': uptime
        })
