# app/teacher/dashboard_routes.py
from flask import render_template, request, session, redirect, url_for, flash, current_app
from . import bp  # Import blueprint from current package (__init__.py)
from app.utils import login_required, role_required
from supabase import Client, PostgrestAPIError
from werkzeug.utils import secure_filename
from datetime import datetime, timezone, timedelta

@bp.route('/dashboard')
@login_required
@role_required('Teacher')
def teacher_dashboard():
    print(f"Accessing Teacher Dashboard BP for user: {session.get('user_name')}")
    supabase: Client = current_app.supabase
    teacher_id = session.get('user_id')
    user_name = session.get('user_name', 'Teacher')

    subjects_taught_count = 0
    total_students_count = 0
    pending_assignments_count = 0 

    if not teacher_id:
        flash('User session invalid. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))

    if not supabase:
        flash('Supabase client not initialized. Cannot load dashboard data.', 'danger')
    else:
        try:
            student_response = supabase.table('profiles') \
                                       .select('id', count='exact') \
                                       .eq('role', 'Student') \
                                       .execute()
            total_students_count = student_response.count or 0

            # Get subjects taught by this teacher
            subjects_response = supabase.table('subjects') \
                                        .select('id', count='exact') \
                                        .eq('teacher_id', teacher_id) \
                                        .execute()
            subjects_taught_count = subjects_response.count or 0
            
            pending_assignments_count = 0
            if subjects_taught_count > 0 and subjects_response.data:
                teacher_subject_ids = [s['id'] for s in subjects_response.data]

                if teacher_subject_ids:
                    assignments_for_teacher_res = supabase.table('assignments') \
                        .select('id') \
                        .in_('subject_id', teacher_subject_ids) \
                        .execute()

                    if assignments_for_teacher_res.data:
                        assignment_ids_for_teacher = [a['id'] for a in assignments_for_teacher_res.data]
                        if assignment_ids_for_teacher:
                            # Counts rows where (feedback is null) OR (feedback = '')
                            or_filter_string = "feedback.is.null,feedback.eq." # eq. means equals empty string
                            pending_review_res = supabase.table('submissions') \
                                .select('id', count='exact') \
                                .in_('assignment_id', assignment_ids_for_teacher) \
                                .or_(or_filter_string) \
                                .execute()
                            pending_assignments_count = pending_review_res.count or 0
        except PostgrestAPIError as e:
            flash(f'Database error loading dashboard: {e.message}', 'danger')
            print(f"Supabase DB Error (Teacher Dashboard) for {teacher_id}: {e}")
        except Exception as e:
            flash('An unexpected error occurred loading dashboard data.', 'danger')
            print(f"Unexpected Error (Teacher Dashboard) for {teacher_id}: {e}")

    return render_template(
        'TeacherDashboard.html',
        pending_assignments_count=pending_assignments_count,
        total_students_count=total_students_count,
        subjects_taught_count=subjects_taught_count,
        user_name=user_name
        )

@bp.route('/settings')
@login_required
@role_required('Teacher')
def teacher_settings():
    """Teacher settings page for profile and password management"""
    user_name = session.get('user_name', 'Teacher')
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
            print(f"Error in teacher_settings profile fetch: {e}")
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
        'TeacherSettings.html',
        profile_first_name=profile_data.get('first_name'),
        profile_middle_name=profile_data.get('middle_name'),
        profile_last_name=profile_data.get('last_name'),
        user_name=user_name,
        user_email=user_email,
        avatar_url=avatar_url
    )

@bp.route('/update_profile', methods=['POST'])
@login_required
@role_required('Teacher')
def teacher_update_profile():
    supabase: Client = current_app.supabase
    user_id = session.get('user_id')
    bucket_name = "avatars"

    if not user_id:
        flash('Critical error: User ID not found in session. Please re-login.', 'danger')
        return redirect(url_for('teacher.teacher_settings'))
    
    file = request.files.get('profile_picture')

    if not file or file.filename == '':
        flash('No file selected.', 'warning')
        return redirect(url_for('teacher.teacher_settings'))

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
    return redirect(url_for('teacher.teacher_settings'))

@bp.route('/change_password', methods=['POST'])
@login_required
@role_required('Teacher')
def teacher_change_password():
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    supabase: Client = current_app.supabase
    access_token = session.get('access_token')

    if not new_password or len(new_password) < 6:
        flash('New password must be at least 6 characters long.', 'danger')
        return redirect(url_for('teacher.teacher_settings'))
    
    if not confirm_password:
        flash('Please confirm your new password.', 'danger')
        return redirect(url_for('teacher.teacher_settings'))
    
    if new_password != confirm_password:
        flash('Passwords do not match. Please try again.', 'danger')
        return redirect(url_for('teacher.teacher_settings'))
    
    if not access_token or not supabase:
        flash('Session or connection error. Please re-login.', 'danger')
        return redirect(url_for('auth.login'))

    try:
        supabase.auth.update_user({"password": new_password})
        flash('Password updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating password: {str(e)}', 'danger')
        print(f"Password update error: {e}")

    return redirect(url_for('teacher.teacher_settings'))
