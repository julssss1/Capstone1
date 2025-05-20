# app/teacher/grading_routes.py
from flask import render_template, request, session, redirect, url_for, flash, current_app
from . import bp  # Import blueprint from current package (__init__.py)
from app.utils import login_required, role_required, check_and_award_badges
from supabase import Client, PostgrestAPIError
from datetime import datetime, timezone, timedelta

def _format_timestamp_for_display(timestamp_str):
    if not timestamp_str:
        return "N/A"
    try:
        # Ensure it's timezone-aware for fromisoformat
        if not ('+' in timestamp_str or timestamp_str.endswith('Z') or '-' in timestamp_str[10:]): # Check for offset or Z
             timestamp_str += '+00:00' # Assume UTC if no offset
        elif timestamp_str.endswith('Z'): 
            timestamp_str = timestamp_str[:-1] + '+00:00'
        
        # Truncate microseconds to 6 digits if present
        if '.' in timestamp_str:
            main_part, fractional_part = timestamp_str.split('.', 1)
            tz_char = None
            # Find timezone separator (+ or -) if it exists after the fractional part
            if '+' in fractional_part: tz_char = '+'
            elif '-' in fractional_part:
                # Ensure the dash is for timezone, not part of the date/time itself
                # A simple check: if a colon exists after the last dash, it's likely a timezone offset
                last_dash_idx = fractional_part.rfind('-')
                if last_dash_idx != -1 and ':' in fractional_part[last_dash_idx:]:
                    tz_char = '-'
            
            if tz_char:
                ms_part, tz_part_val = fractional_part.split(tz_char, 1)
                timestamp_str = f"{main_part}.{ms_part[:6]}{tz_char}{tz_part_val}"
            else: # No explicit timezone offset after fractional seconds
                timestamp_str = f"{main_part}.{fractional_part[:6]}"
        
        dt_utc = datetime.fromisoformat(timestamp_str)
        pht_tz = timezone(timedelta(hours=8)) # PHT is UTC+8
        dt_pht = dt_utc.astimezone(pht_tz)
        return dt_pht.strftime("%b %d, %Y, %I:%M %p PHT")
    except ValueError as ve:
        print(f"ValueError parsing timestamp '{timestamp_str}': {ve}")
        try: # Fallback to simpler UTC formatting if detailed parsing fails
            fallback_dt = datetime.strptime(timestamp_str[:19], "%Y-%m-%dT%H:%M:%S")
            return fallback_dt.strftime("%b %d, %Y, %I:%M %p UTC")
        except: # Raw if all fails
            return timestamp_str 

@bp.route('/gradebook')
@login_required
@role_required('Teacher')
def teacher_gradebook():
    supabase: Client = current_app.supabase
    teacher_id = session.get('user_id')
    user_name = session.get('user_name', 'Teacher')
    selected_subject_id_str = request.args.get('subject_filter') 
    grades_to_display = []
    subjects = []
    selected_subject_name = "All Subjects" 

    if not teacher_id:
        flash('User session invalid. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))

    if not supabase:
        flash('Supabase client not initialized.', 'danger')
        return render_template('Teacher-GradeTable.html', subjects=subjects, grades=grades_to_display, 
                               selected_subject_id=selected_subject_id_str, selected_subject_name=selected_subject_name, user_name=user_name)

    try:
        subjects_response = supabase.table('subjects') \
                                    .select('id, name') \
                                    .eq('teacher_id', teacher_id) \
                                    .order('name') \
                                    .execute()
        subjects = subjects_response.data or []

        if selected_subject_id_str:
            try:
                selected_subject_id = int(selected_subject_id_str)
                subject = next((s for s in subjects if s['id'] == selected_subject_id), None)
                if subject:
                    selected_subject_name = subject['name']
                else: # Subject not found or not taught by this teacher
                    flash(f"Invalid subject selected or you don't teach subject ID {selected_subject_id_str}.", "warning")
                    selected_subject_id = None 
                    selected_subject_name = "All Subjects"
                
                if selected_subject_id: # Proceed only if a valid subject is selected
                    grades_response = supabase.table('submissions') \
                                              .select('*, profiles(first_name, last_name), assignments!inner(title, subject_id)') \
                                              .eq('assignments.subject_id', selected_subject_id) \
                                              .execute()
                    raw_submissions = grades_response.data or []
                    for sub in raw_submissions:
                        profile = sub.get('profiles')
                        sub['student_display_name'] = f"{profile['first_name']} {profile['last_name']}".strip() if profile else "Unknown Student"
                        sub['formatted_submitted_at'] = _format_timestamp_for_display(sub.get('submitted_at'))
                        grades_to_display.append(sub)
            except ValueError:
                flash("Invalid subject filter value.", "warning")
            except PostgrestAPIError as e:
                flash(f'Database error loading grades: {e.message}', 'danger')
            except Exception as e: # Catch other potential errors during processing
                flash(f'An error occurred while processing grades: {str(e)}', 'danger')
    except PostgrestAPIError as e:
        flash(f'Database error loading subjects: {e.message}', 'danger')
    except Exception as e:
        flash(f'An unexpected error occurred: {str(e)}', 'danger')

    return render_template(
        'Teacher-GradeTable.html',
        subjects=subjects, 
        grades=grades_to_display, 
        selected_subject_id=selected_subject_id_str, 
        selected_subject_name=selected_subject_name,
        user_name=user_name
        )

@bp.route('/submission/<int:submission_id>/review', methods=['GET'])
@login_required
@role_required('Teacher')
def review_submission(submission_id):
    supabase: Client = current_app.supabase
    teacher_id = session.get('user_id')
    user_name = session.get('user_name', 'Teacher')
    submission_details = None

    if not teacher_id: return redirect(url_for('auth.login'))
    if not supabase:
        flash('Database connection error.', 'danger')
        return redirect(url_for('teacher.teacher_gradebook'))

    try:
        submission_response = supabase.table('submissions') \
            .select('*, profiles(first_name, last_name), assignments!inner(*, subjects!inner(name, teacher_id), lessons(title))') \
            .eq('id', submission_id) \
            .eq('assignments.subjects.teacher_id', teacher_id) \
            .maybe_single() \
            .execute()

        if submission_response and submission_response.data:
            submission_details = submission_response.data
            submission_details['formatted_submitted_at'] = _format_timestamp_for_display(submission_details.get('submitted_at'))
        else:
            flash('Submission not found or you do not have permission to review it.', 'warning')
            return redirect(url_for('teacher.teacher_gradebook'))
            
    except PostgrestAPIError as e:
        flash(f'Database error fetching submission: {e.message}', 'danger')
        return redirect(url_for('teacher.teacher_gradebook'))
    except Exception as e:
        flash(f'An unexpected error occurred: {e}', 'danger')
        return redirect(url_for('teacher.teacher_gradebook'))

    return render_template(
        'TeacherAssignmentSubmissionView.html',
        submission=submission_details,
        user_name=user_name
    )

@bp.route('/submission/<int:submission_id>/update_feedback', methods=['POST'])
@login_required
@role_required('Teacher')
def update_submission_feedback(submission_id):
    supabase: Client = current_app.supabase
    teacher_id = session.get('user_id')
    
    feedback_text = request.form.get('feedback_text')
    override_grade_str = request.form.get('override_grade')
    new_status = request.form.get('submission_status')

    if not teacher_id: return redirect(url_for('auth.login'))
    if not supabase:
        flash('Database connection error.', 'danger')
        return redirect(url_for('teacher.review_submission', submission_id=submission_id))

    try:
        submission_check_response = supabase.table('submissions') \
            .select('id, student_id, grade, status, assignments!inner(subjects!inner(teacher_id))') \
            .eq('id', submission_id) \
            .eq('assignments.subjects.teacher_id', teacher_id) \
            .maybe_single() \
            .execute()

        if not (submission_check_response and submission_check_response.data):
            flash('Submission not found or permission denied.', 'danger')
            return redirect(url_for('teacher.teacher_gradebook'))

        original_submission_data = submission_check_response.data
        update_data = {}
        if feedback_text is not None: update_data['feedback'] = feedback_text
        
        if override_grade_str:
            try:
                grade = float(override_grade_str)
                if not (0 <= grade <= 100):
                    flash('Override grade must be between 0 and 100.', 'danger')
                    return redirect(url_for('teacher.review_submission', submission_id=submission_id))
                update_data['grade'] = grade
            except ValueError:
                flash('Invalid grade format.', 'danger')
                return redirect(url_for('teacher.review_submission', submission_id=submission_id))
        
        if new_status: update_data['status'] = new_status
        
        if not update_data:
            flash('No changes to save.', 'info')
            return redirect(url_for('teacher.review_submission', submission_id=submission_id))

        update_response = supabase.table('submissions').update(update_data).eq('id', submission_id).execute()

        # Safely check for PostgREST error
        returned_error_obj = getattr(update_response, 'error', None)
        if returned_error_obj:
            # Construct a dictionary for PostgrestAPIError as it expects a dict
            error_dict_for_api_error = {
                "message": getattr(returned_error_obj, 'message', str(returned_error_obj)),
                "code": getattr(returned_error_obj, 'code', ''),
                "details": getattr(returned_error_obj, 'details', ''),
                "hint": getattr(returned_error_obj, 'hint', ''),
            }
            print(f"Supabase PostgREST Error on update: {error_dict_for_api_error}") # Log for server-side debugging
            raise PostgrestAPIError(error_dict_for_api_error)
        
        # Use original_submission_data for student_id, and updated values for grade/status for badge logic
        final_grade_for_badge = update_data.get('grade', original_submission_data.get('grade'))
        final_status_for_badge = update_data.get('status', original_submission_data.get('status'))

        if original_submission_data.get('student_id') and final_grade_for_badge is not None and final_status_for_badge:
            check_and_award_badges(
                submission_id=submission_id, # Pass submission_id
                student_id=original_submission_data['student_id'],
                grade=final_grade_for_badge,
                status=final_status_for_badge,
                supabase_client=supabase
            )
        flash('Feedback and grade updated successfully!', 'success')
    except PostgrestAPIError as e:
        flash(f'Database error: {e.message}', 'danger')
    except Exception as e:
        flash(f'An unexpected error occurred: {e}', 'danger')
    
    return redirect(url_for('teacher.review_submission', submission_id=submission_id))

@bp.route('/assignment/<int:assignment_id>/submissions')
@login_required
@role_required('Teacher')
def view_assignment_submissions(assignment_id):
    supabase: Client = current_app.supabase
    teacher_id = session.get('user_id')
    user_name = session.get('user_name', 'Teacher')
    submissions_list = []
    assignment_title = "Submissions"
    subject_name = "Unknown"

    if not teacher_id: return redirect(url_for('auth.login'))
    if not supabase:
        flash('Database error.', 'danger')
        return redirect(url_for('teacher.teacher_assignment_list'))

    try:
        assignment_response = supabase.table('assignments') \
            .select('title, subjects!inner(name, teacher_id)') \
            .eq('id', assignment_id) \
            .eq('subjects.teacher_id', teacher_id) \
            .maybe_single() \
            .execute()

        if not (assignment_response and assignment_response.data):
            flash('Assignment not found or permission denied.', 'warning')
            return redirect(url_for('teacher.teacher_assignment_list'))

        assignment_title = assignment_response.data.get('title', assignment_title)
        if assignment_response.data.get('subjects'):
             subject_name = assignment_response.data['subjects'].get('name', subject_name)

        submissions_response = supabase.table('submissions') \
            .select('*, profiles(first_name, last_name)') \
            .eq('assignment_id', assignment_id) \
            .order('submitted_at', desc=True) \
            .execute()
            
        raw_submissions = submissions_response.data or []
        for sub in raw_submissions:
            profile = sub.get('profiles')
            sub['student_display_name'] = f"{profile['first_name']} {profile['last_name']}".strip() if profile else "Unknown"
            sub['formatted_submitted_at'] = _format_timestamp_for_display(sub.get('submitted_at'))
            submissions_list.append(sub)
    except PostgrestAPIError as e:
        flash(f'Database error: {e.message}', 'danger')
    except Exception as e:
        flash(f'An unexpected error: {e}', 'danger')
    
    return render_template(
        'TeacherAssignmentSubmissions.html', 
        submissions=submissions_list,
        assignment_title=assignment_title,
        subject_name=subject_name,
        assignment_id=assignment_id,
        user_name=user_name
    )
