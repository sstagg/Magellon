import json

from sqlalchemy import Text, TypeDecorator


class JSON(TypeDecorator):
    """Represents an immutable structure as a json-encoded string."""

    impl = Text

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(Text().with_variant(Text(), 'postgresql'))
        elif dialect.name == 'mysql':
            return dialect.type_descriptor(Text().with_variant(Text(), 'mysql'))
        else:
            return super(JSON, self).load_dialect_impl(dialect)

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value
