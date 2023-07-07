from uuid import UUID

import flask_sqlalchemy.query
import graphene
from graphene import relay, NonNull, String, Field, Mutation, InputObjectType
from graphene_sqlalchemy import SQLAlchemyObjectType, SQLAlchemyConnectionField
from sqlalchemy import LargeBinary
from sqlalchemy.orm import joinedload
from sqlalchemy_utils import UUIDType
from graphene import ResolveInfo
from lib.alchemy_uuid import SqlAlchemyUuidType
from models.models import Camera, Project, Msession, Image

from graphene_sqlalchemy.converter import convert_sqlalchemy_type


@convert_sqlalchemy_type.register(UUIDType)
@convert_sqlalchemy_type.register(SqlAlchemyUuidType)
def convert_uuid_to_string(type, column, registry=None):
    return graphene.UUID


# @convert_sqlalchemy_type.register(LargeBinary)
# def convert_uuid_to_string(type, column, registry=None):
#     return graphene.


class CameraNode(SQLAlchemyObjectType):
    class Meta:
        model = Camera
        interfaces = (relay.Node,)


class ProjectNode(SQLAlchemyObjectType):
    class Meta:
        model = Project
        interfaces = (relay.Node,)


class ProjectInput(InputObjectType):
    name = String(required=True)
    description = String()


class CreateProject(Mutation):
    class Arguments:
        project_data = ProjectInput(required=True)

    project = Field(lambda: ProjectNode)
    @staticmethod
    def mutate(root, info, project_data=None):
        project = Project(name=project_data.name, description=project_data.description)
        # db.session.add(project)
        # db.session.commit()
        return CreateProject(project=project)


class SessionNode(SQLAlchemyObjectType):
    # projectName = Field(String, resolver=lambda obj, info: obj.project1.name)
    project = Field(ProjectNode)

    class Meta:
        model = Msession
        interfaces = (relay.Node,)

    @staticmethod
    def get_node(session, id):
        return session.query(SessionNode).options(joinedload(SessionNode.project1)).get(id)

    def resolve_project(self, info):
        return self.project1


class ImageNode(SQLAlchemyObjectType):
    class Meta:
        model = Image
        interfaces = (relay.Node,)
        # use `only_fields` to only expose specific fields ie "name"
        # only_fields = ("name",)
        # use `exclude_fields` to exclude specific fields ie "last_name"
        # exclude_fields = ("last_name",)


class Mutation(graphene.ObjectType):
    create_project = CreateProject.Field()


class Query(graphene.ObjectType):
    # users = graphene.List(CameraNode)
    # node = relay.Node.Field()
    projects = SQLAlchemyConnectionField(ProjectNode.connection)
    sessions = SQLAlchemyConnectionField(SessionNode.connection)
    Images = SQLAlchemyConnectionField(ImageNode.connection)
    cameras = SQLAlchemyConnectionField(CameraNode.connection, sort=None)

    def resolve_cameras(self, info):
        query: flask_sqlalchemy.query.Query = CameraNode.get_query(info)  # SQLAlchemy query

        return query.all()


qraphql_schema = graphene.Schema(query=Query, mutation=Mutation)
# qraphql_schema.execute(context_value={'session': session})
