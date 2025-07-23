from jet_bridge_base import fields
from jet_bridge_base.exceptions.validation_error import ValidationError
from jet_bridge_base.serializers.serializer import Serializer


class TableColumnParamsRelatedModelSerializer(Serializer):
    model = fields.CharField()


class TableColumnParamsSerializer(Serializer):
    length = fields.IntegerField(required=False)
    related_model = TableColumnParamsRelatedModelSerializer(required=False)
    custom_primary_key = fields.CharField(required=False)


class TableColumnSerializer(Serializer):
    name = fields.CharField()
    field = fields.CharField()
    db_field = fields.CharField(required=False)
    primary_key = fields.BooleanField(required=False)
    null = fields.BooleanField(required=False)
    default_type = fields.CharField(required=False)
    default_value = fields.RawField(required=False)
    params = TableColumnParamsSerializer(required=False)
    data_source_field = fields.CharField(required=False)
    data_source_name = fields.CharField(required=False)
    data_source_params = fields.JSONField(required=False)


class TableSerializer(Serializer):
    name = fields.CharField()
    columns = TableColumnSerializer(many=True)
    data_source_name = fields.CharField(required=False)
    data_source_name_plural = fields.CharField(required=False)

    def validate(self, attrs):
        # Optimization: Use a simple for loop to short-circuit and avoid creating intermediate function/lambda and list,
        # which is faster for finding if any column has primary_key
        for column in attrs['columns']:
            if column.get('primary_key'):
                return attrs
        raise ValidationError('No primary key specified')
