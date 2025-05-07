from flask import Flask, session, redirect, url_for, flash, render_template
import os
import threading 
from supabase import create_client, Client 


from . import sign_logic

def create_app(config_class='config.Config'):
    """Application Factory Function"""
    app = Flask(__name__, instance_relative_config=True)

    # Load configuration
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
        
        if sign_logic.model is None or sign_logic.hands is None:
             print("*"*60)
             print("WARNING: Sign recognition initialization failed. Some features might not work.")
             print("*"*60)
          

    # Register Blueprints
    from .auth import routes as auth_routes
    from .student import routes as student_routes
    from .teacher import routes as teacher_routes
    from .admin import routes as admin_routes

    app.register_blueprint(auth_routes.bp) 
    app.register_blueprint(student_routes.bp, url_prefix='/student')
    app.register_blueprint(teacher_routes.bp, url_prefix='/teacher')
    app.register_blueprint(admin_routes.bp, url_prefix='/admin')

    
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

    # --- Register Error Handlers ---
    @app.errorhandler(404)
    def page_not_found(e):
        flash("The page you requested was not found (404).", "warning")
        # return render_template('404.html'), 404
        if 'user_role' in session:
            role = session['user_role']
            if role == 'Student': return redirect(url_for('student.student_dashboard')), 302
            elif role == 'Teacher': return redirect(url_for('teacher.teacher_dashboard')), 302
            elif role == 'Admin': return redirect(url_for('admin.admin_dashboard')), 302
        return redirect(url_for('auth.login')), 302

    @app.errorhandler(403)
    def forbidden(e):
        flash("You do not have permission to access this page (403).", "danger")
        # return render_template('403.html'), 403
        if 'user_role' in session:
            role = session['user_role']
            if role == 'Student': return redirect(url_for('student.student_dashboard')), 302
            elif role == 'Teacher': return redirect(url_for('teacher.teacher_dashboard')), 302
            elif role == 'Admin': return redirect(url_for('admin.admin_dashboard')), 302
        return redirect(url_for('auth.login')), 302

    @app.errorhandler(500)
    def internal_server_error(e):
         print(f"Internal Server Error: {e}")
         flash("An internal server error occurred. Please try again later.", "danger")      
         # return render_template('500.html'), 500    
         if 'user_role' in session:
             role = session['user_role']
             if role == 'Student': return redirect(url_for('student.student_dashboard')), 302
             elif role == 'Teacher': return redirect(url_for('teacher.teacher_dashboard')), 302
             elif role == 'Admin': return redirect(url_for('admin.admin_dashboard')), 302
         return redirect(url_for('auth.login')), 302
    print("App factory finished.")
    return app
