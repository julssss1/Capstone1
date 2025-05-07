# app/student/__init__.py
from flask import Blueprint

bp = Blueprint('student', __name__) # No template folder needed if using main app/templates

from . import routes