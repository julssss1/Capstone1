from functools import wraps
from flask import session, flash, redirect, url_for, abort

def login_required(f):
    """Decorator to ensure user is logged in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_role' not in session:
            flash('Please log in to access this page.', 'warning')
            # Use the correct endpoint name including blueprint
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(required_role):
    """Decorator to ensure user has the correct role."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_role' not in session:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login')) # Redirect to auth blueprint login

            user_role = session.get('user_role')
            if user_role != required_role:
                # flash(f'Access denied. You need the "{required_role}" role for this page.', 'danger') # Removed flash, 403 page will show message
                abort(403) # Trigger the 403 error handler

            return f(*args, **kwargs)
        return decorated_function
    return decorator
