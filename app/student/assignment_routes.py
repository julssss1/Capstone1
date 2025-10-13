from flask import render_template, session, url_for, request, flash, redirect, current_app
from . import bp  # Use . to import bp from the current package (student)
from app.utils import login_required, role_required
from supabase import Client, PostgrestAPIError
import json
from datetime import datetime, timezone, timedelta

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
        # Get enrolled subjects (subject-based enrollment)
        enrollments_response = supabase.table('enrollments') \
            .select('subject_id') \
            .eq('student_id', student_id) \
            .eq('status', 'active') \
            .execute()
        
        if not (enrollments_response and enrollments_response.data):
            flash("You are not enrolled in any subjects yet. Please contact your administrator.", "info")
            return render_template('StudentAssignment.html', user_name=user_name, assignments=[])
        
        # Get subject IDs from enrollments
        subject_ids = [e['subject_id'] for e in enrollments_response.data]
        
        # Get assignments only from those subjects
        assignments_response = supabase.table('assignments') \
                                   .select('*, subjects(name), lessons(title)') \
                                   .in_('subject_id', subject_ids) \
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
    
    now_utc = datetime.now(timezone.utc)
    return render_template('StudentViewAssignment.html', assignment=assignment_data, user_name=session.get('user_name'), now_utc=now_utc)

@bp.route('/assignment/<int:assignment_id>/submit', methods=['POST'])
@login_required
@role_required('Student')
def submit_assignment_work(assignment_id):
    supabase: Client = current_app.supabase
    student_id = session.get('user_id')
    form_notes = request.form.get('submission_notes')
    sign_attempts_json = request.form.get('sign_attempts_json')
    
    recorded_sign_attempts = []
    average_confidence = 0.0
    calculated_grade = 0.0
    current_assignment_id = int(assignment_id)

    if not student_id:
        flash('User session invalid.', 'danger'); return redirect(url_for('auth.login'))
    if not supabase:
        flash('Database connection error.', 'danger'); return redirect(url_for('student.view_assignment_student', assignment_id=current_assignment_id))

    try:
        assignment_res = supabase.table('assignments').select('due_date').eq('id', current_assignment_id).single().execute()
        if not (assignment_res and assignment_res.data):
            flash('Assignment not found.', 'danger')
            return redirect(url_for('student.student_assignment'))
        
        due_date_str = assignment_res.data.get('due_date')
        if due_date_str:
            due_date = datetime.fromisoformat(due_date_str)
            if datetime.now(timezone.utc) > due_date:
                flash('This assignment is past the due date and can no longer be submitted.', 'danger')
                return redirect(url_for('student.view_assignment_student', assignment_id=current_assignment_id))
    except Exception as e:
        flash(f"Could not verify assignment due date: {e}", 'danger')
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
                    pht_tz = timezone(timedelta(hours=8)) 
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
