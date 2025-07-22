from .mongo_operator import MongoOperator


class MongoColumn(object):

    def __init__(self, table, name, type, nullable=True, mixed_types=None, autoincrement=False, default=None,
                 server_default=None, foreign_keys=None, comment=None, params=None):
        self.table = table
        self.name = name
        self.key = name
        self.type = type
        self.nullable = nullable
        self.mixed_types = mixed_types
        self.autoincrement = autoincrement
        self.default = default
        self.server_default = server_default
        # Avoid unnecessary creation of empty list/dict
        if foreign_keys is None:
            self.foreign_keys = []
        else:
            self.foreign_keys = foreign_keys
        self.comment = comment
        if params is None:
            self.params = {}
        else:
            self.params = params

    @staticmethod
    def deserialize(table, obj):
        # Remove 'name' and 'type' in one goto for slight speedup and less attr lookup
        name = obj.pop('name')
        typ = obj.pop('type')
        return MongoColumn(table, name, typ, **obj)

    def serialize(self):
        return {
            'name': self.name,
            'type': self.type,
            'nullable': self.nullable,
            'mixed_types': self.mixed_types,
            'autoincrement': self.autoincrement,
            'default': self.default,
            'server_default': self.server_default,
            'foreign_keys': self.foreign_keys,
            'comment': self.comment,
            'params': self.params
        }

    def __eq__(self, other):
        return MongoOperator('__eq__', self, other)

    def __gt__(self, other):
        return MongoOperator('__gt__', self, other)

    def __ge__(self, other):
        return MongoOperator('__ge__', self, other)

    def __lt__(self, other):
        return MongoOperator('__lt__', self, other)

    def __le__(self, other):
        return MongoOperator('__le__', self, other)

    def isnot(self, other):
        return MongoOperator('not', MongoOperator('__eq__', self, other))

    def ilike(self, value):
        return MongoOperator('ilike', self, value)

    def exists(self, value):
        return MongoOperator('exists', self, value)

    def in_(self, value):
        return MongoOperator('in', self, value)

    def json_icontains(self, value):
        return MongoOperator('json_icontains', self, value)

    def __repr__(self):
        return '{}.{}'.format(self.table.name, self.name)
