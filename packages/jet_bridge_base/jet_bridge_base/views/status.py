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

        instance = schema.get('instance')
        tables_processed = schema.get('tables_processed', 0)
        tables_total = schema.get('tables_total')

        if not instance:
            return {
                'status': 'pending',
                'tables_processed': tables_processed,
                'tables_total': tables_total
            }
        
        _type_map_values = list(instance._type_map.values())
        types_count = len(_type_map_values)

        # Use a dict to count each kind instead of many variables and elifs
        counter = {
            'filters': 0,
            'filters_fields': 0,
            'filters_relationships': 0,
            'lookups': 0,
            'lookups_fields': 0,
            'lookups_relationships': 0,
            'sort': 0,
            'attrs': 0,
        }
        # Map class to key in counter dict
        kind_checks = (
            (ModelFiltersType, 'filters'),
            (ModelFiltersFieldType, 'filters_fields'),
            (ModelFiltersRelationshipType, 'filters_relationships'),
            (ModelLookupsType, 'lookups'),
            (ModelLookupsFieldType, 'lookups_fields'),
            (ModelLookupsRelationshipType, 'lookups_relationships'),
            (ModelSortType, 'sort'),
            (ModelAttrsType, 'attrs'),
        )

        for item in _type_map_values:
            graphene_type = getattr(item, 'graphene_type', None)
            if graphene_type is None:
                continue
            for target_type, key in kind_checks:
                if issubclass_safe(graphene_type, target_type):
                    counter[key] += 1
                    break

        get_schema_time = schema.get('get_schema_time')
        memory_usage_approx = schema.get('memory_usage_approx')
        
        return {
            'status': 'ok',
            'tables_processed': tables_processed,
            'tables_total': tables_total,
            'types': types_count,
            'filters': counter['filters'],
            'filters_fields': counter['filters_fields'],
            'filters_relationships': counter['filters_relationships'],
            'lookups': counter['lookups'],
            'lookups_fields': counter['lookups_fields'],
            'lookups_relationships': counter['lookups_relationships'],
            'sort': counter['sort'],
            'attrs': counter['attrs'],
            'get_schema_time': get_schema_time,
            'memory_usage_approx': memory_usage_approx,
            'memory_usage_approx_str': format_size(memory_usage_approx) if memory_usage_approx else None,
        }

    def map_tunnel(self, tunnel):
        if not tunnel:
            return
        # Only access attributes once
        local_bind_host = tunnel.local_bind_host
        local_bind_port = tunnel.local_bind_port
        ssh_host = tunnel.ssh_host
        ssh_port = tunnel.ssh_port
        return {
            'is_active': tunnel.is_active,
            'local_address': f'{local_bind_host}:{local_bind_port}',
            'remote_address': f'{ssh_host}:{ssh_port}'
        }

    def map_connection(self, connection):
        # pull local variables up for less dict and attr lookup
        cache = connection['cache']
        MappedBase = connection['MappedBase']
        classes = MappedBase.classes
        column_count = 0
        relationships_count = 0

        for Model in classes:
            try:
                mapper = inspect_uniform(Model)
            except Exception as e:
                sentry_controller.capture_exception(e)
                continue
            # add both lengths at once to minimize attribute accesses
            columns = getattr(mapper, 'columns', [])
            rels = getattr(mapper, 'relationships', [])
            column_count += len(columns)
            relationships_count += len(rels)

        graphql_schema = self.map_connection_graphql_schema(cache.get('graphql_schema'))
        graphql_schema_draft = self.map_connection_graphql_schema(cache.get('graphql_schema_draft'))
        graphql_schema_base62 = self.map_connection_graphql_schema(cache.get('graphql_schema_base62'))
        graphql_schema_base62_draft = self.map_connection_graphql_schema(cache.get('graphql_schema_base62_draft'))
        tunnel = self.map_tunnel(connection.get('tunnel'))
        last_request = connection.get('last_request')
        default_timezone_updated = connection.get('default_timezone_updated')
        reflect_memory_usage_approx = connection.get('reflect_memory_usage_approx')
        default_timezone = connection.get('default_timezone')

        return {
            'id': connection['id'],
            'name': connection['name'],
            'params_id': connection['params_id'],
            'project': connection.get('project'),
            'token': connection.get('token'),
            'tables': len(classes),
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
            'default_timezone': str(default_timezone) if default_timezone else None,
            'default_timezone_updated': default_timezone_updated.isoformat() if default_timezone_updated else None,
            'tunnel': tunnel,
            'last_request': last_request.isoformat() if last_request else None,
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
