from flask import Flask, session, redirect, url_for, flash, render_template
import os
import threading
from supabase import create_client, Client
from datetime import datetime, timezone

from . import sign_logic

def format_utc_datetime(value):
    if not value:
        return None
    try:
        if '+' not in value and 'Z' not in value:
            value += '+00:00'
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None

def create_app(config_override=None): # Changed parameter name for clarity
    app = Flask(__name__, instance_relative_config=True)

    # Load default config first
    app.config.from_object('config.Config')

    # Then override with any test-specific config
    if config_override:
        app.config.from_mapping(config_override)

    url: str = app.config.get("SUPABASE_URL")
    key: str = app.config.get("SUPABASE_SERVICE_KEY")

    if not url or not key:
        print("*"*60)
        print("WARNING: Supabase URL or Service Key not configured in config.py.")
        print("Supabase integration will not work.")
        print("*"*60)
        app.supabase = None
    else:
        try:
            app.supabase = create_client(url, key)
            print("Supabase client initialized successfully.")
        except Exception as e:
            print("*"*60)
            print(f"ERROR: Failed to initialize Supabase client: {e}")
            print("*"*60)
            app.supabase = None

    print(f"App created. Static folder: {app.static_folder}, Template folder: {app.template_folder}")
    print(f"Attempting to load model from: {app.config.get('MODEL_PATH')}")


    with app.app_context():
        sign_logic.initialize_resources()

        if sign_logic.interpreter is None or sign_logic.hands is None:
             print("*"*60)
             print("WARNING: Sign recognition initialization failed. Some features might not work.")
             print("*"*60)


    from .auth import bp as auth_bp
    from .student import bp as student_bp
    from .teacher import bp as teacher_bp  # Changed from 'routes as teacher_routes'
    from .admin import bp as admin_bp # Changed from 'routes as admin_routes'

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(student_bp, url_prefix='/student')
    app.register_blueprint(teacher_bp, url_prefix='/teacher') # Changed from 'teacher_routes.bp'
    app.register_blueprint(admin_bp, url_prefix='/admin') # Changed from admin_routes.bp

    # Register custom Jinja filter
    app.jinja_env.filters['format_utc_datetime'] = format_utc_datetime

    @app.route('/')
    def home():
        if 'user_role' in session:
            role = session['user_role']
            if role == 'Student':
                return redirect(url_for('student.student_dashboard'))
            elif role == 'Teacher':
                return redirect(url_for('teacher.teacher_dashboard'))
            elif role == 'Admin':
                return redirect(url_for('admin.admin_dashboard'))
            else:
                session.clear()
                flash('Invalid session role. Please log in again.', 'warning')
                return redirect(url_for('auth.login'))
        return redirect(url_for('auth.login'))

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('403.html'), 403

    @app.errorhandler(500)
    def internal_server_error(e):
         print(f"Internal Server Error: {e}")
         return render_template('500.html'), 500

    print("App factory finished.")
    return app
