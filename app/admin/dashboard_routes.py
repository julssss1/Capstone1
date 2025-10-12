from flask import render_template, session, flash, current_app, redirect, url_for, request
from . import bp
from app.utils import login_required, role_required
from supabase import Client, PostgrestAPIError
from werkzeug.utils import secure_filename
from datetime import datetime, timezone, timedelta

@bp.route('/dashboard')
@login_required
@role_required('Admin')
def admin_dashboard():
    print(f"Accessing Admin Dashboard BP for user: {session.get('user_name')}")
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Admin')
    student_count = 0
    teacher_count = 0
    subject_count = 0
    password_reset_requests = []

    if not supabase:
        flash('Supabase client not initialized. Cannot load dashboard data.', 'danger')
    else:
        try:
            student_response = supabase.table('profiles') \
                                       .select('id', count='exact') \
                                       .eq('role', 'Student') \
                                       .execute()
            student_count = student_response.count or 0

            teacher_response = supabase.table('profiles') \
                                       .select('id', count='exact') \
                                       .eq('role', 'Teacher') \
                                       .execute()
            teacher_count = teacher_response.count or 0

            subject_response = supabase.table('subjects') \
                                       .select('id', count='exact') \
                                       .execute()
            subject_count = subject_response.count or 0

            # Fetch pending password reset requests
            reset_requests_response = supabase.table('password_reset_requests') \
                                              .select('*') \
                                              .eq('status', 'pending') \
                                              .order('requested_at', desc=True) \
                                              .execute()
            password_reset_requests = reset_requests_response.data or []
            
            # Format timestamps to PHT (Philippine Time, UTC+8)
            for request in password_reset_requests:
                if request.get('requested_at'):
                    try:
                        requested_dt_str = request['requested_at']
                        # Ensure timezone-aware
                        if not ('+' in requested_dt_str or requested_dt_str.endswith('Z')):
                            requested_dt_str += '+00:00'
                        elif requested_dt_str.endswith('Z'):
                            requested_dt_str = requested_dt_str[:-1] + '+00:00'
                        
                        # Truncate microseconds to 6 digits
                        if '.' in requested_dt_str:
                            main_part, fractional_part = requested_dt_str.split('.', 1)
                            if '+' in fractional_part:
                                ms_part, tz_part = fractional_part.split('+', 1)
                                requested_dt_str = f"{main_part}.{ms_part[:6]}+{tz_part}"
                            elif '-' in fractional_part:
                                dash_idx = fractional_part.rfind('-')
                                if dash_idx > 0 and fractional_part.count(':') > 0:
                                    ms_part = fractional_part[:dash_idx]
                                    tz_part = fractional_part[dash_idx:]
                                    requested_dt_str = f"{main_part}.{ms_part[:6]}{tz_part}"
                                else:
                                    requested_dt_str = f"{main_part}.{fractional_part[:6]}"
                            else:
                                requested_dt_str = f"{main_part}.{fractional_part[:6]}"
                        
                        requested_dt_utc = datetime.fromisoformat(requested_dt_str)
                        
                        # Convert to PHT (UTC+8)
                        pht_tz = timezone(timedelta(hours=8))
                        requested_dt_pht = requested_dt_utc.astimezone(pht_tz)
                        request['requested_at'] = requested_dt_pht.strftime("%b %d, %Y, %I:%M %p")
                    except (ValueError, Exception) as e:
                        print(f"Error formatting requested_at '{request['requested_at']}': {e}")
                        # Keep original if formatting fails
                        pass

        except PostgrestAPIError as e:
            flash(f'Database error loading dashboard counts: {e.message}', 'danger')
            print(f"Supabase DB Error (Admin Dashboard): {e}")
        except Exception as e:
            flash('An unexpected error occurred loading dashboard data.', 'danger')
            print(f"Unexpected Error (Admin Dashboard): {e}")

    return render_template(
        'AdminDashboard.html',
        student_count=student_count,
        teacher_count=teacher_count,
        subject_count=subject_count,
        user_name=user_name,
        password_reset_requests=password_reset_requests
        )

@bp.route('/handle-password-reset/<int:request_id>')
@login_required
@role_required('Admin')
def handle_password_reset(request_id):
    """Handle password reset request - find user and redirect to edit page"""
    supabase: Client = current_app.supabase
    
    if not supabase:
        flash('Supabase client not initialized.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
    
    try:
        # Get the reset request
        reset_request = supabase.table('password_reset_requests') \
                                .select('*') \
                                .eq('id', request_id) \
                                .single() \
                                .execute()
        
        if not reset_request.data:
            flash('Password reset request not found.', 'danger')
            return redirect(url_for('admin.admin_dashboard'))
        
        email = reset_request.data['email']
        
        # Find user by email using RPC or by listing users
        # Since we can't directly query auth.users, we'll use execute SQL
        user_query = supabase.rpc('get_user_by_email', {'email_param': email}).execute()
        
        if user_query.data and len(user_query.data) > 0:
            user_id = user_query.data[0]['id']
            # Store the request ID in session to mark as complete later
            session['pending_reset_request_id'] = request_id
            flash(f'Editing user account for: {email}', 'info')
            return redirect(url_for('admin.edit_user', user_id=user_id))
        else:
            flash(f'No user account found for email: {email}', 'warning')
            # Mark as completed anyway since user doesn't exist
            supabase.table('password_reset_requests') \
                    .update({'status': 'completed'}) \
                    .eq('id', request_id) \
                    .execute()
            return redirect(url_for('admin.admin_dashboard'))
            
    except Exception as e:
        print(f"Error handling password reset request: {e}")
        flash('An error occurred while processing the request.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))

@bp.route('/complete-password-reset/<int:request_id>')
@login_required
@role_required('Admin')
def complete_password_reset(request_id):
    """Mark password reset request as completed"""
    supabase: Client = current_app.supabase
    
    if not supabase:
        flash('Supabase client not initialized.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
    
    try:
        supabase.table('password_reset_requests') \
                .update({'status': 'completed'}) \
                .eq('id', request_id) \
                .execute()
        
        # Clear the pending reset request from session
        session.pop('pending_reset_request_id', None)
        
        flash('Password reset request marked as completed.', 'success')
    except Exception as e:
        print(f"Error completing password reset request: {e}")
        flash('An error occurred while completing the request.', 'danger')
    
    return redirect(url_for('admin.admin_dashboard'))

@bp.route('/settings')
@login_required
@role_required('Admin')
def admin_settings():
    """Admin settings page for profile and password management"""
    user_name = session.get('user_name', 'Admin')
    user_email = "Not available"
    access_token = session.get('access_token')
    supabase: Client = current_app.supabase
    user_id = session.get('user_id')
    profile_data = {}

    if access_token and supabase and user_id:
        try:
            user_auth_details = supabase.auth.get_user(jwt=access_token)
            if user_auth_details and user_auth_details.user:
                user_email = user_auth_details.user.email or "Email not set"
            
            profile_res = supabase.table('profiles').select('*').eq('id', user_id).maybe_single().execute()
            if profile_res and profile_res.data:
                profile_data = profile_res.data
                db_first_name = profile_data.get('first_name', '')
                db_last_name = profile_data.get('last_name', '')
                if db_first_name or db_last_name:
                    user_name = f"{db_first_name} {db_last_name}".strip()
                session['user_name'] = user_name
        except Exception as e:
            flash(f'Error fetching profile details: {e}', 'warning')
            print(f"Error in admin_settings profile fetch: {e}")
    else:
        flash('Session invalid. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))

    avatar_url = profile_data.get('avatar_path')
    if avatar_url and not avatar_url.startswith('http') and not avatar_url.startswith('/static/'):
        try:
            avatar_url = supabase.storage.from_('avatars').get_public_url(avatar_url)
        except Exception as e:
            print(f"Error getting public URL for avatar: {e}")
            avatar_url = url_for('static', filename='Images/default_avatar.png')
    elif not avatar_url:
        avatar_url = url_for('static', filename='Images/default_avatar.png')

    return render_template(
        'AdminSettings.html',
        profile_first_name=profile_data.get('first_name'),
        profile_middle_name=profile_data.get('middle_name'),
        profile_last_name=profile_data.get('last_name'),
        user_name=user_name,
        user_email=user_email,
        avatar_url=avatar_url
    )

@bp.route('/update_profile', methods=['POST'])
@login_required
@role_required('Admin')
def admin_update_profile():
    supabase: Client = current_app.supabase
    user_id = session.get('user_id')
    bucket_name = "avatars"

    if not user_id:
        flash('Critical error: User ID not found in session. Please re-login.', 'danger')
        return redirect(url_for('admin.admin_settings'))
    
    file = request.files.get('profile_picture')

    if not file or file.filename == '':
        flash('No file selected.', 'warning')
        return redirect(url_for('admin.admin_settings'))

    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
    if '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions:
        filename = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        storage_path = f"{user_id}/{timestamp}_{filename}"

        try:
            file_content = file.read()
            
            upload_api_response = supabase.storage.from_(bucket_name).upload(
                path=storage_path, file=file_content,
                file_options={"content-type": file.content_type, "cache-control": "3600", "upsert": "false"}
            )

            update_profiles_response = supabase.table('profiles').update({'avatar_path': storage_path}).eq('id', user_id).execute()
            
            if update_profiles_response and hasattr(update_profiles_response, 'error') and update_profiles_response.error:
                flash(f'Database update failed: {update_profiles_response.error.message}', 'danger')
            elif update_profiles_response and update_profiles_response.data:
                flash('Profile picture updated successfully!', 'success')
            else:
                flash('Profile picture uploaded, but database update response was unexpected.', 'warning')

        except PostgrestAPIError as pg_e:
            flash(f'Database error after upload: {pg_e.message}', 'danger')
        except Exception as e:
            flash(f'Error uploading file: {str(e)}', 'danger')
    else:
        flash('Invalid file type.', 'danger')
    return redirect(url_for('admin.admin_settings'))

@bp.route('/change_password', methods=['POST'])
@login_required
@role_required('Admin')
def admin_change_password():
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    supabase: Client = current_app.supabase
    access_token = session.get('access_token')

    if not new_password or len(new_password) < 6:
        flash('New password must be at least 6 characters long.', 'danger')
        return redirect(url_for('admin.admin_settings'))
    
    if not confirm_password:
        flash('Please confirm your new password.', 'danger')
        return redirect(url_for('admin.admin_settings'))
    
    if new_password != confirm_password:
        flash('Passwords do not match. Please try again.', 'danger')
        return redirect(url_for('admin.admin_settings'))
    
    if not access_token or not supabase:
        flash('Session or connection error. Please re-login.', 'danger')
        return redirect(url_for('auth.login'))

    try:
        supabase.auth.update_user({"password": new_password})
        flash('Password updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating password: {str(e)}', 'danger')
        print(f"Password update error: {e}")

    return redirect(url_for('admin.admin_settings'))
