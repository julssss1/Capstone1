from flask import Blueprint

bp = Blueprint('student', __name__, template_folder='../templates', static_folder='../static')

# Import routes from the new modules to register them with the blueprint
from . import dashboard_routes
from . import assignment_routes
from . import learning_routes
from . import profile_routes
from . import sign_recognition_routes
