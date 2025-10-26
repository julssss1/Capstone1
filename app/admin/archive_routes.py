from flask import render_template, request, session, redirect, url_for, flash, current_app, jsonify
from . import bp
from app.utils import login_required, role_required
from app.archive_utils import unarchive_subject, unarchive_lesson, unarchive_assignment, unarchive_user
from supabase import Client, PostgrestAPIError
from datetime import datetime

@bp.route('/archives')
@login_required
@role_required('Admin')
def view_archives():
    """Display archived records with filtering capabilities."""
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Admin')
    
    # Get filter parameters
    archive_type = request.args.get('type', 'users')  # Default to users
    search_query = request.args.get('search', '').strip()
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    if not supabase:
        flash('Supabase client not initialized.', 'danger')
        return render_template('AdminArchives.html', 
                             archives=[], 
                             archive_type=archive_type,
                             search_query=search_query,
                             date_from=date_from,
                             date_to=date_to,
                             user_name=user_name)
    
    archives = []
    
    try:
        # Build query based on archive type
        if archive_type == 'users':
            query = supabase.table('archived_profiles').select('*')
            
            # Apply search filter
            if search_query:
                # Search in first name, last name, or email
                query = query.or_(f'first_name.ilike.%{search_query}%,last_name.ilike.%{search_query}%,email.ilike.%{search_query}%')
            
            # Apply date filters
            if date_from:
                query = query.gte('archived_at', f'{date_from}T00:00:00')
            if date_to:
                query = query.lte('archived_at', f'{date_to}T23:59:59')
            
            response = query.order('archived_at', desc=True).execute()
            archives = response.data or []
            
            # Format display data
            for archive in archives:
                first_name = archive.get('first_name', '')
                last_name = archive.get('last_name', '')
                middle_name = archive.get('middle_name', '')
                middle_initial = f" {middle_name[0]}." if middle_name else ""
                archive['display_name'] = f"{first_name}{middle_initial} {last_name}".strip()
                archive['type_label'] = 'User'
        
        elif archive_type == 'subjects':
            query = supabase.table('archived_subjects').select('*')
            
            # Apply search filter
            if search_query:
                query = query.or_(f'name.ilike.%{search_query}%,teacher_name.ilike.%{search_query}%')
            
            # Apply date filters
            if date_from:
                query = query.gte('archived_at', f'{date_from}T00:00:00')
            if date_to:
                query = query.lte('archived_at', f'{date_to}T23:59:59')
            
            response = query.order('archived_at', desc=True).execute()
            archives = response.data or []
            
            # Format display data
            for archive in archives:
                archive['display_name'] = archive.get('name', 'Unknown Subject')
                archive['type_label'] = 'Subject'
        
        elif archive_type == 'lessons':
            query = supabase.table('archived_lessons').select('*')
            
            # Apply search filter
            if search_query:
                query = query.or_(f'title.ilike.%{search_query}%,subject_name.ilike.%{search_query}%')
            
            # Apply date filters
            if date_from:
                query = query.gte('archived_at', f'{date_from}T00:00:00')
            if date_to:
                query = query.lte('archived_at', f'{date_to}T23:59:59')
            
            response = query.order('archived_at', desc=True).execute()
            archives = response.data or []
            
            # Format display data
            for archive in archives:
                archive['display_name'] = archive.get('title', 'Unknown Lesson')
                archive['type_label'] = 'Lesson'
        
        elif archive_type == 'assignments':
            query = supabase.table('archived_assignments').select('*')
            
            # Apply search filter
            if search_query:
                query = query.or_(f'title.ilike.%{search_query}%,subject_name.ilike.%{search_query}%')
            
            # Apply date filters
            if date_from:
                query = query.gte('archived_at', f'{date_from}T00:00:00')
            if date_to:
                query = query.lte('archived_at', f'{date_to}T23:59:59')
            
            response = query.order('archived_at', desc=True).execute()
            archives = response.data or []
            
            # Format display data
            for archive in archives:
                archive['display_name'] = archive.get('title', 'Unknown Assignment')
                archive['type_label'] = 'Assignment'
        
        elif archive_type == 'submissions':
            query = supabase.table('archived_submissions').select('*')
            
            # Apply search filter
            if search_query:
                query = query.or_(f'student_name.ilike.%{search_query}%,assignment_title.ilike.%{search_query}%')
            
            # Apply date filters
            if date_from:
                query = query.gte('archived_at', f'{date_from}T00:00:00')
            if date_to:
                query = query.lte('archived_at', f'{date_to}T23:59:59')
            
            response = query.order('archived_at', desc=True).execute()
            archives = response.data or []
            
            # Format display data
            for archive in archives:
                student_name = archive.get('student_name', 'Unknown Student')
                assignment_title = archive.get('assignment_title', 'Unknown Assignment')
                archive['display_name'] = f"{student_name} - {assignment_title}"
                archive['type_label'] = 'Submission'
        
        elif archive_type == 'enrollments':
            query = supabase.table('archived_enrollments').select('*')
            
            # Apply search filter
            if search_query:
                query = query.or_(f'student_name.ilike.%{search_query}%,subject_name.ilike.%{search_query}%,teacher_name.ilike.%{search_query}%')
            
            # Apply date filters
            if date_from:
                query = query.gte('archived_at', f'{date_from}T00:00:00')
            if date_to:
                query = query.lte('archived_at', f'{date_to}T23:59:59')
            
            response = query.order('archived_at', desc=True).execute()
            archives = response.data or []
            
            # Format display data
            for archive in archives:
                student_name = archive.get('student_name', 'Unknown Student')
                subject_name = archive.get('subject_name', 'Unknown Subject')
                archive['display_name'] = f"{student_name} - {subject_name}"
                archive['type_label'] = 'Enrollment'
        
        # Format archived_at dates for display (convert to GMT+8 Philippine Time)
        from datetime import timedelta
        for archive in archives:
            if archive.get('archived_at'):
                try:
                    # Parse the UTC timestamp
                    dt = datetime.fromisoformat(archive['archived_at'].replace('Z', '+00:00'))
                    # Convert to Philippine Time (UTC+8)
                    dt_pht = dt + timedelta(hours=8)
                    archive['archived_at_formatted'] = dt_pht.strftime('%B %d, %Y at %I:%M %p')
                except:
                    archive['archived_at_formatted'] = archive['archived_at']
            else:
                archive['archived_at_formatted'] = 'Unknown'
    
    except PostgrestAPIError as e:
        flash(f'Database error loading archives: {e.message}', 'danger')
        print(f"Supabase DB Error (View Archives): {e}")
    except Exception as e:
        flash('An unexpected error occurred loading archives.', 'danger')
        print(f"Unexpected Error (View Archives): {e}")
    
    return render_template('AdminArchives.html',
                         archives=archives,
                         archive_type=archive_type,
                         search_query=search_query,
                         date_from=date_from,
                         date_to=date_to,
                         user_name=user_name)

@bp.route('/archives/view/<archive_type>/<int:original_id>')
@login_required
@role_required('Admin')
def view_archive_detail(archive_type, original_id):
    """View detailed information about a specific archived record."""
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Admin')
    
    if not supabase:
        flash('Supabase client not initialized.', 'danger')
        return redirect(url_for('admin.view_archives'))
    
    archive_detail = None
    table_name = None
    
    # Map archive type to table name
    type_to_table = {
        'users': 'archived_profiles',
        'subjects': 'archived_subjects',
        'lessons': 'archived_lessons',
        'assignments': 'archived_assignments',
        'submissions': 'archived_submissions',
        'enrollments': 'archived_enrollments'
    }
    
    table_name = type_to_table.get(archive_type)
    
    if not table_name:
        flash('Invalid archive type.', 'danger')
        return redirect(url_for('admin.view_archives'))
    
    try:
        response = supabase.table(table_name).select('*').eq('original_id', original_id).maybe_single().execute()
        archive_detail = response.data
        
        if not archive_detail:
            flash(f'Archive record not found.', 'warning')
            return redirect(url_for('admin.view_archives', type=archive_type))
        
        # Format archived_at date
        if archive_detail.get('archived_at'):
            try:
                dt = datetime.fromisoformat(archive_detail['archived_at'].replace('Z', '+00:00'))
                archive_detail['archived_at_formatted'] = dt.strftime('%B %d, %Y at %I:%M %p')
            except:
                archive_detail['archived_at_formatted'] = archive_detail['archived_at']
    
    except Exception as e:
        flash('Error loading archive details.', 'danger')
        print(f"Error loading archive detail: {e}")
        return redirect(url_for('admin.view_archives', type=archive_type))
    
    return render_template('AdminArchiveDetail.html',
                         archive=archive_detail,
                         archive_type=archive_type,
                         user_name=user_name)

@bp.route('/archives/unarchive/<archive_type>/<archive_id>', methods=['POST'])
@login_required
@role_required('Admin')
def unarchive_record(archive_type, archive_id):
    """Restore an archived record back to its original table."""
    admin_id = session.get('user_id')
    
    if not admin_id:
        flash('Admin user not found in session.', 'danger')
        return redirect(url_for('admin.view_archives', type=archive_type))
    
    try:
        result = None
        
        if archive_type == 'users':
            # Users use UUID strings, not integers
            result = unarchive_user(archive_id, admin_id)
        elif archive_type == 'subjects':
            # Convert to int for subjects, lessons, assignments
            result = unarchive_subject(int(archive_id), admin_id)
        elif archive_type == 'lessons':
            result = unarchive_lesson(int(archive_id), admin_id)
        elif archive_type == 'assignments':
            result = unarchive_assignment(int(archive_id), admin_id)
        else:
            flash(f'Unarchive not supported for {archive_type}.', 'warning')
            return redirect(url_for('admin.view_archives', type=archive_type))
        
        if result and result.get('success'):
            flash(result.get('message', 'Record restored successfully!'), 'success')
        else:
            flash(result.get('message', 'Failed to restore record.'), 'danger')
    
    except Exception as e:
        flash(f'Error restoring record: {str(e)}', 'danger')
        print(f"Error unarchiving {archive_type} {archive_id}: {e}")
    
    return redirect(url_for('admin.view_archives', type=archive_type))
