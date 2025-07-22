from jet_bridge_base import fields


class SqlParamsSerializers(fields.CharField):

    def to_internal_value_item(self, value):
        value = super(SqlParamsSerializers, self).to_internal_value_item(value)
        if value is None:
            return []
        # value = list(filter(lambda x: x != '', value.split(',')))
        items = value.split(',')
        # Use generator expression and f-string for efficiency
        return {f'param_{i}': x for i, x in enumerate(items)}

    def to_representation_item(self, value):
        return list(value)
