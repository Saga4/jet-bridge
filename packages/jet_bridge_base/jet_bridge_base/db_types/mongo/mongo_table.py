from jet_bridge_base.utils.common import CollectionDict

from .mongo_column import MongoColumn


class MongoTable(object):
    def __init__(self, name, columns=None, comment=None, schema=None):
        self.name = name
        if columns:
            # Use a dict comprehension for faster and clearer construction
            self.columns = CollectionDict({
                x['name']: MongoColumn.deserialize(self, x)
                for x in columns
            })
        else:
            self.columns = CollectionDict()
        self.comment = comment
        self.schema = schema

    def append_column(self, column):
        self.columns[column.name] = column

    @staticmethod
    def deserialize(obj):
        # No change, as .pop is probably required (don't copy unnecessarily)
        name = obj.pop('name')
        return MongoTable(name, **obj)

    def serialize(self):
        return {
            'name': self.name,
            'columns': list(map(lambda x: x.serialize(), self.columns.values())),
            'comment': self.comment,
            'schema': self.schema
        }

    def __repr__(self):
        return self.name
