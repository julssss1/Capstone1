from flask import Flask, session, redirect, url_for, flash, render_template
import os
import threading
from supabase import create_client, Client
from flask_socketio import SocketIO

from . import sign_logic

# Initialize SocketIO with async_mode for eventlet and CORS settings
socketio = SocketIO(async_mode='eventlet', cors_allowed_origins="*")

def create_app(config_class='config.Config'):
    app = Flask(__name__, instance_relative_config=True)

    # Initialize SocketIO with the Flask app
    # The cors_allowed_origins is already set when socketio was instantiated
    socketio.init_app(app, manage_session=False)

    app.config.from_object(config_class)

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

    from .auth import routes as auth_routes
    from .student import bp as student_bp
    from .teacher import bp as teacher_bp  # Changed from 'routes as teacher_routes'
    from .admin import bp as admin_bp # Changed from 'routes as admin_routes'

    # Import and register socket event handlers
    from . import socket_events # We will create this file next

    app.register_blueprint(auth_routes.bp)
    app.register_blueprint(student_bp, url_prefix='/student')
    app.register_blueprint(teacher_bp, url_prefix='/teacher') # Changed from 'teacher_routes.bp'
    app.register_blueprint(admin_bp, url_prefix='/admin') # Changed from admin_routes.bp

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
    return app, socketio # Return both app and socketio instance
