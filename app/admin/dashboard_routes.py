from flask import render_template, session, flash, current_app
from . import bp
from app.utils import login_required, role_required
from supabase import Client, PostgrestAPIError

@bp.route('/dashboard')
@login_required
@role_required('Admin')
def admin_dashboard():
    print(f"Accessing Admin Dashboard BP for user: {session.get('user_name')}")
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Admin')
    student_count = 0
    teacher_count = 0
    subject_count = 0

    if not supabase:
        flash('Supabase client not initialized. Cannot load dashboard data.', 'danger')
    else:
        try:
            student_response = supabase.table('profiles') \
                                       .select('id', count='exact') \
                                       .eq('role', 'Student') \
                                       .execute()
            student_count = student_response.count or 0

            teacher_response = supabase.table('profiles') \
                                       .select('id', count='exact') \
                                       .eq('role', 'Teacher') \
                                       .execute()
            teacher_count = teacher_response.count or 0

            subject_response = supabase.table('subjects') \
                                       .select('id', count='exact') \
                                       .execute()
            subject_count = subject_response.count or 0

        except PostgrestAPIError as e:
            flash(f'Database error loading dashboard counts: {e.message}', 'danger')
            print(f"Supabase DB Error (Admin Dashboard): {e}")
        except Exception as e:
            flash('An unexpected error occurred loading dashboard data.', 'danger')
            print(f"Unexpected Error (Admin Dashboard): {e}")

    return render_template(
        'AdminDashboard.html',
        student_count=student_count,
        teacher_count=teacher_count,
        subject_count=subject_count,
        user_name=user_name
        )
