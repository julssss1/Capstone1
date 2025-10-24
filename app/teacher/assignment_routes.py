# app/teacher/assignment_routes.py
from flask import render_template, request, session, redirect, url_for, flash, current_app, jsonify
from . import bp  # Import blueprint from current package (__init__.py)
from app.utils import login_required, role_required
from supabase import Client, PostgrestAPIError
from datetime import datetime, timezone, timedelta

@bp.route('/api/get-lessons-by-subject/<int:subject_id>')
@login_required
@role_required('Teacher')
def get_lessons_by_subject(subject_id):
    """API endpoint to fetch lessons for a subject without page refresh"""
    supabase: Client = current_app.supabase
    teacher_id = session.get('user_id')
    
    if not teacher_id:
        return jsonify({'success': False, 'message': 'User session invalid.'}), 401
    
    if not supabase:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500
    
    try:
        # First verify the teacher owns this subject
        subject_response = supabase.table('subjects') \
                                   .select('id') \
                                   .eq('id', subject_id) \
                                   .eq('teacher_id', teacher_id) \
                                   .maybe_single() \
                                   .execute()
        
        if not subject_response.data:
            return jsonify({'success': False, 'message': 'Subject not found or unauthorized.', 'lessons': []}), 403
        
        # Fetch lessons for this subject
        lessons_response = supabase.table('lessons') \
                                   .select('id, title') \
                                   .eq('subject_id', subject_id) \
                                   .order('title') \
                                   .execute()
        
        lessons = lessons_response.data or []
        return jsonify({'success': True, 'lessons': lessons}), 200
        
    except PostgrestAPIError as e:
        return jsonify({'success': False, 'message': f'Database error: {e.message}', 'lessons': []}), 500
    except Exception as e:
        print(f"Error fetching lessons for subject {subject_id}: {e}")
        return jsonify({'success': False, 'message': 'An unexpected error occurred.', 'lessons': []}), 500

@bp.route('/assignment/create/<int:subject_id>') # Changed from lesson_id to subject_id for clarity
@login_required
@role_required('Teacher')
def create_assignment_for_subject(subject_id): # Renamed from create_assignment_for_lesson
     supabase: Client = current_app.supabase
     teacher_id = session.get('user_id')
     subject_name = f"Subject ID {subject_id}"
     can_create = False
     if supabase and teacher_id:
         try:
             subject_response = supabase.table('subjects') \
                                       .select('name') \
                                       .eq('id', subject_id) \
                                       .eq('teacher_id', teacher_id) \
                                       .maybe_single() \
                                       .execute()
             if subject_response.data:
                 subject_name = subject_response.data['name']
                 can_create = True
         except Exception as e:
             print(f"Error checking subject ownership for create_assignment_for_subject: {e}")

     if can_create:
         flash(f"Create assignment for '{subject_name}'.", "info")
         return redirect(url_for('teacher.create_assignment', subject_id=subject_id))
     else:
         flash(f"Subject with ID {subject_id} not found or not taught by you.", "warning")
         return redirect(url_for('teacher.teacher_lessons')) # Or teacher_dashboard

@bp.route('/assignment/create', methods=['GET', 'POST'])
@login_required
@role_required('Teacher')
def create_assignment():
    supabase: Client = current_app.supabase
    teacher_id = session.get('user_id')
    user_name = session.get('user_name', 'Teacher')
    subjects = []
    lessons_for_subject = [] # Lessons associated with the selected subject
    pre_selected_subject_id = request.args.get('subject_id', type=int)
    pre_selected_lesson_id = request.args.get('lesson_id', type=int) # For potential future use if assignments are tied to specific lessons within a subject

    if not teacher_id:
        flash('User session invalid. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))

    if not supabase:
        flash('Supabase client not initialized. Cannot create assignment.', 'danger')
        return redirect(url_for('teacher.teacher_dashboard'))

    try:
        subjects_response = supabase.table('subjects') \
                                    .select('id, name') \
                                    .eq('teacher_id', teacher_id) \
                                    .order('name') \
                                    .execute()
        subjects = subjects_response.data or []
        
        # If a subject is pre-selected, fetch its lessons
        if pre_selected_subject_id:
            subject_exists_for_teacher = any(s['id'] == pre_selected_subject_id for s in subjects)
            if subject_exists_for_teacher:
                lessons_response = supabase.table('lessons') \
                                           .select('id, title') \
                                           .eq('subject_id', pre_selected_subject_id) \
                                           .order('title') \
                                           .execute()
                lessons_for_subject = lessons_response.data or []
            else:
                flash("Pre-selected subject not found or not taught by you.", "warning")
                pre_selected_subject_id = None # Reset if invalid

    except Exception as e:
        flash('Error fetching data for assignment creation.', 'danger')
        print(f"Error fetching data for teacher {teacher_id} in create_assignment: {e}")

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        subject_id_form = request.form.get('subject_id', type=int)
        lesson_id_form = request.form.get('lesson_id', type=int) 
        due_date = request.form.get('due_date')
        correct_answers = request.form.get('correct_answers', '')

        # Enhanced validation
        validation_errors = []
        
        if not title:
            validation_errors.append('Assignment title is required.')
        elif len(title) < 3:
            validation_errors.append('Assignment title must be at least 3 characters long.')
        
        if not description:
            validation_errors.append('Assignment description is required.')
        elif len(description) < 10:
            validation_errors.append('Assignment description must be at least 10 characters long.')
        
        if not subject_id_form:
            validation_errors.append('Subject selection is required.')
        
        if not lesson_id_form:
            validation_errors.append('Lesson selection is required.')
        
        if not due_date:
            validation_errors.append('Due date is required.')
        
        if not correct_answers or not correct_answers.strip():
            validation_errors.append('Expected Answer/Words is required.')
        elif len(correct_answers.strip()) < 2:
            validation_errors.append('Expected Answer/Words must be at least 2 characters long.')
        
        if validation_errors:
            for error in validation_errors:
                flash(error, 'danger')
            return redirect(url_for('teacher.create_assignment', 
                                    subject_id=pre_selected_subject_id, 
                                    lesson_id=pre_selected_lesson_id))

        assignment_data = {
            'title': title,
            'description': description,
            'subject_id': subject_id_form,
            'due_date': due_date,
            'correct_answers': correct_answers.strip() if correct_answers else None,
            # 'teacher_id': teacher_id # Ensure your 'assignments' table has this if you want to link directly
        }
        if lesson_id_form: # Only add lesson_id if it was selected and is valid
            assignment_data['lesson_id'] = lesson_id_form

        try:
            insert_response = supabase.table('assignments').insert(assignment_data).execute()
            if insert_response.data:
                flash('Assignment created successfully!', 'success')
                return redirect(url_for('teacher.manage_subject_content', subject_id=subject_id_form))
            else:
                error_msg = "Failed to create assignment."
                if hasattr(insert_response, 'error') and insert_response.error:
                     error_msg += f" Database error: {insert_response.error.message}"
                flash(error_msg, 'danger')

        except PostgrestAPIError as e:
            flash(f'Database error creating assignment: {e.message}', 'danger')
            print(f"Supabase DB Error (Create Assignment POST) for teacher {teacher_id}: {e}")
        except Exception as e:
            flash('An unexpected error occurred creating the assignment.', 'danger')
            print(f"Unexpected Error (Create Assignment POST) for teacher {teacher_id}: {e}")
        
        return redirect(url_for('teacher.create_assignment', 
                                subject_id=pre_selected_subject_id, 
                                lesson_id=pre_selected_lesson_id))

    return render_template(
        'TeacherAssignment.html',
        subjects=subjects,
        lessons_for_subject=lessons_for_subject,
        pre_selected_subject_id=pre_selected_subject_id,
        pre_selected_lesson_id=pre_selected_lesson_id,
        user_name=user_name
        )

@bp.route('/assignments/list')
@login_required
@role_required('Teacher')
def teacher_assignment_list():
    supabase: Client = current_app.supabase
    teacher_id = session.get('user_id')
    user_name = session.get('user_name', 'Teacher')
    assignments_with_counts = []
    
    # Get filter parameters
    filter_subject_id = request.args.get('subject_filter', type=int)
    filter_lesson_id = request.args.get('lesson_filter', type=int)

    if not teacher_id:
        flash('User session invalid. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))

    if not supabase:
        flash('Supabase client not initialized.', 'danger')
        return render_template('TeacherAssignmentList.html', 
                             assignments_with_counts=assignments_with_counts, 
                             subjects=[], 
                             lessons=[], 
                             filter_subject_id=filter_subject_id,
                             filter_lesson_id=filter_lesson_id,
                             user_name=user_name)

    try:
        # Get all subjects for this teacher
        subjects_response = supabase.table('subjects').select('id, name').eq('teacher_id', teacher_id).order('name').execute()
        subjects = subjects_response.data or []
        
        if not subjects:
            flash('You are not teaching any subjects.', 'info')
            return render_template('TeacherAssignmentList.html', 
                                 assignments_with_counts=[], 
                                 subjects=[], 
                                 lessons=[],
                                 filter_subject_id=filter_subject_id,
                                 filter_lesson_id=filter_lesson_id,
                                 user_name=user_name)
        
        teacher_subject_ids = [s['id'] for s in subjects]
        subjects_map = {s['id']: s['name'] for s in subjects}
        
        # Get lessons for the selected subject (for the lesson filter dropdown)
        lessons = []
        if filter_subject_id:
            lessons_response = supabase.table('lessons') \
                                      .select('id, title') \
                                      .eq('subject_id', filter_subject_id) \
                                      .order('title') \
                                      .execute()
            lessons = lessons_response.data or []

        # Build the query for assignments
        query = supabase.table('assignments').select('*, lessons(id, title)')
        
        # Apply filters
        if filter_subject_id:
            query = query.eq('subject_id', filter_subject_id)
        else:
            query = query.in_('subject_id', teacher_subject_ids)
        
        if filter_lesson_id:
            query = query.eq('lesson_id', filter_lesson_id)
        
        assignments_response = query.order('created_at', desc=True).execute()
        all_teacher_assignments = assignments_response.data or []

        for assignment in all_teacher_assignments:
            submissions_count_response = supabase.table('submissions') \
                                                 .select('id', count='exact') \
                                                 .eq('assignment_id', assignment['id']) \
                                                 .execute()
            submission_count = submissions_count_response.count or 0
            
            subject_name = subjects_map.get(assignment['subject_id'], 'Unknown Subject')
            lesson_data = assignment.get('lessons')
            lesson_title = lesson_data.get('title') if lesson_data else 'N/A (General Assignment)'

            assignments_with_counts.append({
                'assignment': assignment,
                'submission_count': submission_count,
                'subject_name': subject_name,
                'lesson_name': lesson_title
            })

    except PostgrestAPIError as e:
        flash(f'Database error loading assignments: {e.message}', 'danger')
        print(f"Supabase DB Error (Teacher Assignment List) for {teacher_id}: {e}")
    except Exception as e:
        flash('An unexpected error occurred loading assignments.', 'danger')
        print(f"Unexpected Error (Teacher Assignment List) for {teacher_id}: {e}")

    return render_template(
        'TeacherAssignmentList.html',
        assignments_with_counts=assignments_with_counts,
        subjects=subjects,
        lessons=lessons,
        filter_subject_id=filter_subject_id,
        filter_lesson_id=filter_lesson_id,
        user_name=user_name
    )

@bp.route('/assignment/update-due-date/<int:assignment_id>', methods=['POST'])
@login_required
@role_required('Teacher')
def update_assignment_due_date(assignment_id):
    supabase: Client = current_app.supabase
    teacher_id = session.get('user_id')
    
    if not teacher_id:
        return jsonify({'success': False, 'message': 'User session invalid.'}), 401
    
    if not supabase:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500
    
    new_due_date = request.json.get('due_date')
    
    if not new_due_date:
        return jsonify({'success': False, 'message': 'Due date is required.'}), 400
    
    try:
        # First, verify the teacher owns this assignment through their subjects
        assignment_response = supabase.table('assignments') \
                                     .select('id, subject_id') \
                                     .eq('id', assignment_id) \
                                     .maybe_single() \
                                     .execute()
        
        if not assignment_response.data:
            return jsonify({'success': False, 'message': 'Assignment not found.'}), 404
        
        # Verify teacher owns the subject
        subject_response = supabase.table('subjects') \
                                   .select('id') \
                                   .eq('id', assignment_response.data['subject_id']) \
                                   .eq('teacher_id', teacher_id) \
                                   .maybe_single() \
                                   .execute()
        
        if not subject_response.data:
            return jsonify({'success': False, 'message': 'Unauthorized to update this assignment.'}), 403
        
        # Update the due date
        update_response = supabase.table('assignments') \
                                 .update({'due_date': new_due_date}) \
                                 .eq('id', assignment_id) \
                                 .execute()
        
        if update_response.data:
            return jsonify({'success': True, 'message': 'Due date updated successfully.', 'new_due_date': new_due_date}), 200
        else:
            return jsonify({'success': False, 'message': 'Failed to update due date.'}), 500
            
    except PostgrestAPIError as e:
        return jsonify({'success': False, 'message': f'Database error: {e.message}'}), 500
    except Exception as e:
        print(f"Error updating due date for assignment {assignment_id}: {e}")
        return jsonify({'success': False, 'message': 'An unexpected error occurred.'}), 500

@bp.route('/assignment/delete/<int:assignment_id>', methods=['POST'])
@login_required
@role_required('Teacher')
def delete_assignment(assignment_id):
    supabase: Client = current_app.supabase
    teacher_id = session.get('user_id')
    
    if not teacher_id:
        return jsonify({'success': False, 'message': 'User session invalid.'}), 401
    
    if not supabase:
        return jsonify({'success': False, 'message': 'Database connection error.'}), 500
    
    try:
        # First, verify the teacher owns this assignment through their subjects
        assignment_response = supabase.table('assignments') \
                                     .select('id, subject_id, title') \
                                     .eq('id', assignment_id) \
                                     .maybe_single() \
                                     .execute()
        
        if not assignment_response.data:
            return jsonify({'success': False, 'message': 'Assignment not found.'}), 404
        
        # Verify teacher owns the subject
        subject_response = supabase.table('subjects') \
                                   .select('id') \
                                   .eq('id', assignment_response.data['subject_id']) \
                                   .eq('teacher_id', teacher_id) \
                                   .maybe_single() \
                                   .execute()
        
        if not subject_response.data:
            return jsonify({'success': False, 'message': 'Unauthorized to delete this assignment.'}), 403
        
        # Delete the assignment (submissions will be cascade deleted if FK is set with ON DELETE CASCADE)
        delete_response = supabase.table('assignments') \
                                 .delete() \
                                 .eq('id', assignment_id) \
                                 .execute()
        
        if delete_response.data or delete_response.count == 0:  # Success if data returned or count is 0
            flash(f'Assignment "{assignment_response.data["title"]}" deleted successfully!', 'success')
            return jsonify({'success': True, 'message': 'Assignment deleted successfully.'}), 200
        else:
            return jsonify({'success': False, 'message': 'Failed to delete assignment.'}), 500
            
    except PostgrestAPIError as e:
        return jsonify({'success': False, 'message': f'Database error: {e.message}'}), 500
    except Exception as e:
        print(f"Error deleting assignment {assignment_id}: {e}")
        return jsonify({'success': False, 'message': 'An unexpected error occurred.'}), 500
