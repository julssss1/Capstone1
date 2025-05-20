# app/teacher/dashboard_routes.py
from flask import render_template, request, session, redirect, url_for, flash, current_app
from . import bp  # Import blueprint from current package (__init__.py)
from app.utils import login_required, role_required
from supabase import Client, PostgrestAPIError
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
