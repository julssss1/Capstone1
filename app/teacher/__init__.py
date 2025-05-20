from flask import Blueprint

bp = Blueprint('teacher', __name__, template_folder='../templates', static_folder='../static')

# Import routes from the new modules to register them with the blueprint
from . import dashboard_routes
from . import lesson_routes
from . import assignment_routes
from . import grading_routes
