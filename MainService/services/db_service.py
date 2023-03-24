from flask_sqlalchemy import SQLAlchemy
from sqlalchemy_utils import create_database, drop_database


class DbService:
    def __init__(self, db: SQLAlchemy):
        self.db = db

    def create_all_tables(self):
        self.db.create_all()

    def drop_all_tables(self):
        self.db.drop_all()

    def execute_sql(self, sql: str, params=None):
        with self.db.engine.connect() as conn:
            result = conn.execute(sql, params)
            if result.returns_rows:
                return result.fetchall()
            else:
                return None

    def create_app_database(self):
        create_database(self.db.engine.url)

    def drop_app_database(self):
        drop_database(self.db.engine.url)

        # def create_database(self):
        #     with self.db.engine.connect() as conn:
        #         conn.execute("COMMIT")
        #         conn.execute(f"CREATE DATABASE {self.db.engine.url.database}")
        #
        # def drop_database(self):
        #     with self.db.engine.connect() as conn:
        #         conn.execute("COMMIT")
        #         conn.execute(f"DROP DATABASE IF EXISTS {self.db.engine.url.database}")
