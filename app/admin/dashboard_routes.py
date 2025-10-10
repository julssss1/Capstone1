from flask import render_template, session, flash, current_app, redirect, url_for
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
    password_reset_requests = []

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

            # Fetch pending password reset requests
            reset_requests_response = supabase.table('password_reset_requests') \
                                              .select('*') \
                                              .eq('status', 'pending') \
                                              .order('requested_at', desc=True) \
                                              .execute()
            password_reset_requests = reset_requests_response.data or []

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
        user_name=user_name,
        password_reset_requests=password_reset_requests
        )

@bp.route('/handle-password-reset/<int:request_id>')
@login_required
@role_required('Admin')
def handle_password_reset(request_id):
    """Handle password reset request - find user and redirect to edit page"""
    supabase: Client = current_app.supabase
    
    if not supabase:
        flash('Supabase client not initialized.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
    
    try:
        # Get the reset request
        reset_request = supabase.table('password_reset_requests') \
                                .select('*') \
                                .eq('id', request_id) \
                                .single() \
                                .execute()
        
        if not reset_request.data:
            flash('Password reset request not found.', 'danger')
            return redirect(url_for('admin.admin_dashboard'))
        
        email = reset_request.data['email']
        
        # Find user by email using RPC or by listing users
        # Since we can't directly query auth.users, we'll use execute SQL
        user_query = supabase.rpc('get_user_by_email', {'email_param': email}).execute()
        
        if user_query.data and len(user_query.data) > 0:
            user_id = user_query.data[0]['id']
            # Store the request ID in session to mark as complete later
            session['pending_reset_request_id'] = request_id
            flash(f'Editing user account for: {email}', 'info')
            return redirect(url_for('admin.edit_user', user_id=user_id))
        else:
            flash(f'No user account found for email: {email}', 'warning')
            # Mark as completed anyway since user doesn't exist
            supabase.table('password_reset_requests') \
                    .update({'status': 'completed'}) \
                    .eq('id', request_id) \
                    .execute()
            return redirect(url_for('admin.admin_dashboard'))
            
    except Exception as e:
        print(f"Error handling password reset request: {e}")
        flash('An error occurred while processing the request.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))

@bp.route('/complete-password-reset/<int:request_id>')
@login_required
@role_required('Admin')
def complete_password_reset(request_id):
    """Mark password reset request as completed"""
    supabase: Client = current_app.supabase
    
    if not supabase:
        flash('Supabase client not initialized.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
    
    try:
        supabase.table('password_reset_requests') \
                .update({'status': 'completed'}) \
                .eq('id', request_id) \
                .execute()
        
        # Clear the pending reset request from session
        session.pop('pending_reset_request_id', None)
        
        flash('Password reset request marked as completed.', 'success')
    except Exception as e:
        print(f"Error completing password reset request: {e}")
        flash('An error occurred while completing the request.', 'danger')
    
    return redirect(url_for('admin.admin_dashboard'))
