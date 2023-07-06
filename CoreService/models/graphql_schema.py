# import graphene
# from graphene_sqlalchemy import SQLAlchemyObjectType, SQLAlchemyConnectionField
# from graphene import ObjectType, Field, String, ID, Int, relay
#
# from models.sqlalchemy_models import Camera
#
#
# class CameraType(SQLAlchemyObjectType):
#     class Meta:
#         model = Camera
#         interfaces = (graphene.relay.Node,)
#
#
# class CreateTodo(ObjectType):
#     todo = Field(lambda: CameraType)
#
#     class Arguments:
#         title = String(required=True)
#         description = String()
#
#     def mutate(self, info, title, description):
#         # db = get_db()
#         todo = Camera(title=title, description=description)
#         # db.add(todo)
#         # db.commit()
#         # db.refresh(todo)
#         return CreateTodo(todo=todo)
#     # upload_file = FileUploadMutation.Field()
#
#
# class Query2(graphene.ObjectType):
#     # camera = graphene.Field(CameraType)
#     # camera = relay.Node.Field(CameraType)
#     all_cameras = SQLAlchemyConnectionField(CameraType)
#
#     # def resolve_camera(self, info):
#     #     # You can implement your query logic here
#     #     # For example, to retrieve a camera object:
#     #     camera = Camera.query.first()
#     #     return camera
#
#
# graphene_schema = graphene.Schema(query=Query2, mutation=CreateTodo)
import graphene


class CameraType(graphene.Interface):
    id = graphene.ID()
    name = graphene.String()
    # friends = graphene.List(lambda: CameraType)

    # def resolve_friends(self, info):

    # The character friends is a list of strings
    # return [get_character(f) for f in self.friends]


class Camera(graphene.ObjectType):
    class Meta:
        interfaces = (CameraType,)


class Query(graphene.ObjectType):
    hello = graphene.String(description='A typical hello world')
    camera = graphene.Field(Camera)

    def resolve_hello(self, info):
        return 'World'

    def resolve_camera(root, info):
        camera_type = Camera()
        camera_type.id = "1"
        camera_type.name = "Sample Camera"

        return camera_type


graphene_schema = graphene.Schema(query=Query)
