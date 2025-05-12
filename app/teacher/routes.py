# app/teacher/routes.py
from flask import render_template, request, session, redirect, url_for, flash, current_app
from . import bp
from app.utils import login_required, role_required
from supabase import Client, PostgrestAPIError
from datetime import datetime, timezone, timedelta # Ensure timedelta and timezone are imported

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
            
            # Calculate pending assignments (submitted but no feedback)
            pending_assignments_count = 0
            if subjects_taught_count > 0:
                # Get all assignment IDs for subjects taught by this teacher
                teacher_subject_ids = [s['id'] for s in subjects_response.data] # Assuming subjects_response.data contains the subjects

                if teacher_subject_ids:
                    # Count submissions for these assignments where feedback is null or empty
                    # This requires a join or a subquery logic if not directly filterable.
                    # A simpler approach: get all relevant assignments, then count submissions for them.
                    
                    assignments_for_teacher_res = supabase.table('assignments') \
                        .select('id') \
                        .in_('subject_id', teacher_subject_ids) \
                        .execute()

                    if assignments_for_teacher_res.data:
                        assignment_ids_for_teacher = [a['id'] for a in assignments_for_teacher_res.data]
                        if assignment_ids_for_teacher:
                            pending_submissions_res = supabase.table('submissions') \
                                .select('id', count='exact') \
                                .in_('assignment_id', assignment_ids_for_teacher) \
                                .is_('feedback', 'null') \
                                .execute()
                            # Also consider empty string as no feedback
                            pending_submissions_empty_feedback_res = supabase.table('submissions') \
                                .select('id', count='exact') \
                                .in_('assignment_id', assignment_ids_for_teacher) \
                                .eq('feedback', '') \
                                .execute()
                            
                            count1 = pending_submissions_res.count or 0
                            count2 = pending_submissions_empty_feedback_res.count or 0
                            
                            # This double counting is not ideal if a submission has NULL and then gets an empty string.
                            # A better way is to fetch submissions and check in Python, or use a more complex SQL query.
                            # For now, let's assume feedback being NULL is the primary indicator.
                            # Or, more simply, count submissions whose status is 'Auto-Graded' or 'Submitted'
                            # if those statuses imply pending review.

                            # Let's refine to count submissions that are 'Auto-Graded' or 'Submitted'
                            # Count submissions for these assignments where feedback is null OR feedback is an empty string.
                            # Using 'or' condition in Supabase-py: .or_('feedback.is.null,feedback.eq.')
                            
                            # Query for feedback IS NULL
                            pending_null_feedback_res = supabase.table('submissions') \
                                .select('id', count='exact') \
                                .in_('assignment_id', assignment_ids_for_teacher) \
                                .is_('feedback', 'null') \
                                .execute()
                            count_null_feedback = pending_null_feedback_res.count or 0

                            # Query for feedback IS '' (empty string), but NOT NULL
                            # This is tricky because we don't want to double count if feedback was NULL and then set to ''.
                            # A more robust way is to fetch the feedback status and count in Python,
                            # or use a view/RPC in Supabase if this gets too complex.

                            # Let's simplify: count where feedback is NULL.
                            # If you also want to count empty strings as "no feedback" and they are distinct from NULL,
                            # the logic would need to be more careful to avoid double counting.
                            # For now, assuming "no feedback" primarily means the feedback field is NULL.
                            # If a teacher explicitly clears feedback to an empty string, that's a different case.
                            # The most common "pending" state is NULL feedback.

                            # If you want to count where feedback is NULL OR feedback is an empty string,
                            # and these are mutually exclusive states for a given record at one time:
                            # count_empty_feedback = 0
                            # if you decide to also count empty strings:
                            #   pending_empty_feedback_res = supabase.table('submissions') \
                            #       .select('id', count='exact') \
                            #       .in_('assignment_id', assignment_ids_for_teacher) \
                            #       .eq('feedback', '') \
                            #       .execute()
                            #   count_empty_feedback = pending_empty_feedback_res.count or 0
                            # pending_assignments_count = count_null_feedback + count_empty_feedback 
                            # This sum is only correct if a record can't be both NULL and ''.

                            # Let's use the .or_ filter for a single query
                            # Counts rows where (feedback is null) OR (feedback = '')
                            pending_feedback_query = supabase.table('submissions') \
                                .select('id', count='exact') \
                                .in_('assignment_id', assignment_ids_for_teacher) \
                                .filter('feedback', 'is', 'null') \
                                .execute()
                            
                            # The .or_ filter needs to be applied carefully.
                            # A simpler and often more reliable way for complex OR on same/different columns
                            # is sometimes to fetch relevant data and count in Python, or use an RPC.

                            # Given the client library's capabilities, let's try a filter that PostgREST understands for OR on the same column.
                            # feedback=is.null OR feedback=eq.''
                            # This might require raw PostgREST filter syntax if not directly supported.
                            # For now, let's stick to counting NULLs as the primary "no feedback" indicator,
                            # as this is the state before any teacher interaction.
                            # If a teacher saves an empty string, that's an explicit action.

                            # Count submissions where feedback is NULL OR feedback is an empty string
                            # The .or_() filter in supabase-py takes a string of comma-separated conditions.
                            # Each condition is column.operator.value
                            # e.g., "feedback.is.null,feedback.eq." (the dot after eq is for empty string)

                            # Let's try using the .or_ filter directly if supported for count
                            # This is the correct way to form an OR condition for PostgREST
                            # feedback=is.null OR feedback=eq.''
                            # We need to ensure the client library translates this correctly.
                            # A common way is to use the .filter() with 'or' condition.

                            # Simpler: Count NULLs, then count empty strings, and sum.
                            # This assumes a feedback field won't be both NULL and an empty string.
                            
                            query_null = supabase.table('submissions') \
                                .select('id', count='exact') \
                                .in_('assignment_id', assignment_ids_for_teacher) \
                                .is_('feedback', 'null') \
                                .execute()
                            count_null = query_null.count or 0

                            query_empty = supabase.table('submissions') \
                                .select('id', count='exact') \
                                .in_('assignment_id', assignment_ids_for_teacher) \
                                .eq('feedback', '') \
                                .execute()
                            count_empty = query_empty.count or 0
                            
                            # This might double count if a feedback field could somehow be considered both null and empty by different queries,
                            # or if the same submission ID appears due to some other reason.
                            # However, NULL and '' are distinct.
                            # A more robust way if there was overlap would be to fetch IDs and count unique IDs.
                            # But for counting distinct conditions, summing counts from non-overlapping queries is fine.
                            # The issue is if a submission has NULL, it's counted. If another has '', it's counted.
                            # If the same submission had NULL and then was updated to '', it would only match one.
                            # The problem is if the definition of "pending" means "feedback is NULL" OR "feedback is ''".
                            # The most direct way to get this count is with a single query using an OR condition.

                            # Count submissions where feedback is NULL
                            query_null_feedback = supabase.table('submissions') \
                                .select('id', count='exact') \
                                .in_('assignment_id', assignment_ids_for_teacher) \
                                .is_('feedback', 'null') \
                                .execute()
                            count_null = query_null_feedback.count or 0

                            # Count submissions where feedback is an empty string
                            query_empty_feedback = supabase.table('submissions') \
                                .select('id', count='exact') \
                                .in_('assignment_id', assignment_ids_for_teacher) \
                                .eq('feedback', '') \
                                .execute()
                            count_empty = query_empty_feedback.count or 0

                            # Count submissions where feedback is the literal string 'None'
                            query_none_string_feedback = supabase.table('submissions') \
                                .select('id', count='exact') \
                                .in_('assignment_id', assignment_ids_for_teacher) \
                                .eq('feedback', 'None') \
                                .execute()
                            count_none_string = query_none_string_feedback.count or 0
                            
                            pending_assignments_count = count_null + count_empty + count_none_string

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

@bp.route('/lessons') 
@login_required
@role_required('Teacher')
def teacher_lessons():
    print(f"Accessing Teacher Lessons BP for user: {session.get('user_name')}")
    supabase: Client = current_app.supabase
    teacher_id = session.get('user_id')
    user_name = session.get('user_name', 'Teacher')
    lessons = [] 


    if not teacher_id:
        flash('User session invalid. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))

    if not supabase:
        flash('Supabase client not initialized. Cannot load lessons.', 'danger')
    else:
        try:
            # Fetch subjects taught by this teacher
            lessons_response = supabase.table('subjects') \
                                       .select('id, name, description') \
                                       .eq('teacher_id', teacher_id) \
                                       .order('name') \
                                       .execute()
            lessons = lessons_response.data or []


        except PostgrestAPIError as e:
            flash(f'Database error loading lessons: {e.message}', 'danger')
            print(f"Supabase DB Error (Teacher Lessons) for {teacher_id}: {e}")
        except Exception as e:
            flash('An unexpected error occurred loading lessons.', 'danger')
            print(f"Unexpected Error (Teacher Lessons) for {teacher_id}: {e}")

    return render_template(
        'Teacher-Subject.html', 
        teacher_lessons=lessons, 
        user_name=user_name
        )

@bp.route('/gradebook')
@login_required
@role_required('Teacher')
def teacher_gradebook():
    print(f"Accessing Teacher Gradebook BP for user: {session.get('user_name')}")
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
        flash('Supabase client not initialized. Cannot load gradebook data.', 'danger')
    else:
        try:
            
            
            subjects_response = supabase.table('subjects') \
                                        .select('id, name') \
                                        .eq('teacher_id', teacher_id) \
                                        .order('name') \
                                        .execute()
            subjects = subjects_response.data or []


            
            if selected_subject_id_str:
                try:
                    selected_subject_id = int(selected_subject_id_str) # Convert for query if needed
                    subject = next((s for s in subjects if s['id'] == selected_subject_id), None)
                    if subject:
                        selected_subject_name = subject['name']
                    else:
                        flash(f"Invalid subject selected or you don't teach subject ID {selected_subject_id_str}.", "warning")
                        selected_subject_id = None # Reset selection
                        selected_subject_name = "All Subjects"

                    if selected_subject_id:
                   
                        grades_response = supabase.table('submissions') \
                                                  .select('*, profiles(first_name, last_name), assignments!inner(title, subject_id)') \
                                                  .eq('assignments.subject_id', selected_subject_id) \
                                                  .execute()
                                                 

                    
                        raw_submissions = grades_response.data or []
                        grades_to_display = []
                        for sub in raw_submissions:
                            profile = sub.get('profiles')
                            if profile:
                                fname = profile.get('first_name', '')
                                lname = profile.get('last_name', '')
                                sub['student_display_name'] = f"{fname} {lname}".strip() if fname or lname else "Unknown Student"
                            else:
                                sub['student_display_name'] = "Unknown Student"
                            
                            # Format submitted_at for display
                            if sub.get('submitted_at'):
                                try:
                                    submitted_dt_str = sub['submitted_at']
                                    if submitted_dt_str.endswith('Z'):
                                        submitted_dt_str = submitted_dt_str[:-1] + '+00:00'
                                    
                                    if '.' in submitted_dt_str:
                                        main_part, fractional_part = submitted_dt_str.split('.', 1)
                                        tz_char = None
                                        if '+' in fractional_part: tz_char = '+'
                                        elif '-' in fractional_part:
                                            if fractional_part.count(':') > 0 and (fractional_part.rfind('-') > 0 or fractional_part.rfind('+') > 0) :
                                                if '+' in fractional_part: tz_char = '+' # Should not happen if - is present
                                                elif '-' in fractional_part:
                                                    potential_tz_dash_idx = fractional_part.rfind('-')
                                                    if potential_tz_dash_idx > 0: tz_char = '-'
                                        
                                        if tz_char:
                                            ms_part, tz_part_val = fractional_part.split(tz_char, 1)
                                            submitted_dt_str = f"{main_part}.{ms_part[:6]}{tz_char}{tz_part_val}"
                                        else: 
                                            submitted_dt_str = f"{main_part}.{fractional_part[:6]}"
                                            
                                    submitted_dt_utc = datetime.fromisoformat(submitted_dt_str)
                                    pht_tz = timezone(timedelta(hours=8))
                                    submitted_dt_pht = submitted_dt_utc.astimezone(pht_tz)
                                    sub['formatted_submitted_at'] = submitted_dt_pht.strftime("%b %d, %Y, %I:%M %p")
                                except ValueError as ve:
                                    print(f"ValueError parsing submitted_at '{sub['submitted_at']}' in gradebook: {ve}")
                                    try:
                                        fallback_dt = datetime.strptime(sub['submitted_at'][:19], "%Y-%m-%dT%H:%M:%S")
                                        sub['formatted_submitted_at'] = fallback_dt.strftime("%b %d, %Y, %I:%M %p UTC")
                                    except:
                                        sub['formatted_submitted_at'] = sub['submitted_at'] # Raw if all fails
                            else:
                                sub['formatted_submitted_at'] = "N/A"
                                
                            grades_to_display.append(sub)

                except ValueError:
                    flash("Invalid subject filter value.", "warning")
                    selected_subject_id_str = None # Reset selection
                except PostgrestAPIError as e:
                    flash(f'Database error loading grades: {e.message}', 'danger')
                    print(f"Supabase DB Error (Teacher Gradebook - Grades) for {teacher_id}, subject {selected_subject_id_str}: {e}")
                except Exception as e:
                    flash('An unexpected error occurred loading grades.', 'danger')
                    print(f"Unexpected Error (Teacher Gradebook - Grades) for {teacher_id}, subject {selected_subject_id_str}: {e}")

        except PostgrestAPIError as e:
            flash(f'Database error loading subjects: {e.message}', 'danger')
            print(f"Supabase DB Error (Teacher Gradebook - Subjects) for {teacher_id}: {e}")
        except Exception as e:
            flash('An unexpected error occurred loading subjects.', 'danger')
            print(f"Unexpected Error (Teacher Gradebook - Subjects) for {teacher_id}: {e}")

    return render_template(
        'Teacher-GradeTable.html',
        subjects=subjects, 
        grades=grades_to_display, 
        selected_subject_id=selected_subject_id_str, 
        selected_subject_name=selected_subject_name,
        user_name=user_name
        )

@bp.route('/lesson/manage/<int:lesson_id>')
@login_required
@role_required('Teacher')
def manage_lesson(lesson_id):
     # Optional: Verify lesson_id belongs to teacher before flashing message
     supabase: Client = current_app.supabase
     teacher_id = session.get('user_id')
     lesson_name = f"Lesson ID {lesson_id}"
     can_manage = False
     if supabase and teacher_id:
         try:
             lesson_response = supabase.table('subjects') \
                                       .select('name') \
                                       .eq('id', lesson_id) \
                                       .eq('teacher_id', teacher_id) \
                                       .maybe_single() \
                                       .execute()
             if lesson_response.data:
                 lesson_name = lesson_response.data['name']
                 can_manage = True
         except Exception as e:
             print(f"Error checking lesson ownership for manage_lesson: {e}")

     if can_manage:
         flash(f"Manage content for lesson '{lesson_name}' (page not implemented).", "info")
     else:
         flash(f"Lesson with ID {lesson_id} not found or not taught by you.", "warning")
     return redirect(url_for('teacher.teacher_lessons'))

@bp.route('/assignment/create/<int:lesson_id>') 
@login_required
@role_required('Teacher')
def create_assignment_for_lesson(lesson_id):
    
     supabase: Client = current_app.supabase
     teacher_id = session.get('user_id')
     lesson_name = f"Lesson ID {lesson_id}"
     can_create = False
     if supabase and teacher_id:
         try:
             lesson_response = supabase.table('subjects') \
                                       .select('name') \
                                       .eq('id', lesson_id) \
                                       .eq('teacher_id', teacher_id) \
                                       .maybe_single() \
                                       .execute()
             if lesson_response.data:
                 lesson_name = lesson_response.data['name']
                 can_create = True
         except Exception as e:
             print(f"Error checking lesson ownership for create_assignment_for_lesson: {e}")

     if can_create:
         # Redirect to the main create assignment page, pre-filling the subject
         flash(f"Create assignment for '{lesson_name}'.", "info")
         return redirect(url_for('teacher.create_assignment', subject_id=lesson_id))
     else:
         flash(f"Lesson with ID {lesson_id} not found or not taught by you.", "warning")
         return redirect(url_for('teacher.teacher_lessons'))


@bp.route('/assignment/create', methods=['GET', 'POST'])
@login_required
@role_required('Teacher')
def create_assignment():
    supabase: Client = current_app.supabase
    teacher_id = session.get('user_id')
    user_name = session.get('user_name', 'Teacher')
    subjects = []
    lessons_for_subject = []
    pre_selected_subject_id = request.args.get('subject_id', type=int)
    pre_selected_lesson_id = request.args.get('lesson_id', type=int)


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
        teacher_subject_ids = {s['id'] for s in subjects}

        # If a subject is pre-selected (e.g., from "Add Activity" link), fetch its lessons
        if pre_selected_subject_id and pre_selected_subject_id in teacher_subject_ids:
            lessons_response = supabase.table('lessons') \
                                       .select('id, title') \
                                       .eq('subject_id', pre_selected_subject_id) \
                                       .order('title') \
                                       .execute()
            lessons_for_subject = lessons_response.data or []
        
    except Exception as e:
        flash('Error fetching data for assignment creation.', 'danger')
        print(f"Error fetching data for teacher {teacher_id} in create_assignment: {e}")
        # teacher_subject_ids might not be set if error was in fetching subjects
        if 'teacher_subject_ids' not in locals():
             teacher_subject_ids = set()

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        subject_id_form = request.form.get('subject_id', type=int)
        lesson_id_form = request.form.get('lesson_id', type=int) # Will be None if empty string or not provided
        due_date = request.form.get('due_date')
        # File handling would be more complex and require request.files, skipping for now

        if not title or not description or not subject_id_form or not due_date:
            flash('Title, Description, Subject, and Due Date are required.', 'danger')
            # Re-render form with existing data if possible, or redirect to GET
            # For simplicity, redirecting to GET which will repopulate subjects
            return redirect(url_for('teacher.create_assignment', 
                                    subject_id=pre_selected_subject_id, 
                                    lesson_id=pre_selected_lesson_id))

        assignment_data = {
            'title': title,
            'description': description,
            'subject_id': subject_id_form,
            'due_date': due_date,
            # 'teacher_id': teacher_id # Assuming assignments should be linked to the teacher who created them
                                      # This depends on your 'assignments' table schema.
                                      # If 'assignments' table doesn't have 'teacher_id', remove this.
        }
        if lesson_id_form: # Only add lesson_id if it was selected
            assignment_data['lesson_id'] = lesson_id_form

        try:
            insert_response = supabase.table('assignments').insert(assignment_data).execute()
            if insert_response.data:
                flash('Assignment created successfully!', 'success')
                # Redirect to a relevant page, e.g., the subject content page or assignments list
                return redirect(url_for('teacher.manage_subject_content', subject_id=subject_id_form))
            else:
                flash('Failed to create assignment. No data returned from insert.', 'danger')
                if hasattr(insert_response, 'error') and insert_response.error:
                     flash(f"Database error: {insert_response.error.message}", "danger")

        except PostgrestAPIError as e:
            flash(f'Database error creating assignment: {e.message}', 'danger')
            print(f"Supabase DB Error (Create Assignment POST) for teacher {teacher_id}: {e}")
        except Exception as e:
            flash('An unexpected error occurred creating the assignment.', 'danger')
            print(f"Unexpected Error (Create Assignment POST) for teacher {teacher_id}: {e}")
        
        # If creation failed, re-render form with data (or redirect to GET)
        # For simplicity, redirecting to GET which will repopulate subjects
        return redirect(url_for('teacher.create_assignment', 
                                subject_id=pre_selected_subject_id, 
                                lesson_id=pre_selected_lesson_id))


    # --- GET Request: Show the form (this part remains) ---
    return render_template(
        'TeacherAssignment.html',
        subjects=subjects,
        lessons_for_subject=lessons_for_subject, # Pass lessons for the pre-selected subject
        pre_selected_subject_id=pre_selected_subject_id,
        pre_selected_lesson_id=pre_selected_lesson_id,
        user_name=user_name
        )

@bp.route('/subject/<int:subject_id>/content')
@login_required
@role_required('Teacher')
def manage_subject_content(subject_id):
    supabase: Client = current_app.supabase
    teacher_id = session.get('user_id')
    user_name = session.get('user_name', 'Teacher')
    subject_name = "Unknown Subject"
    lessons = []

    if not teacher_id:
        flash('User session invalid. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))

    if not supabase:
        flash('Supabase client not initialized. Cannot load content.', 'danger')
        return redirect(url_for('teacher.teacher_lessons'))

    try:
        # Verify teacher owns the subject and get its name
        subject_response = supabase.table('subjects') \
                                   .select('id, name, teacher_id') \
                                   .eq('id', subject_id) \
                                   .maybe_single() \
                                   .execute()

        if not subject_response.data or subject_response.data['teacher_id'] != teacher_id:
            flash('Subject not found or you do not have permission to manage it.', 'warning')
            return redirect(url_for('teacher.teacher_lessons'))
        
        subject_name = subject_response.data['name']

        # Fetch lessons for this subject
        lessons_response = supabase.table('lessons') \
                                   .select('*, assignments(*)') \
                                   .eq('subject_id', subject_id) \
                                   .order('created_at', desc=False) \
                                   .execute()
        # The assignments will be nested under each lesson object if the foreign key is set up correctly
        # and Supabase's default GET request behavior for related tables is used.
        # The select('*, assignments(*)') should achieve this.
        lessons_with_assignments = lessons_response.data or []

    except PostgrestAPIError as e:
        flash(f'Database error loading subject content: {e.message}', 'danger')
        print(f"Supabase DB Error (Manage Subject Content) for teacher {teacher_id}, subject {subject_id}: {e}")
        return redirect(url_for('teacher.teacher_lessons'))
    except Exception as e:
        flash('An unexpected error occurred loading subject content.', 'danger')
        print(f"Unexpected Error (Manage Subject Content) for teacher {teacher_id}, subject {subject_id}: {e}")
        return redirect(url_for('teacher.teacher_lessons'))

    return render_template(
        'TeacherSubjectContent.html',
        subject_name=subject_name,
        lessons=lessons_with_assignments, # Pass lessons with nested assignments
        user_name=user_name,
        subject_id=subject_id # Pass subject_id for "Add Activity" link
    )

@bp.route('/subject/lesson/<int:lesson_id>/view')
@login_required
@role_required('Teacher')
def view_lesson_content_teacher(lesson_id):
    supabase: Client = current_app.supabase
    teacher_id = session.get('user_id')
    user_name = session.get('user_name', 'Teacher')
    lesson_data = None
    subject_name = "Unknown Subject"
    subject_id_for_back_link = None

    if not teacher_id:
        flash('User session invalid. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))

    if not supabase:
        flash('Supabase client not initialized.', 'danger')
        return redirect(url_for('teacher.teacher_lessons'))

    try:
        # Fetch the lesson and its subject details
        # Ensure the teacher owns the subject this lesson belongs to
        response = supabase.table('lessons') \
                           .select('*, subjects!inner(id, name, teacher_id)') \
                           .eq('id', lesson_id) \
                           .eq('subjects.teacher_id', teacher_id) \
                           .maybe_single() \
                           .execute()

        if response.data:
            lesson_data = response.data
            subject_data = lesson_data.get('subjects')
            if subject_data:
                subject_name = subject_data.get('name', 'Unknown Subject')
                subject_id_for_back_link = subject_data.get('id')
            else: # Should not happen if !inner join works as expected and subject exists
                flash('Could not retrieve subject details for this lesson.', 'warning')
                return redirect(url_for('teacher.teacher_lessons'))
        else:
            flash('Lesson not found or you do not have permission to view it.', 'warning')
            return redirect(url_for('teacher.teacher_lessons'))

    except PostgrestAPIError as e:
        flash(f'Database error loading lesson: {e.message}', 'danger')
        print(f"Supabase DB Error (View Lesson Teacher) for lesson {lesson_id}, teacher {teacher_id}: {e}")
        return redirect(url_for('teacher.teacher_lessons'))
    except Exception as e:
        flash('An unexpected error occurred loading the lesson.', 'danger')
        print(f"Unexpected Error (View Lesson Teacher) for lesson {lesson_id}, teacher {teacher_id}: {e}")
        return redirect(url_for('teacher.teacher_lessons'))

    return render_template(
        'TeacherLessonView.html',
        lesson_data=lesson_data,
        subject_name=subject_name,
        subject_id=subject_id_for_back_link, # For the "Back to Subject Content" link
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

    if not teacher_id:
        flash('User session invalid. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))

    if not supabase:
        flash('Supabase client not initialized.', 'danger')
        return render_template('TeacherAssignmentList.html', assignments_with_counts=assignments_with_counts, user_name=user_name)

    try:
        # Step 1: Get subjects taught by the teacher
        subjects_response = supabase.table('subjects').select('id, name').eq('teacher_id', teacher_id).execute()
        if not subjects_response.data:
            flash('You are not teaching any subjects.', 'info')
            return render_template('TeacherAssignmentList.html', assignments_with_counts=[], user_name=user_name)
        
        teacher_subject_ids = [s['id'] for s in subjects_response.data]
        subjects_map = {s['id']: s['name'] for s in subjects_response.data}

        # Step 2: Get all assignments for those subjects, including lesson details
        assignments_response = supabase.table('assignments') \
                                     .select('*, lessons(title)') \
                                     .in_('subject_id', teacher_subject_ids) \
                                     .order('created_at', desc=True) \
                                     .execute()
        
        all_teacher_assignments = assignments_response.data or []

        for assignment in all_teacher_assignments:
            # Step 3: For each assignment, count submissions
            submissions_count_response = supabase.table('submissions') \
                                                 .select('id', count='exact') \
                                                 .eq('assignment_id', assignment['id']) \
                                                 .execute()
            submission_count = submissions_count_response.count or 0
            
            subject_name = subjects_map.get(assignment['subject_id'], 'Unknown Subject')
            lesson_name = assignment.get('lessons', {}).get('title') if assignment.get('lessons') else 'N/A'


            assignments_with_counts.append({
                'assignment': assignment,
                'submission_count': submission_count,
                'subject_name': subject_name,
                'lesson_name': lesson_name
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

    if not teacher_id:
        flash('User session invalid. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))
    if not supabase:
        flash('Database connection error.', 'danger')
        return redirect(url_for('teacher.teacher_gradebook')) # Or other appropriate teacher page

    try:
        # Fetch submission details, including related assignment, student profile, subject, and lesson
        # Ensure the teacher has permission to view this submission (e.g., by checking if the assignment's subject is taught by them)
        submission_response = supabase.table('submissions') \
            .select('*, profiles(first_name, last_name), assignments!inner(*, subjects!inner(name, teacher_id), lessons(title))') \
            .eq('id', submission_id) \
            .eq('assignments.subjects.teacher_id', teacher_id) \
            .maybe_single() \
            .execute()

        if submission_response and submission_response.data:
            submission_details = submission_response.data
            # Format submitted_at for display
            if submission_details.get('submitted_at'):
                try:
                    submitted_dt_str = submission_details['submitted_at']
                    # Ensure it's timezone-aware for fromisoformat
                    if not ('+' in submitted_dt_str or submitted_dt_str.endswith('Z')):
                        submitted_dt_str += '+00:00' # Assume UTC if no offset
                    elif submitted_dt_str.endswith('Z'): 
                        submitted_dt_str = submitted_dt_str[:-1] + '+00:00'
                    
                    # Truncate microseconds to 6 digits
                    if '.' in submitted_dt_str:
                        main_part, fractional_part = submitted_dt_str.split('.', 1)
                        tz_char = None
                        if '+' in fractional_part: tz_char = '+'
                        elif '-' in fractional_part: 
                            if fractional_part.count(':') > 0 and (fractional_part.rfind('-') > 0 or fractional_part.rfind('+') > 0) : # Check for : after -
                                if '+' in fractional_part: tz_char = '+' # Should not happen if - is present
                                elif '-' in fractional_part:
                                    potential_tz_dash_idx = fractional_part.rfind('-')
                                    if potential_tz_dash_idx > 0: tz_char = '-'
                        
                        if tz_char:
                            ms_part, tz_part_val = fractional_part.split(tz_char, 1)
                            submitted_dt_str = f"{main_part}.{ms_part[:6]}{tz_char}{tz_part_val}"
                        else: 
                            submitted_dt_str = f"{main_part}.{fractional_part[:6]}"
                            
                    submitted_dt_utc = datetime.fromisoformat(submitted_dt_str)
                    
                    # Convert to PHT (UTC+8)
                    pht_tz = timezone(timedelta(hours=8))
                    submitted_dt_pht = submitted_dt_utc.astimezone(pht_tz)
                    submission_details['formatted_submitted_at'] = submitted_dt_pht.strftime("%b %d, %Y, %I:%M %p PHT")
                except ValueError as ve:
                    print(f"ValueError parsing submitted_at '{submission_details['submitted_at']}' in teacher review: {ve}")
                    try: # Fallback to simpler UTC formatting
                        fallback_dt = datetime.strptime(submission_details['submitted_at'][:19], "%Y-%m-%dT%H:%M:%S")
                        submission_details['formatted_submitted_at'] = fallback_dt.strftime("%b %d, %Y, %I:%M %p UTC")
                    except: # Raw if all fails
                        submission_details['formatted_submitted_at'] = submission_details['submitted_at'] 
            else:
                submission_details['formatted_submitted_at'] = "N/A"
        else:
            flash('Submission not found or you do not have permission to review it.', 'warning')
            return redirect(url_for('teacher.teacher_gradebook')) # Or other appropriate teacher page
            
    except PostgrestAPIError as e:
        flash(f'Database error fetching submission for review: {e.message}', 'danger')
        print(f"Supabase DB Error (Review Submission GET): {e}")
        return redirect(url_for('teacher.teacher_gradebook'))
    except Exception as e:
        flash(f'An unexpected error occurred: {e}', 'danger')
        print(f"Unexpected Error (Review Submission GET): {e}")
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

    if not teacher_id:
        flash('User session invalid. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))
    if not supabase:
        flash('Database connection error.', 'danger')
        return redirect(url_for('teacher.review_submission', submission_id=submission_id))

    try:
        # First, verify the teacher has permission to update this submission
        # (e.g., by checking if the assignment's subject is taught by them)
        submission_check_response = supabase.table('submissions') \
            .select('id, assignments!inner(subjects!inner(teacher_id))') \
            .eq('id', submission_id) \
            .eq('assignments.subjects.teacher_id', teacher_id) \
            .maybe_single() \
            .execute()

        if not (submission_check_response and submission_check_response.data):
            flash('Submission not found or you do not have permission to update it.', 'danger')
            return redirect(url_for('teacher.teacher_gradebook'))

        update_data = {}
        if feedback_text is not None: # Allow empty string for feedback
            update_data['feedback'] = feedback_text
        
        final_grade = None
        if override_grade_str:
            try:
                final_grade = float(override_grade_str)
                if not (0 <= final_grade <= 100):
                    flash('Override grade must be between 0 and 100.', 'danger')
                    return redirect(url_for('teacher.review_submission', submission_id=submission_id))
                update_data['grade'] = final_grade
            except ValueError:
                flash('Invalid format for override grade. Please enter a number.', 'danger')
                return redirect(url_for('teacher.review_submission', submission_id=submission_id))
        
        if new_status:
            update_data['status'] = new_status
        
        if not update_data:
            flash('No changes to save.', 'info')
            return redirect(url_for('teacher.review_submission', submission_id=submission_id))

        print(f"Updating submission {submission_id} with: {update_data}")
        update_response = supabase.table('submissions').update(update_data).eq('id', submission_id).execute()

        if update_response and hasattr(update_response, 'error') and update_response.error:
            raise PostgrestAPIError(update_response.error)
        
        flash('Feedback and grade updated successfully!', 'success')
        return redirect(url_for('teacher.review_submission', submission_id=submission_id))

    except PostgrestAPIError as e:
        flash(f'Database error updating submission: {e.message}', 'danger')
        print(f"Supabase DB Error (Update Submission Feedback POST): {e}")
    except Exception as e:
        flash(f'An unexpected error occurred: {e}', 'danger')
        print(f"Unexpected Error (Update Submission Feedback POST): {e}")
    
    return redirect(url_for('teacher.review_submission', submission_id=submission_id))
