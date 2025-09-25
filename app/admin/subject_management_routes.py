from flask import render_template, request, session, redirect, url_for, flash, current_app
from . import bp
from app.utils import login_required, role_required
from supabase import Client, PostgrestAPIError

def _get_teachers(supabase: Client):
    """Helper function to fetch teachers for dropdowns."""
    try:
        teachers_response = supabase.table('profiles') \
                                    .select('id, first_name, last_name') \
                                    .eq('role', 'Teacher') \
                                    .order('last_name') \
                                    .order('first_name') \
                                    .execute()
        teachers_raw = teachers_response.data or []
        teachers = []
        for teacher in teachers_raw:
            display_name = f"{teacher.get('first_name', '')} {teacher.get('last_name', '')}".strip()
            teachers.append({
                'id': teacher['id'],
                'display_name': display_name if display_name else f"Teacher ID {teacher['id']}"
            })
        return teachers
    except Exception as e:
        print(f"Error fetching teachers: {e}")
        return []

@bp.route('/subjects')
@login_required
@role_required('Admin')
def admin_subject_management():
    print(f"Accessing Admin Subject Management BP for user: {session.get('user_name')}")
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Admin')
    subjects = []

    if not supabase:
        flash('Supabase client not initialized. Cannot load subjects.', 'danger')
    else:
        try:
            subjects_response = supabase.table('subjects') \
                                        .select('id, name, description, profiles(id, first_name, last_name)') \
                                        .order('name') \
                                        .execute()
            subjects_raw = subjects_response.data or []

            subjects = []
            for subject in subjects_raw:
                teacher_profile = subject.get('profiles')
                if teacher_profile:
                    teacher_name = f"{teacher_profile.get('first_name', '')} {teacher_profile.get('last_name', '')}".strip()
                    subject['teacher_name'] = teacher_name if teacher_name else "N/A"
                else:
                    subject['teacher_name'] = "N/A"
                subjects.append(subject)

        except PostgrestAPIError as e:
            flash(f'Database error loading subjects: {e.message}', 'danger')
            print(f"Supabase DB Error (Admin Subject List): {e}")
        except Exception as e:
            flash('An unexpected error occurred loading subjects.', 'danger')
            print(f"Unexpected Error (Admin Subject List): {e}")

    return render_template(
        'Admin-Subject.html',
        subjects=subjects,
        user_name=user_name
        )

@bp.route('/subjects/view/<int:subject_id>')
@login_required
@role_required('Admin')
def view_manage_subject(subject_id):
    """Displays a single subject and its associated lessons."""
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Admin')
    subject = None
    lessons = []

    if not supabase:
        flash('Supabase client not initialized.', 'danger')
        return redirect(url_for('admin.admin_subject_management'))

    try:
        # Fetch subject details including the teacher's name
        subject_response = supabase.table('subjects') \
                                   .select('id, name, description, profiles(id, first_name, last_name)') \
                                   .eq('id', subject_id) \
                                   .maybe_single() \
                                   .execute()
        subject = subject_response.data

        if subject:
            teacher_profile = subject.get('profiles')
            if teacher_profile:
                subject['teacher_name'] = f"{teacher_profile.get('first_name', '')} {teacher_profile.get('last_name', '')}".strip()
            else:
                subject['teacher_name'] = "Not Assigned"

            # Fetch lessons for this subject
            lessons_response = supabase.table('lessons') \
                                       .select('id, title, description, profiles(id, first_name, last_name)') \
                                       .eq('subject_id', subject_id) \
                                       .order('title') \
                                       .execute()
            lessons_raw = lessons_response.data or []
            
            for lesson in lessons_raw:
                creator_profile = lesson.get('profiles')
                if creator_profile:
                    lesson['created_by_name'] = f"{creator_profile.get('first_name', '')} {creator_profile.get('last_name', '')}".strip()
                else:
                    lesson['created_by_name'] = "N/A"
                lessons.append(lesson)

    except Exception as e:
        flash('An error occurred while fetching subject details.', 'danger')
        print(f"Error fetching subject/lessons for view/manage: {e}")
        return redirect(url_for('admin.admin_subject_management'))

    if not subject:
        flash(f"Subject with ID {subject_id} not found.", 'warning')
        return redirect(url_for('admin.admin_subject_management'))

    return render_template(
        'AdminSubjectViewManage.html',
        subject=subject,
        lessons=lessons,
        user_name=user_name
    )

@bp.route('/subject/add', methods=['GET', 'POST'])
@login_required
@role_required('Admin')
def add_subject():
    """Handles adding a new subject."""
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Admin')

    if not supabase:
        flash('Supabase client not initialized.', 'danger')
        return redirect(url_for('admin.admin_subject_management'))

    teachers = _get_teachers(supabase)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        teacher_id = request.form.get('teacher_id')

        if not name or not teacher_id:
            flash('Subject Name and Assigned Teacher are required.', 'warning')
            return render_template('AdminSubjectAddEdit.html', teachers=teachers, subject=request.form, user_name=user_name, action="Add")

        if not any(t['id'] == teacher_id for t in teachers):
             flash('Invalid Teacher selected.', 'danger')
             return render_template('AdminSubjectAddEdit.html', teachers=teachers, subject=request.form, user_name=user_name, action="Add")

        try:
            insert_response = supabase.table('subjects').insert({
                'name': name,
                'description': description,
                'teacher_id': teacher_id
            }).execute()

            if insert_response.data:
                flash(f"Subject '{name}' added successfully!", "success")
                return redirect(url_for('admin.admin_subject_management'))
            else:
                flash("Failed to add subject. Please try again.", "danger")
                print(f"Failed Supabase subject insert response: {insert_response}")

        except PostgrestAPIError as e:
            if 'duplicate key value violates unique constraint' in e.message:
                 flash(f'Subject name "{name}" already exists.', 'danger')
            else:
                 flash(f'Database error adding subject: {e.message}', 'danger')
            print(f"Supabase DB Error (Add Subject): {e}")
        except Exception as e:
            flash('An unexpected error occurred adding the subject.', 'danger')
            print(f"Unexpected Error (Add Subject): {e}")

        return render_template('AdminSubjectAddEdit.html', teachers=teachers, subject=request.form, user_name=user_name, action="Add")

    return render_template('AdminSubjectAddEdit.html', teachers=teachers, subject={}, user_name=user_name, action="Add")

@bp.route('/subject/edit/<int:subject_id>', methods=['GET', 'POST'])
@login_required
@role_required('Admin')
def edit_subject(subject_id):
    """Handles editing an existing subject."""
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Admin')
    subject_data = None

    if not supabase:
        flash('Supabase client not initialized.', 'danger')
        return redirect(url_for('admin.admin_subject_management'))

    teachers = _get_teachers(supabase)

    try:
        subject_response = supabase.table('subjects') \
                                   .select('id, name, description, teacher_id') \
                                   .eq('id', subject_id) \
                                   .maybe_single() \
                                   .execute()
        subject_data = subject_response.data
    except Exception as e:
        flash('Error fetching subject details.', 'danger')
        print(f"Error fetching subject {subject_id} for edit: {e}")
        return redirect(url_for('admin.admin_subject_management'))

    if not subject_data:
        flash(f"Subject with ID {subject_id} not found.", "warning")
        return redirect(url_for('admin.admin_subject_management'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        teacher_id = request.form.get('teacher_id')

        if not name or not teacher_id:
            flash('Subject Name and Assigned Teacher are required.', 'warning')
            return render_template('AdminSubjectAddEdit.html', teachers=teachers, subject=subject_data, user_name=user_name, action="Edit")

        if not any(t['id'] == teacher_id for t in teachers):
             flash('Invalid Teacher selected.', 'danger')
             return render_template('AdminSubjectAddEdit.html', teachers=teachers, subject=subject_data, user_name=user_name, action="Edit")

        try:
            update_response = supabase.table('subjects').update({
                'name': name,
                'description': description,
                'teacher_id': teacher_id
            }).eq('id', subject_id).execute()

            if update_response.data:
                flash(f"Subject '{name}' updated successfully!", "success")
                return redirect(url_for('admin.admin_subject_management'))
            else:
                flash("Failed to update subject. It might no longer exist.", "danger")
                print(f"Failed Supabase subject update response: {update_response}")

        except PostgrestAPIError as e:
             if 'duplicate key value violates unique constraint' in e.message:
                 flash(f'Subject name "{name}" already exists.', 'danger')
             else:
                 flash(f'Database error updating subject: {e.message}', 'danger')
             print(f"Supabase DB Error (Edit Subject {subject_id}): {e}")
        except Exception as e:
            flash('An unexpected error occurred updating the subject.', 'danger')
            print(f"Unexpected Error (Edit Subject {subject_id}): {e}")

        return render_template('AdminSubjectAddEdit.html', teachers=teachers, subject=subject_data, user_name=user_name, action="Edit")

    return render_template('AdminSubjectAddEdit.html', teachers=teachers, subject=subject_data, user_name=user_name, action="Edit")

@bp.route('/subject/delete/<int:subject_id>', methods=['POST'])
@login_required
@role_required('Admin')
def delete_subject(subject_id):
    """Handles deleting a subject."""
    supabase: Client = current_app.supabase

    if not supabase:
        flash('Supabase client not initialized.', 'danger')
        return redirect(url_for('admin.admin_subject_management'))

    try:

        delete_response = supabase.table('subjects').delete().eq('id', subject_id).execute()

        if delete_response.data:
            flash(f"Subject ID {subject_id} deleted successfully.", "success")
            print(f"Admin deleted subject ID: {subject_id}")
        else:
            flash(f"Failed to delete subject ID {subject_id}. It might have already been deleted.", "warning")
            print(f"Failed Supabase subject delete response: {delete_response}")

    except PostgrestAPIError as e:
        if 'violates foreign key constraint' in e.message:
             flash(f'Cannot delete subject ID {subject_id} because it still has associated data (e.g., assignments, enrollments). Please remove associated data first.', 'danger')
        else:
             flash(f'Database error deleting subject: {e.message}', 'danger')
        print(f"Supabase DB Error (Delete Subject {subject_id}): {e}")
    except Exception as e:
        flash('An unexpected error occurred deleting the subject.', 'danger')
        print(f"Unexpected Error (Delete Subject {subject_id}): {e}")

    return redirect(url_for('admin.admin_subject_management'))
