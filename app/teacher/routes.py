# app/teacher/routes.py
from flask import render_template, request, session, redirect, url_for, flash, current_app
from . import bp
from app.utils import login_required, role_required
from supabase import Client, PostgrestAPIError

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


@bp.route('/assignment/create', methods=['GET'])
@login_required
@role_required('Teacher')
def create_assignment():
    supabase: Client = current_app.supabase
    teacher_id = session.get('user_id')
    user_name = session.get('user_name', 'Teacher')
    subjects = []

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
    except Exception as e:
        flash('Error fetching subjects for assignment creation.', 'danger')
        print(f"Error fetching subjects for teacher {teacher_id} in create_assignment: {e}")
        teacher_subject_ids = set()


    # --- GET Request: Show the form ---
    pre_selected_subject = request.args.get('subject_id') # For linking from lesson page
    return render_template(
        'TeacherAssignment.html',
        subjects=subjects,
        pre_selected_subject=pre_selected_subject, # Pass to template to select in dropdown
        user_name=user_name
        )
