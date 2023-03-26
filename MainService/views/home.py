from flask import Blueprint, render_template
# from flask_openapi3 import Info, OpenAPI

# info = Info(title="Magellon Main Service API", version="1.0.0")
# app = OpenAPI(__name__, info=info)

home_bp = Blueprint('home', __name__, url_prefix='/')


@home_bp.get('/')
def home():
    return render_template('home.html')
