from flask import render_template, Response, session, url_for, request, flash, redirect, current_app
from . import bp
from app.utils import login_required, role_required
from app.sign_logic import generate_frames, get_stable_prediction, get_available_signs
from supabase import Client, PostgrestAPIError
from gotrue.errors import AuthApiError
from werkzeug.exceptions import NotFound

@bp.route('/dashboard')
@login_required
@role_required('Student')
def student_dashboard():
    print(f"Accessing Student Dashboard BP for user: {session.get('user_name')}")
    model_signs = get_available_signs()
    if model_signs:
        available_signs = model_signs
        print(f"Signs available from model: {available_signs}")
    else:
        print("Warning: Model classes not available. Using default sign list.")
        available_signs = [chr(i) for i in range(ord('A'), ord('Z') + 1)]
        available_signs.extend(['Hello', 'Thank You', 'I Love You'])
        available_signs = sorted(list(set(available_signs)))

    assignment_url = "#"


    return render_template(
        'StudentDashboard.html',
        available_signs=available_signs,
        assignment_url=assignment_url,
        user_name=session.get('user_name', 'Student')
    )

@bp.route('/assignment')
@login_required
@role_required('Student')
def student_assignment():
    """Renders the dedicated assignment page, listing all available assignments."""
    print(f"Accessing Student Assignment page for user: {session.get('user_name')}")
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Student')
    assignments_list = []

    if not supabase:
        flash('Supabase client not initialized. Cannot fetch assignments.', 'danger')
    else:
        try:
            # Fetch all assignments and join with subjects table to get subject_name
            # Assuming students can see assignments from all subjects for now.
            # A real-world scenario might filter by subjects the student is enrolled in.
            response = supabase.table('assignments') \
                               .select('*, subjects(name), lessons(title)') \
                               .order('due_date', desc=False) \
                               .execute()
            if response.data:
                assignments_list = response.data
            else:
                assignments_list = []
                if hasattr(response, 'error') and response.error:
                    flash(f"Error fetching assignments: {response.error.message}", "danger")
                else:
                    print("No assignments found or error in fetching.") # No assignments is not an error to flash

        except PostgrestAPIError as e:
            flash(f'Database error fetching assignments: {e.message}', 'danger')
            print(f"Supabase DB Error (Student Assignments): {e}")
        except Exception as e:
            flash('An unexpected error occurred while loading assignments.', 'danger')
            print(f"Unexpected Error (Student Assignments): {e}")
            
    return render_template(
        'StudentAssignment.html', 
        user_name=user_name,
        assignments=assignments_list
    )

@bp.route('/video_feed')
@login_required
@role_required('Student')
def video_feed():
    print("Request received for student video feed endpoint.")
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@bp.route('/get_prediction')
@login_required
@role_required('Student')
def get_prediction():
    prediction = get_stable_prediction()
    response = Response(prediction, mimetype='text/plain')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@bp.route('/settings')
@login_required
@role_required('Student')
def student_settings():
    """Renders the student settings page, fetching user email."""
    print(f"Accessing Student Settings page for user: {session.get('user_name')}")
    user_name = session.get('user_name', 'Student')
    user_email = "Not available"
    access_token = session.get('access_token')
    supabase: Client = current_app.supabase
    user_id = session.get('user_id')
    avatar_url = url_for('static', filename='Images/yvan.png')

    if access_token and supabase and user_id:
        try:
            user_response = supabase.auth.get_user(jwt=access_token)
            if user_response.user:
                user_email = user_response.user.email or "Email not set"
                print(f"Fetched user details for settings page: Email={user_email}")

                # Initialize profile attributes to be passed to template
                profile_first_name = session.get('user_name', 'Student') # Fallback
                profile_middle_name = None
                profile_last_name = ""


                profile_response = supabase.table('profiles') \
                                           .select('first_name, last_name, middle_name, avatar_path') \
                                           .eq('id', user_id) \
                                           .maybe_single() \
                                           .execute()

                if profile_response.data:
                    profile_data = profile_response.data
                    profile_first_name = profile_data.get('first_name', '')
                    profile_middle_name = profile_data.get('middle_name') # Will be None if not present or null
                    profile_last_name = profile_data.get('last_name', '')
                    
                    # Update session user_name if needed (without middle initial for general use)
                    session_user_name = f"{profile_first_name or ''} {profile_last_name or ''}".strip()
                    if session_user_name:
                        session['user_name'] = session_user_name
                    
                    user_name = session_user_name # user_name for sidebar can remain First Last

                    avatar_path = profile_data.get('avatar_path')
                    if avatar_path:
                        try:
                            avatar_url = supabase.storage.from_('avatars').get_public_url(avatar_path)
                            print(f"Generated public URL for avatar: {avatar_url}")
                        except Exception as storage_error:
                            print(f"Error generating public URL for {avatar_path}: {storage_error}")
                else:
                    print(f"No profile found in 'profiles' table for user_id: {user_id}")

            else:
                 print("Could not fetch user details using token for settings page.")
                 flash('Could not load user details. Session might be invalid.', 'warning')

        except AuthApiError as e:
            print(f"AuthApiError fetching user details for settings: {e}")
            flash('Authentication error fetching user details. Please log in again.', 'danger')
            if "Invalid JWT" in e.message or "expired" in e.message:
                 return redirect(url_for('auth.login'))
        except PostgrestAPIError as e:
            print(f"Database error fetching profile details: {e}")
            flash('Error loading profile information.', 'warning')
        except Exception as e:
            print(f"Unexpected error fetching user details for settings: {e}")
            flash('An error occurred loading your details.', 'warning')

    elif not access_token:
         print("No access token found in session for settings page.")
         flash('Session expired or invalid. Please log in again.', 'warning')
         return redirect(url_for('auth.login'))
    elif not user_id:
         print("No user ID found in session for settings page.")
         flash('User session invalid. Please log in again.', 'warning')
         return redirect(url_for('auth.login'))

    return render_template(
        'StudentSettings.html', 
        # Pass individual name parts for flexible display in template header
        profile_first_name=profile_first_name,
        profile_middle_name=profile_middle_name,
        profile_last_name=profile_last_name,
        user_name=user_name, # For sidebar, keep as First Last
        user_email=user_email, 
        avatar_url=avatar_url
    )


@bp.route('/my_progress')
@login_required
@role_required('Student')
def student_progress():
    """Renders the student progress page fetching data from Supabase."""
    print(f"Accessing Student Progress page for user: {session.get('user_name')}")
    supabase: Client = current_app.supabase
    user_id = session.get('user_id')
    user_name = session.get('user_name', 'Student')

    all_subjects = []

    if not user_id:
        flash('User session not found. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))

    if not supabase:
        flash('Supabase client not initialized. Cannot fetch progress.', 'danger')
        return render_template('StudentProgress.html', title='My Progress', all_subjects=all_subjects, user_name=user_name)

    try:
        print("Attempting to fetch all subjects for progress page...")
        try:
            subjects_response = supabase.table('subjects') \
                                        .select('id, name, description') \
                                        .order('name') \
                                        .execute()
            print(f"Raw response data for all_subjects fetch: data={subjects_response.data}")
            all_subjects = subjects_response.data or []
            print(f"Assigned all_subjects: {all_subjects}")
        except Exception as subj_e:
            flash('Error loading available subjects list.', 'warning')
            print(f"EXCEPTION fetching all subjects for progress page: {subj_e}")
            all_subjects = []


    except Exception as e:
        flash('An error occurred loading subject data.', 'danger')
        print(f"Error fetching subjects for progress page: {e}")
        all_subjects = []

    return render_template(
        'StudentProgress.html',
        title='My Progress',
        all_subjects=all_subjects,
        user_name=user_name
    )

from werkzeug.exceptions import NotFound

@bp.route('/subject/<int:subject_id>/lessons')
@login_required
@role_required('Student')
def view_subject_lessons(subject_id):
    """Renders the list of lessons for a specific subject."""
    print(f"Accessing lesson list for subject ID: {subject_id} for user: {session.get('user_name')}")
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Student')
    subject_name = "Subject Lessons"
    lessons_list = []

    if not supabase:
        flash('Supabase client not initialized. Cannot fetch lesson data.', 'danger')
        return render_template('StudentLessons.html', subject_id=subject_id, subject_name=subject_name, lessons=lessons_list, user_name=user_name)

    try:
        print(f"Fetching subject name for ID: {subject_id}")
        subject_response = supabase.table('subjects') \
                                   .select('name') \
                                   .eq('id', subject_id) \
                                   .maybe_single() \
                                   .execute()

        if subject_response.data:
            subject_name = subject_response.data.get('name', 'Subject Lessons')
            print(f"Found subject: {subject_name}")
        else:
            print(f"Subject with ID {subject_id} not found.")
            flash('Subject not found.', 'warning')
            return redirect(url_for('student.student_progress'))

        print(f"Fetching all lessons for subject ID: {subject_id} including their assignments")
        lessons_response = supabase.table('lessons') \
                                   .select('*, assignments(*)') \
                                   .eq('subject_id', subject_id) \
                                   .order('id') \
                                   .execute()

        if lessons_response and lessons_response.data:
            lessons_list = lessons_response.data
            print(f"Found {len(lessons_list)} lessons for subject {subject_id}.")
        else:
            lessons_list = []
            print(f"No lessons found for subject {subject_id}.")

    except PostgrestAPIError as e:
        flash(f'Database error fetching lesson list: {e.message}', 'danger')
        lessons_list = []
        print(f"Supabase DB Error fetching lesson list for subject {subject_id}: {e}")
    except Exception as e:
        flash('An unexpected error occurred while loading the lesson list.', 'danger')
        lessons_list = []
        print(f"Unexpected Error fetching lesson list for subject {subject_id}: {e}")

    return render_template(
        'StudentLessons.html',
        subject_id=subject_id,
        subject_name=subject_name,
        lessons=lessons_list,
        user_name=user_name
    )

@bp.route('/lesson/<int:lesson_id>/content')
@login_required
@role_required('Student')
def view_lesson_content(lesson_id):
    """Renders the content view for a specific lesson using StudentLessonView.html."""
    print(f"Accessing content for lesson ID: {lesson_id} for user: {session.get('user_name')}")
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Student')
    subject_name = "Lesson Content"
    lesson_data = None
    subject_id = None

    if not supabase:
        flash('Supabase client not initialized. Cannot fetch lesson content.', 'danger')
        return render_template('StudentLessonView.html', subject_id=subject_id, subject_name=subject_name, lesson_data=lesson_data, user_name=user_name)

    try:
        print(f"Fetching lesson details for lesson ID: {lesson_id}")
        lesson_response = supabase.table('lessons') \
                                  .select('title, description, content, subject_id, subjects(name)') \
                                  .eq('id', lesson_id) \
                                  .maybe_single() \
                                  .execute()

        if lesson_response and lesson_response.data:
            lesson_data = lesson_response.data
            subject_id = lesson_data.get('subject_id')
            print(f"Found lesson titled: {lesson_data.get('title')}")

            if lesson_data.get('subjects') and isinstance(lesson_data['subjects'], dict):
                subject_name = lesson_data['subjects'].get('name', subject_name)
            else:
                 if subject_id:
                     subj_resp = supabase.table('subjects').select('name').eq('id', subject_id).maybe_single().execute()
                     if subj_resp.data:
                         subject_name = subj_resp.data.get('name', subject_name)

            if not isinstance(lesson_data.get('content'), (list, dict)):
                 print(f"Warning: Lesson content for lesson {lesson_id} is not a list or dict: {type(lesson_data.get('content'))}")

        else:
            lesson_data = None
            print(f"No lesson found for lesson ID {lesson_id}.")
            flash('Lesson not found.', 'warning')
            return redirect(url_for('student.student_progress'))

    except PostgrestAPIError as e:
        flash(f'Database error fetching lesson content: {e.message}', 'danger')
        lesson_data = None
        print(f"Supabase DB Error fetching content for lesson {lesson_id}: {e}")
        return redirect(url_for('student.student_progress'))
    except Exception as e:
        flash('An unexpected error occurred while loading lesson content.', 'danger')
        print(f"Unexpected Error fetching content for lesson {lesson_id}: {e}")
        return redirect(url_for('student.student_progress'))

    return render_template(
        'StudentLessonView.html',
        subject_id=subject_id,
        subject_name=subject_name,
        lesson_data=lesson_data,
        user_name=user_name
    )

@bp.route('/update_profile', methods=['POST'])
@login_required
@role_required('Student')
def update_profile():
    """Handles profile picture upload."""
    from werkzeug.utils import secure_filename
    from datetime import datetime
    import os

    supabase: Client = current_app.supabase
    user_id = session.get('user_id')
    bucket_name = "avatars"

    if not user_id or not supabase:
        flash('Session invalid or Supabase client not available.', 'danger')
        return redirect(url_for('auth.login'))

    if 'profile_picture' not in request.files:
        flash('No profile picture file selected.', 'warning')
        return redirect(url_for('student.student_settings'))

    file = request.files['profile_picture']

    if file.filename == '':
        flash('No selected file.', 'warning')
        return redirect(url_for('student.student_settings'))

    if file:
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
        if '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions:

            filename = secure_filename(file.filename)
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            storage_path = f"{user_id}/{timestamp}_{filename}"

            try:
                print(f"Attempting to upload {filename} to Supabase Storage at path: {storage_path}")
                file_content = file.read()
                file.seek(0)

                upload_response = supabase.storage.from_(bucket_name).upload(
                    path=storage_path,
                    file=file_content,
                    file_options={"content-type": file.content_type}
                )
                print("Upload attempt finished.")

                print(f"File uploaded successfully. Updating profile table for user {user_id} with path: {storage_path}")
                update_data = {'avatar_path': storage_path}
                update_response = supabase.table('profiles').update(update_data).eq('id', user_id).execute()

                if update_response.data:
                     flash('Profile picture updated successfully!', 'success')
                     print(f"Profile table updated successfully for user {user_id}.")
                else:
                     flash('Profile picture uploaded, but database update failed. Please contact support.', 'warning')
                     print(f"Profile table update potentially failed for user {user_id} (no data returned). Response: {update_response}")

            except PostgrestAPIError as db_error:
                 flash(f'Database update failed: {db_error.message}', 'error')
                 print(f"Database error updating profile for user {user_id}: {db_error}")
                 try:
                     print(f"Attempting to remove orphaned file: {storage_path}")
                     supabase.storage.from_(bucket_name).remove([storage_path])
                 except Exception as remove_error:
                     print(f"Failed to remove orphaned file {storage_path} after DB error: {remove_error}")
            except Exception as e:
                flash(f'Error uploading file: {e}', 'error')
                print(f"Error during profile picture upload for user {user_id}: {e}")

        else:
            flash('Invalid file type. Allowed types: png, jpg, jpeg, gif.', 'danger')

    return redirect(url_for('student.student_settings'))

@bp.route('/assignment/<int:assignment_id>/view')
@login_required
@role_required('Student')
def view_assignment_student(assignment_id):
    """Renders the detailed view for a specific assignment for a student."""
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Student')
    assignment_details = None

    if not supabase:
        flash('Supabase client not initialized. Cannot fetch assignment details.', 'danger')
        return redirect(url_for('student.student_assignment'))

    try:
        response = supabase.table('assignments') \
                           .select('*, subjects(name), lessons(title)') \
                           .eq('id', assignment_id) \
                           .maybe_single() \
                           .execute()
        
        if response.data:
            assignment_details = response.data
        else:
            flash('Assignment not found.', 'warning')
            return redirect(url_for('student.student_assignment'))

    except PostgrestAPIError as e:
        flash(f'Database error fetching assignment details: {e.message}', 'danger')
        print(f"Supabase DB Error (View Student Assignment): {e}")
        return redirect(url_for('student.student_assignment'))
    except Exception as e:
        flash('An unexpected error occurred while loading the assignment.', 'danger')
        print(f"Unexpected Error (View Student Assignment): {e}")
        return redirect(url_for('student.student_assignment'))

    return render_template(
        'StudentViewAssignment.html',
        assignment=assignment_details,
        user_name=user_name
    )

@bp.route('/assignment/<int:assignment_id>/submit', methods=['POST'])
@login_required
@role_required('Student')
def submit_assignment_work(assignment_id):
    """Handles the submission of work for a specific assignment."""
    # This is a placeholder.
    # Actual implementation would handle file uploads to Supabase Storage (if any),
    # save submission details (file path/link, notes, student_id, assignment_id, submission_timestamp)
    # to the 'submissions' table.
    flash(f'Submission for assignment ID {assignment_id} received (not fully implemented).', 'info')
    # For now, redirect back to the assignment view page or the main assignment list.
    return redirect(url_for('student.view_assignment_student', assignment_id=assignment_id))


@bp.route('/change_password', methods=['POST'])
@login_required
@role_required('Student')
def change_password():
    """Handles the password change form submission using Supabase Auth."""
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    user_id = session.get('user_id')
    supabase: Client = current_app.supabase
    access_token = session.get('access_token')
    refresh_token = session.get('refresh_token')

    if not new_password:
        flash('New password cannot be empty.', 'danger')
        return redirect(url_for('student.student_settings'))

    if len(new_password) < 6:
         flash('New password must be at least 6 characters long.', 'danger')
         return redirect(url_for('student.student_settings'))

    if not user_id:
        flash('User session not found. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))

    if not supabase:
        flash('Supabase client not initialized. Cannot update password.', 'danger')
        return redirect(url_for('student.student_settings'))

    if not access_token:
        flash('User authentication token not found. Please log in again.', 'danger')
        print(f"Missing access token for user {user_id} during password change attempt.")
        return redirect(url_for('auth.login'))

    if not refresh_token:
        flash('User authentication refresh token not found. Please log in again.', 'danger')
        print(f"Missing refresh token for user {user_id} during password change attempt.")
        return redirect(url_for('auth.login'))

    try:
        print(f"Setting Supabase auth session for user {user_id} before password update.")
        supabase.auth.set_session(access_token=access_token, refresh_token=refresh_token)

        print(f"Attempting password update for the currently authenticated user.")
        update_response = supabase.auth.update_user(
             {"password": new_password}
        )

        if update_response.user:
            flash('Password updated successfully!', 'success')
            print(f"Password updated successfully for user associated with the token.")
        else:
            flash('Failed to update password. Please try again or re-login.', 'danger')
            print(f"Password update failed for user. Response: {update_response}")

    except AuthApiError as e:
        flash(f'Authentication error updating password: {e.message}', 'danger')
        print(f"Supabase Auth Error updating password: {e}")
        if "Invalid JWT" in e.message or "expired" in e.message:
             flash('Your session may have expired. Please log in again.', 'warning')
             return redirect(url_for('auth.login'))
    except Exception as e:
        flash('An unexpected error occurred while updating password.', 'danger')
        print(f"Unexpected Error updating password: {e}")

    return redirect(url_for('student.student_settings'))
