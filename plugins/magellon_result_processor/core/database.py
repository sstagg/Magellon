from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.settings import AppSettingsSingleton


# from controller.context_manager import context_set_db_session_rollback
# engine = create_engine(get_db_connection(), connect_args={"check_same_thread": False})


def get_db_connection():
    return f'{AppSettingsSingleton.get_instance().database_settings.DB_Driver}://{AppSettingsSingleton.get_instance().database_settings.DB_USER}:{AppSettingsSingleton.get_instance().database_settings.DB_PASSWORD}@{AppSettingsSingleton.get_instance().database_settings.DB_HOST}:{AppSettingsSingleton.get_instance().database_settings.DB_Port}/{AppSettingsSingleton.get_instance().database_settings.DB_NAME}'


engine = create_engine(get_db_connection())
session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    try:
        db = session_local()
        yield db
    finally:
        db.close()

# def get_db():
#     """this function is used to inject db_session dependency in every rest api requests"""
#
#     db: Session = session_local()
#     try:
#         yield db
#         #  commit the db session if no exception occurs
#         #  if context_set_db_session_rollback is set to True then rollback the db session
#         # if context_set_db_session_rollback.get():
#         #     logging.info('rollback db session')
#         #     db.rollback()
#         # else:
#         #     db.commit()
#     except Exception as e:
#         #  rollback the db session if any exception occurs
#         logging.error(e)
#         db.rollback()
#     finally:
#         #  close the db session
#         db.close()
