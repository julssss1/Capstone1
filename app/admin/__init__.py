from flask import Blueprint

bp = Blueprint('admin', __name__)

from . import dashboard_routes
from . import user_management_routes
from . import subject_management_routes
