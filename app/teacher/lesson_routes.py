# app/teacher/lesson_routes.py
from flask import render_template, request, session, redirect, url_for, flash, current_app
from . import bp  # Import blueprint from current package (__init__.py)
from app.utils import login_required, role_required
from supabase import Client, PostgrestAPIError
from datetime import datetime, timezone, timedelta

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
            # Fetch subjects taught by this teacher (subjects are treated as "lessons" in this context)
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

@bp.route('/lesson/manage/<int:lesson_id>') # lesson_id here refers to subject_id
@login_required
@role_required('Teacher')
def manage_lesson(lesson_id):
     supabase: Client = current_app.supabase
     teacher_id = session.get('user_id')
     subject_name = f"Subject ID {lesson_id}"
     can_manage = False
     if supabase and teacher_id:
         try:
             subject_response = supabase.table('subjects') \
                                       .select('name') \
                                       .eq('id', lesson_id) \
                                       .eq('teacher_id', teacher_id) \
                                       .maybe_single() \
                                       .execute()
             if subject_response.data:
                 subject_name = subject_response.data['name']
                 can_manage = True
         except Exception as e:
             print(f"Error checking subject ownership for manage_lesson: {e}")

     if can_manage:
         flash(f"Redirecting to manage content for subject '{subject_name}'.", "info")
         return redirect(url_for('teacher.manage_subject_content', subject_id=lesson_id))
     else:
         flash(f"Subject with ID {lesson_id} not found or not taught by you.", "warning")
     return redirect(url_for('teacher.teacher_lessons'))


@bp.route('/subject/<int:subject_id>/content')
@login_required
@role_required('Teacher')
def manage_subject_content(subject_id):
    supabase: Client = current_app.supabase
    teacher_id = session.get('user_id')
    user_name = session.get('user_name', 'Teacher')
    subject_name = "Unknown Subject"
    lessons_with_assignments = [] # Renamed for clarity

    if not teacher_id:
        flash('User session invalid. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))

    if not supabase:
        flash('Supabase client not initialized. Cannot load content.', 'danger')
        return redirect(url_for('teacher.teacher_lessons'))

    try:
        subject_response = supabase.table('subjects') \
                                   .select('id, name, teacher_id') \
                                   .eq('id', subject_id) \
                                   .maybe_single() \
                                   .execute()

        if not subject_response.data or subject_response.data['teacher_id'] != teacher_id:
            flash('Subject not found or you do not have permission to manage it.', 'warning')
            return redirect(url_for('teacher.teacher_lessons'))
        
        subject_name = subject_response.data['name']

        lessons_response = supabase.table('lessons') \
                                   .select('*, assignments(*)') \
                                   .eq('subject_id', subject_id) \
                                   .order('created_at', desc=False) \
                                   .execute()
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
        lessons=lessons_with_assignments, 
        user_name=user_name,
        subject_id=subject_id
    )

@bp.route('/subject/lesson/<int:lesson_id>/view') # This is for viewing a specific lesson's content
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
            else:
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
        subject_id=subject_id_for_back_link,
        user_name=user_name
    )
