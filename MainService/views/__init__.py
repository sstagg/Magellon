from flask import Blueprint

# Import the blueprints from the subdirectories
from views.home import home_bp


# Register the blueprints
views_bp = Blueprint('views', __name__)
views_bp.register_blueprint(home_bp)
