from typing import Optional

import strawberry
from pydantic import typing
from strawberry.fastapi import GraphQLRouter
from strawberry.schema.config import StrawberryConfig
from strawberry.types import Info

from models.sqlalchemy_models import Camera

# https://github.com/syedfaisalsaleeem/FastApi-Strawberry-GraphQL-SqlAlchemy-BoilerPlate/blob/main/src/graphql/resolvers/stickynote_resolver.py
# @strawberry.type
# class Camera:
#     id: strawberry.ID
#     name: str
#
#     @classmethod
#     def marshal(cls, model: Camera) -> "Camera":
#         return cls(id=strawberry.ID(str(model.id)), name=model.name)


@strawberry.type
class Query:
    @strawberry.field
    def hello(self,name: Optional[str]) -> str:
        return "Hello World " + name


graphql_strawberry_schema = strawberry.Schema(query=Query,
                                              config=StrawberryConfig(auto_camel_case=True))

strawberry_graphql_router = GraphQLRouter(graphql_strawberry_schema)
# strawberry_graphql_router = GraphQLRouter(graphql_strawberry_schema,context_getter=)
