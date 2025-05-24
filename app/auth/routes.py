from flask import render_template, redirect, url_for, flash, request, session, current_app
from . import bp
from app.utils import login_required
from app.sign_logic import release_resources as release_camera_resources 
from supabase import Client, PostgrestAPIError
from gotrue.errors import AuthApiError

@bp.route('/login', methods=['GET', 'POST'])
def login():
    supabase: Client = current_app.supabase 

    # Redirect if already logged in
    if 'user_role' in session:
        return redirect(url_for('home'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Email and password are required.', 'warning')
            return redirect(url_for('auth.login'))

        if not supabase:
             flash('Supabase client not initialized. Cannot log in.', 'danger')
             return redirect(url_for('auth.login'))

        try:
            # Attempt to sign in using Supabase Auth
            auth_response = supabase.auth.sign_in_with_password({"email": email, "password": password})

            if auth_response.user and auth_response.session:
                user_id = auth_response.user.id

                # Fetch user role and name from the 'profiles' table
                try:
                    # Select first_name and last_name instead of full_name
                    profile_response = supabase.table('profiles').select('role, first_name, last_name').eq('id', user_id).single().execute()

                    if profile_response.data:
                        user_role = profile_response.data.get('role')
                        # Combine first and last name, provide default if either is missing
                        first_name = profile_response.data.get('first_name')
                        last_name = profile_response.data.get('last_name')
                        if first_name and last_name:
                            user_name = f"{first_name} {last_name}"
                        elif first_name:
                            user_name = first_name
                        elif last_name:
                            user_name = last_name
                        else:
                            user_name = 'User' # Default if both are missing

                        if not user_role:
                             flash('User role not found in profile. Please contact admin.', 'danger')
                             supabase.auth.sign_out() # Sign out if profile is incomplete
                             return redirect(url_for('auth.login'))

                        # Clear previous session and store new info
                        session.clear()
                        session['user_id'] = user_id
                        session['user_role'] = user_role
                        session['user_name'] = user_name
                        # Store Supabase tokens in Flask session
                        session['access_token'] = auth_response.session.access_token
                        session['refresh_token'] = auth_response.session.refresh_token
                        print("DEBUG: Supabase tokens stored in session.") # Added for debugging

                        flash(f"Login successful! Welcome, {user_name}.", 'success')

                        # Redirect based on role
                        if user_role == 'Student':
                            return redirect(url_for('student.student_dashboard'))
                        elif user_role == 'Teacher':
                            return redirect(url_for('teacher.teacher_dashboard'))
                        elif user_role == 'Admin':
                            return redirect(url_for('admin.admin_dashboard'))
                        else:
                            flash('Unknown user role assigned.', 'danger')
                            supabase.auth.sign_out()
                            session.clear()
                            return redirect(url_for('auth.login'))
                    else:
                        flash('User profile not found. Please contact admin.', 'danger')
                        supabase.auth.sign_out() # Sign out if profile doesn't exist
                        return redirect(url_for('auth.login'))

                except PostgrestAPIError as e:
                     flash(f'Error fetching user profile: {e.message}', 'danger')
                     print(f"Error fetching profile for user {user_id}: {e}")
                     supabase.auth.sign_out()
                     return redirect(url_for('auth.login'))
                except Exception as e:
                     flash(f'An unexpected error occurred while fetching profile.', 'danger')
                     print(f"Unexpected error fetching profile for user {user_id}: {e}")
                     supabase.auth.sign_out()
                     return redirect(url_for('auth.login'))

            else:
                flash('Login failed. Please check your credentials.', 'danger')
                return redirect(url_for('auth.login'))

        except AuthApiError as e:
            # Handle specific Supabase Auth errors
            if "Invalid login credentials" in e.message:
                 flash('Invalid email or password.', 'danger')
            elif "Email not confirmed" in e.message:
                 flash('Please confirm your email address before logging in.', 'warning')
            else:
                 flash(f'Authentication error: {e.message}', 'danger')
                 print(f"Supabase Auth Error: {e}")
            return redirect(url_for('auth.login'))
        except Exception as e:
            # Catch other potential errors (network issues, etc.)
            flash('An unexpected error occurred during login.', 'danger')
            print(f"Unexpected Login Error: {e}")
            return redirect(url_for('auth.login'))

    # GET request
    return render_template('loginpage.html')

@bp.route('/logout')
# @login_required # Removed decorator
def logout():
    # Get user name for flash message before clearing session
    user_name = session.get('user_name', 'User') 

    # Release camera and related resources first
    try:
        print("Calling release_camera_resources from logout...")
        release_camera_resources()
        print("Camera resources signaled for release.")
    except Exception as e:
        print(f"Error calling release_camera_resources during logout: {e}")
        flash('Could not properly stop camera feed, but proceeding with logout.', 'warning')

    supabase: Client = current_app.supabase

    if supabase:
        try:
            supabase.auth.sign_out()
            # Sign out successful on Supabase side
        except AuthApiError as e:
            # Log error but proceed with clearing Flask session anyway
            print(f"Supabase sign out error: {e}")
            flash('Error during Supabase logout, but session cleared locally.', 'warning')
        except Exception as e:
            print(f"Unexpected error during Supabase sign out: {e}")
            flash('Unexpected error during Supabase logout.', 'warning')

    session.clear() # Clear Flask session regardless of Supabase outcome
    flash(f'You have been logged out, {user_name}.', 'info')
    return redirect(url_for('auth.login'))
