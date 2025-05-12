from flask import render_template, Response, session, url_for, request, flash, redirect, current_app
from . import bp
from app.utils import login_required, role_required
from app.sign_logic import generate_frames, get_stable_prediction, get_available_signs
from supabase import Client, PostgrestAPIError
from gotrue.errors import AuthApiError
from werkzeug.exceptions import NotFound
from werkzeug.utils import secure_filename
import os
import json 
from datetime import datetime, timezone, timedelta # Added timedelta

ASSIGNMENT_UPLOAD_FOLDER = 'app/static/uploads/assignments' 

@bp.route('/dashboard')
@login_required
@role_required('Student')
def student_dashboard():
    model_signs = get_available_signs()
    available_signs = model_signs if model_signs else sorted(list(set([chr(i) for i in range(ord('A'), ord('Z') + 1)] + ['Hello', 'Thank You', 'I Love You'])))
    return render_template(
        'StudentDashboard.html',
        available_signs=available_signs,
        user_name=session.get('user_name', 'Student')
    )

@bp.route('/assignment')
@login_required
@role_required('Student')
def student_assignment():
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Student')
    student_id = session.get('user_id')
    assignments_with_status = []

    if not student_id:
        flash('User session invalid. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))
    if not supabase:
        flash('Database connection not available.', 'danger')
        return render_template('StudentAssignment.html', user_name=user_name, assignments=assignments_with_status)

    try:
        assignments_response = supabase.table('assignments') \
                                   .select('*, subjects(name), lessons(title)') \
                                   .order('due_date', desc=False) \
                                   .execute()
        
        if assignments_response and assignments_response.data:
            all_assignments = assignments_response.data
            assignment_ids = [a['id'] for a in all_assignments]
            submissions_map = {}
            if assignment_ids:
                submissions_response = supabase.table('submissions') \
                                           .select('assignment_id, id, status, grade') \
                                           .eq('student_id', student_id) \
                                           .in_('assignment_id', assignment_ids) \
                                           .execute()
                if submissions_response and submissions_response.data:
                    submissions_map = {
                        sub['assignment_id']: {
                            'submission_id': sub['id'], 
                            'status': sub.get('status', 'Submitted'), 
                            'grade': sub.get('grade')
                        } for sub in submissions_response.data
                    }
            
            for assignment_item in all_assignments: 
                submission_info = submissions_map.get(assignment_item['id'])
                if submission_info:
                    assignment_item['submission_status'] = submission_info['status']
                    assignment_item['submission_id'] = submission_info['submission_id']
                    assignment_item['grade'] = submission_info['grade']
                else:
                    assignment_item['submission_status'] = 'Not Submitted'
                    assignment_item['submission_id'] = None
                    assignment_item['grade'] = None
                assignments_with_status.append(assignment_item)
        elif hasattr(assignments_response, 'error') and assignments_response.error:
            flash(f"Error fetching assignments: {assignments_response.error.message}", "danger")

    except PostgrestAPIError as e: 
        flash(f'Database error fetching assignments: {e.message}', 'danger')
        print(f"Supabase DB Error (Student Assignments): {e}")
    except Exception as e: 
        flash(f'Error loading assignments: {e}', 'danger')
        print(f"Error in student_assignment: {e}")
            
    return render_template('StudentAssignment.html', user_name=user_name, assignments=assignments_with_status)

@bp.route('/video_feed')
@login_required
@role_required('Student')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@bp.route('/get_prediction')
@login_required
@role_required('Student')
def get_prediction():
    prediction_data = get_stable_prediction() 
    return Response(prediction_data, mimetype='application/json')

@bp.route('/settings')
@login_required
@role_required('Student')
def student_settings():
    user_name = session.get('user_name', 'Student')
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
                db_first_name = profile_data.get('first_name','')
                db_last_name = profile_data.get('last_name','')
                if db_first_name or db_last_name:
                    user_name = f"{db_first_name} {db_last_name}".strip()
                session['user_name'] = user_name 
        except Exception as e:
            flash(f'Error fetching profile details: {e}', 'warning')
            print(f"Error in student_settings profile fetch: {e}")
    else:
        flash('Session invalid. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))

    avatar_url = profile_data.get('avatar_path')
    if avatar_url and not avatar_url.startswith('http'): 
        try:
            avatar_url = supabase.storage.from_('avatars').get_public_url(avatar_url)
        except Exception as e: 
            print(f"Error getting public URL for avatar: {e}")
            avatar_url = url_for('static', filename='Images/yvan.png') 
    elif not avatar_url:
        avatar_url = url_for('static', filename='Images/yvan.png')

    return render_template(
        'StudentSettings.html', 
        profile_first_name=profile_data.get('first_name'),
        profile_middle_name=profile_data.get('middle_name'),
        profile_last_name=profile_data.get('last_name'),
        user_name=user_name, 
        user_email=user_email, 
        avatar_url=avatar_url
    )

@bp.route('/my_progress')
@login_required
@role_required('Student')
def student_progress():
    user_name = session.get('user_name', 'Student')
    supabase: Client = current_app.supabase
    all_subjects = []
    if not supabase:
        flash('Database connection not available.', 'danger')
        return render_template('StudentProgress.html', title='My Progress', user_name=user_name, all_subjects=all_subjects) 
    
    try:
        print("Attempting to fetch all subjects for progress page...")
        subjects_response = supabase.table('subjects').select('id, name, description').order('name').execute()
        
        if subjects_response and subjects_response.data:
            all_subjects = subjects_response.data
        elif hasattr(subjects_response, 'error') and subjects_response.error:
            flash(f"Error fetching subjects for progress: {subjects_response.error.message}", "warning")
            print(f"Error fetching subjects for progress page: {subjects_response.error}")
            
    except Exception as e:
        flash(f"Error loading subjects: {e}", "warning")
        print(f"Error in student_progress fetching subjects: {e}")
            
    return render_template('StudentProgress.html', title='My Progress', user_name=user_name, all_subjects=all_subjects)


@bp.route('/subject/<int:subject_id>/lessons')
@login_required
@role_required('Student')
def view_subject_lessons(subject_id):
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Student')
    student_id = session.get('user_id') 
    subject = None
    lessons_with_assignment_status = []

    if not student_id:
        flash("User session not found.", "danger")
        return redirect(url_for('auth.login'))
    if not supabase:
        flash('Database connection not available.', 'danger')
        return render_template('StudentLessons.html', subject=subject, lessons=lessons_with_assignment_status, user_name=user_name, subject_name="Lessons")

    try:
        subject_res = supabase.table('subjects').select('*').eq('id', subject_id).maybe_single().execute()
        if not (subject_res and subject_res.data): 
            flash('Subject not found.', 'warning'); return redirect(url_for('student.student_progress'))
        subject = subject_res.data
        
        lessons_res = supabase.table('lessons').select('*, assignments(*)').eq('subject_id', subject_id).order('id').execute()
        
        if lessons_res and lessons_res.data:
            for lesson in lessons_res.data:
                if lesson.get('assignments'):
                    assignment_ids_for_lesson = [asn['id'] for asn in lesson['assignments']]
                    if assignment_ids_for_lesson:
                        submissions_res = supabase.table('submissions') \
                            .select('assignment_id, id') \
                            .eq('student_id', student_id) \
                            .in_('assignment_id', assignment_ids_for_lesson) \
                            .execute()
                        
                        submissions_map = {}
                        if submissions_res and submissions_res.data:
                            submissions_map = {sub['assignment_id']: sub['id'] for sub in submissions_res.data}

                        for asn in lesson['assignments']:
                            asn['student_submission_id'] = submissions_map.get(asn['id'])
                lessons_with_assignment_status.append(lesson)
        
    except Exception as e:
        flash(f"Error loading lessons: {e}", 'danger')
        print(f"Error in view_subject_lessons: {e}")
        
    return render_template('StudentLessons.html', subject=subject, lessons=lessons_with_assignment_status, user_name=user_name, subject_name=subject.get('name') if subject else "Lessons")


@bp.route('/lesson/<int:lesson_id>/content')
@login_required
@role_required('Student')
def view_lesson_content(lesson_id):
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Student')
    lesson = None
    try:
        lesson_res = supabase.table('lessons').select('*, subjects(name)').eq('id', lesson_id).maybe_single().execute()
        if not (lesson_res and lesson_res.data): 
            flash('Lesson not found.', 'warning'); return redirect(url_for('student.student_progress'))
        lesson = lesson_res.data
    except Exception as e:
        flash(f"Error loading lesson content: {e}", 'danger')
        print(f"Error in view_lesson_content: {e}")
    subject_name_from_join = lesson.get('subjects', {}).get('name') if lesson and lesson.get('subjects') else "Lesson"
    return render_template('StudentLessonView.html', lesson_data=lesson, user_name=user_name, subject_name=subject_name_from_join)


@bp.route('/update_profile', methods=['POST'])
@login_required
@role_required('Student')
def update_profile():
    supabase: Client = current_app.supabase
    user_id = session.get('user_id')
    bucket_name = "avatars"
    file = request.files.get('profile_picture')

    if not file or file.filename == '':
        flash('No file selected.', 'warning'); return redirect(url_for('student.student_settings'))

    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
    if '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions:
        filename = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        storage_path = f"{user_id}/{timestamp}_{filename}"
        try:
            file_content = file.read()
            supabase.storage.from_(bucket_name).upload(
                path=storage_path, file=file_content, 
                file_options={"content-type": file.content_type, "cache-control": "3600", "upsert": "false"}
            )
            update_profiles_response = supabase.table('profiles').update({'avatar_path': storage_path}).eq('id', user_id).execute()
            
            if update_profiles_response and hasattr(update_profiles_response, 'error') and update_profiles_response.error:
                 flash(f'Database update failed: {update_profiles_response.error.message}', 'danger')
            elif update_profiles_response: 
                 flash('Profile picture updated successfully!', 'success')
            else: 
                 flash('Profile picture uploaded, but database update response was unexpected.', 'warning')

        except Exception as e:
            flash(f'Error uploading file: {e}', 'danger'); print(f"Upload error: {e}")
    else:
        flash('Invalid file type.', 'danger')
    return redirect(url_for('student.student_settings'))


@bp.route('/assignment/<int:assignment_id>/view')
@login_required
@role_required('Student')
def view_assignment_student(assignment_id):
    supabase: Client = current_app.supabase
    assignment_data = None 
    try:
        assignment_res = supabase.table('assignments').select('*, subjects(name), lessons(title)').eq('id', assignment_id).maybe_single().execute()
        if not (assignment_res and assignment_res.data): 
            flash('Assignment not found.', 'warning'); return redirect(url_for('student.student_assignment'))
        assignment_data = assignment_res.data
    except Exception as e:
        flash(f"Error loading assignment: {e}", 'danger'); print(f"Error in view_assignment_student: {e}")
        return redirect(url_for('student.student_assignment'))
    return render_template('StudentViewAssignment.html', assignment=assignment_data, user_name=session.get('user_name'))


@bp.route('/assignment/<int:assignment_id>/submit', methods=['POST'])
@login_required
@role_required('Student')
def submit_assignment_work(assignment_id):
    supabase: Client = current_app.supabase
    student_id = session.get('user_id')
    form_notes = request.form.get('submission_notes')
    file = request.files.get('submission_file')
    sign_attempts_json = request.form.get('sign_attempts_json')
    
    file_path_to_store = None 
    recorded_sign_attempts = []
    average_confidence = 0.0
    calculated_grade = 0.0
    current_assignment_id = int(assignment_id)

    if not student_id:
        flash('User session invalid.', 'danger'); return redirect(url_for('auth.login'))
    if not supabase:
        flash('Database connection error.', 'danger'); return redirect(url_for('student.view_assignment_student', assignment_id=current_assignment_id))

    if not os.path.exists(ASSIGNMENT_UPLOAD_FOLDER):
        try: os.makedirs(ASSIGNMENT_UPLOAD_FOLDER)
        except OSError as e: flash(f'Upload directory error: {e}', 'danger'); return redirect(url_for('student.view_assignment_student', assignment_id=current_assignment_id))

    if file and file.filename:
        if '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt', 'mp4', 'mov', 'avi'}:
            filename = secure_filename(file.filename)
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
            unique_filename = f"{student_id}_{current_assignment_id}_{timestamp}_{filename}"
            file_path_on_disk = os.path.join(ASSIGNMENT_UPLOAD_FOLDER, unique_filename)
            try:
                file.save(file_path_on_disk)
                # file_path_to_store = os.path.join('uploads/assignments', unique_filename).replace('\\', '/') # If saving to DB
                print(f"File saved to: {file_path_on_disk}") 
            except Exception as e:
                flash(f'Error saving file: {e}', 'danger')
                return redirect(url_for('student.view_assignment_student', assignment_id=current_assignment_id))
        else:
            flash('Invalid file type.', 'danger')
            return redirect(url_for('student.view_assignment_student', assignment_id=current_assignment_id))

    if sign_attempts_json:
        try:
            recorded_sign_attempts = json.loads(sign_attempts_json)
            if recorded_sign_attempts:
                valid_attempts = [attempt for attempt in recorded_sign_attempts if isinstance(attempt, dict) and attempt.get('confidence') is not None]
                if valid_attempts:
                    total_confidence = sum(attempt.get('confidence', 0.0) for attempt in valid_attempts)
                    average_confidence = total_confidence / len(valid_attempts)
                    calculated_grade = round(average_confidence * 100, 2)
            print(f"Attempts: {recorded_sign_attempts}, Avg Conf: {average_confidence}, Grade: {calculated_grade}")
        except Exception as e:
            flash('Error processing sign attempts data.', 'warning'); print(f"Error parsing sign_attempts_json: {e}")

    submission_id = None
    try:
        existing_submission_res = supabase.table('submissions') \
            .select('id') \
            .eq('student_id', student_id) \
            .eq('assignment_id', current_assignment_id) \
            .maybe_single().execute()

        if existing_submission_res and hasattr(existing_submission_res, 'error') and existing_submission_res.error:
            raise PostgrestAPIError(existing_submission_res.error)
        
        is_update = False
        if existing_submission_res and existing_submission_res.data:
            submission_id = existing_submission_res.data['id']
            is_update = True
            print(f"Found existing submission ID: {submission_id}. Preparing for update.")

        data_for_db = {
            'student_id': student_id,
            'assignment_id': current_assignment_id,
            'submission_content': form_notes,
            'submitted_at': datetime.utcnow().isoformat(),
            'grade': calculated_grade,
            'average_confidence': average_confidence,
            'status': 'Auto-Graded'
            # 'file_path': file_path_to_store, # Omitted as 'submissions' table doesn't have this column
        }

        if is_update:
            print(f"Updating submission ID {submission_id} with: {data_for_db}")
            db_response = supabase.table('submissions').update(data_for_db).eq('id', submission_id).execute()
        else: 
            print(f"Inserting new submission with: {data_for_db}")
            db_response = supabase.table('submissions').insert(data_for_db, returning="representation").execute()

        if db_response and hasattr(db_response, 'error') and db_response.error: 
            raise PostgrestAPIError(db_response.error)

        if not is_update: 
            if db_response and db_response.data and len(db_response.data) > 0: 
                submission_id = db_response.data[0]['id']
                print(f"New submission created with ID: {submission_id}")
            else: 
                print("Insert operation did not return data. Attempting manual fetch of submission ID...")
                fetch_res = supabase.table('submissions').select('id') \
                    .eq('student_id', student_id) \
                    .eq('assignment_id', current_assignment_id) \
                    .order('submitted_at', desc=True).limit(1).maybe_single().execute()
                if fetch_res and hasattr(fetch_res, 'error') and fetch_res.error:
                    raise PostgrestAPIError(fetch_res.error)
                if fetch_res and fetch_res.data:
                    submission_id = fetch_res.data['id']
                    print(f"Manually fetched submission ID: {submission_id}")
                else:
                    flash('Submission created, but failed to confirm submission ID. Please check assignments.', 'danger')
                    return redirect(url_for('student.student_assignment'))
        
        if submission_id:
            if recorded_sign_attempts:
                attempts_to_insert = [{
                    'submission_id': submission_id, 
                    'student_id': student_id,
                    'related_assignment_id': current_assignment_id, 
                    'sign_recognized': att.get('sign'),
                    'confidence_score': att.get('confidence'), 
                    'timestamp': datetime.utcnow().isoformat() 
                } for att in recorded_sign_attempts if isinstance(att, dict) and att.get('sign') is not None]
                
                if attempts_to_insert:
                    sign_attempts_res = supabase.table('sign_attempts').insert(attempts_to_insert, returning="minimal").execute()
                    if sign_attempts_res and hasattr(sign_attempts_res, 'error') and sign_attempts_res.error: 
                        flash(f"Submission saved, but error saving sign attempts: {sign_attempts_res.error.message}", 'warning')
                    else:
                        print(f"Saved {len(attempts_to_insert)} sign attempts for submission {submission_id}")
            
            if calculated_grade >= 100.0: 
                badge_res = supabase.table('badges').select('id').eq('name', 'Perfect Score').maybe_single().execute()
                if badge_res and badge_res.data and not (hasattr(badge_res, 'error') and badge_res.error):
                    badge_id = badge_res.data['id']
                    user_badge_res = supabase.table('user_badges').select('id').eq('user_id', student_id).eq('badge_id', badge_id).eq('submission_id', submission_id).maybe_single().execute()
                    if not (user_badge_res and user_badge_res.data) and not (hasattr(user_badge_res, 'error') and user_badge_res.error) :
                        badge_insert_res = supabase.table('user_badges').insert({'user_id': student_id, 'badge_id': badge_id, 'submission_id': submission_id, 'earned_at': datetime.utcnow().isoformat()}).execute()
                        if badge_insert_res and hasattr(badge_insert_res, 'error') and badge_insert_res.error: 
                             flash(f"Error awarding badge: {badge_insert_res.error.message}", 'warning')
                        else:
                             flash('Congratulations! You earned the "Perfect Score" badge!', 'success')
            
            flash('Assignment submitted and auto-graded successfully!', 'success')
            return redirect(url_for('student.view_submission_details', submission_id=submission_id))
        else: 
            flash('Failed to obtain submission ID after operation.', 'danger')
            return redirect(url_for('student.student_assignment'))

    except PostgrestAPIError as e:
        flash(f'Database operation error: {e.message} (Code: {e.code if hasattr(e, "code") else "N/A"})', 'danger')
        print(f"Supabase DB Error (Submit Assignment): {e}, Details: {getattr(e, 'details', '')}, Hint: {getattr(e, 'hint', '')}")
    except Exception as e:
        flash(f'An unexpected error occurred: {e}', 'danger')
        print(f"Unexpected Error (Submit Assignment): {e}")
    
    return redirect(url_for('student.view_assignment_student', assignment_id=current_assignment_id))


@bp.route('/submission/<int:submission_id>')
@login_required
@role_required('Student')
def view_submission_details(submission_id):
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Student')
    student_id = session.get('user_id')
    submission = None 

    if not student_id: flash('User session invalid.', 'danger'); return redirect(url_for('auth.login'))
    if not supabase: flash('Database connection error.', 'danger'); return redirect(url_for('student.student_assignment'))

    try:
        submission_res = supabase.table('submissions') \
                           .select('*, grade, average_confidence, status, assignments(*, subjects(name), lessons(title))') \
                           .eq('id', submission_id) \
                           .eq('student_id', student_id) \
                           .maybe_single().execute()
        
        if submission_res and submission_res.data: 
            submission = submission_res.data
            if 'submission_content' in submission and 'notes' not in submission: 
                submission['notes'] = submission['submission_content']
            
            submission['grade'] = submission.get('grade') 
            submission['average_confidence'] = submission.get('average_confidence')
            submission['status'] = submission.get('status', 'Submitted') # Default if not present

            if submission.get('submitted_at'):
                try:
                    submitted_dt_str = submission['submitted_at']
                    # Ensure it's timezone-aware for fromisoformat
                    if not ('+' in submitted_dt_str or submitted_dt_str.endswith('Z')):
                        submitted_dt_str += '+00:00' # Assume UTC if no offset
                    elif submitted_dt_str.endswith('Z'): 
                        submitted_dt_str = submitted_dt_str[:-1] + '+00:00'
                    
                    # Truncate microseconds to 6 digits
                    if '.' in submitted_dt_str:
                        main_part, fractional_part = submitted_dt_str.split('.', 1)
                        # Separate fractional seconds from timezone
                        if '+' in fractional_part:
                            ms_part, tz_part = fractional_part.split('+', 1)
                            submitted_dt_str = f"{main_part}.{ms_part[:6]}+{tz_part}"
                        elif '-' in fractional_part:
                             # Check if it's a timezone minus by looking for ':' after it
                            dash_idx = fractional_part.rfind('-')
                            if dash_idx > 0 and fractional_part.count(':') > 0 : # Check for colon after last dash
                                ms_part = fractional_part[:dash_idx]
                                tz_part = fractional_part[dash_idx:]
                                submitted_dt_str = f"{main_part}.{ms_part[:6]}{tz_part}"
                            else: # No timezone, just fractional seconds
                                submitted_dt_str = f"{main_part}.{fractional_part[:6]}"
                        else: # Only fractional seconds, no timezone part after '.'
                            submitted_dt_str = f"{main_part}.{fractional_part[:6]}"
                            
                    submitted_dt_utc = datetime.fromisoformat(submitted_dt_str)
                    
                    # Convert to PHT (UTC+8)
                    pht_tz = timezone(timedelta(hours=8)) # Corrected: use timedelta directly
                    submitted_dt_pht = submitted_dt_utc.astimezone(pht_tz)
                    submission['formatted_submitted_at'] = submitted_dt_pht.strftime("%b %d, %Y, %I:%M %p")
                except ValueError as ve:
                    print(f"ValueError parsing submitted_at '{submission['submitted_at']}': {ve}")
                    # Fallback to simpler formatting if complex parsing fails
                    try:
                        fallback_dt = datetime.strptime(submission['submitted_at'][:19], "%Y-%m-%dT%H:%M:%S")
                        submission['formatted_submitted_at'] = fallback_dt.strftime("%b %d, %Y, %I:%M %p UTC")
                    except:
                        submission['formatted_submitted_at'] = submission['submitted_at'] # Raw if everything fails
            else:
                submission['formatted_submitted_at'] = "N/A"
        else:
            flash('Submission not found or permission denied.', 'warning')
            return redirect(url_for('student.student_assignment'))
            
    except Exception as e:
        flash(f'Error fetching submission: {e}', 'danger')
        print(f"Error in view_submission_details: {e}")
        return redirect(url_for('student.student_assignment'))

    return render_template('StudentAssignmentSubmissionView.html', submission=submission, user_name=user_name)


@bp.route('/change_password', methods=['POST'])
@login_required
@role_required('Student')
def change_password():
    new_password = request.form.get('new_password')
    supabase: Client = current_app.supabase
    access_token = session.get('access_token') 

    if not new_password or len(new_password) < 6:
        flash('New password must be at least 6 characters long.', 'danger')
        return redirect(url_for('student.student_settings'))
    if not access_token or not supabase: 
        flash('Session or connection error. Please re-login.', 'danger')
        return redirect(url_for('auth.login'))

    try:
        supabase.auth.update_user({"password": new_password}) 
        flash('Password updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating password: {e}', 'danger')
        print(f"Password update error: {e}")

    return redirect(url_for('student.student_settings'))
