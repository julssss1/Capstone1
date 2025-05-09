from flask import render_template, request, session, redirect, url_for, flash, current_app
from . import bp
from app.utils import login_required, role_required
from supabase import create_client, Client, PostgrestAPIError
from gotrue.errors import AuthApiError


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

@bp.route('/users')
@login_required
@role_required('Admin')
def admin_user_management():
    print(f"Accessing Admin User Management BP for user: {session.get('user_name')}")
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Admin')
    search_query = request.args.get('search_query', '').strip()
    role_filter = request.args.get('role_filter', '').strip()
    users = []
    supabase_admin_client = None

    if not supabase:
        flash('Supabase client not initialized. Cannot load users.', 'danger')
        return render_template(
            'AdminUserManagement.html',
            users=users,
            user_name=user_name,
            search_query=search_query,
            role_filter=role_filter
        )

    try:
        admin_url = current_app.config.get("SUPABASE_URL")
        admin_key = current_app.config.get("SUPABASE_SERVICE_KEY")
        if not admin_url or not admin_key:
             flash("Critical Error: Supabase URL or Service Key missing. Cannot fetch user emails.", "danger")
             print("CRITICAL ERROR: Supabase URL/Service Key missing in config for admin client creation in user list.")
        else:
            supabase_admin_client = create_client(admin_url, admin_key)
            print("DEBUG: Temporary admin client created successfully for user list.")
    except Exception as admin_client_ex:
         flash("Critical Error: Failed to create Supabase admin client. Cannot fetch user emails.", "danger")
         print(f"CRITICAL ERROR: Failed to create admin client for user list: {admin_client_ex}")

    try:
        auth_users_map = {}
        if supabase_admin_client:
            try:
                print("DEBUG: Attempting to call supabase_admin_client.auth.admin.list_users()")
                list_users_response = supabase_admin_client.auth.admin.list_users()
                print(f"DEBUG: Raw list_users response type: {type(list_users_response)}")


                auth_users_list = []

                if hasattr(list_users_response, 'users') and isinstance(list_users_response.users, list):
                    auth_users_list = list_users_response.users
                    print(f"DEBUG: Extracted users from response.users attribute.")
                elif hasattr(list_users_response, 'data') and isinstance(list_users_response.data, list):
                     auth_users_list = list_users_response.data
                     print(f"DEBUG: Extracted users from response.data attribute.")
                elif isinstance(list_users_response, list):
                     auth_users_list = list_users_response
                     print(f"DEBUG: Response itself is a list of users.")

                else:
                     print(f"WARNING: Unexpected response structure from list_users: {type(list_users_response)}. Could not extract user list.")
                     flash("Warning: Could not retrieve user email details due to unexpected response format.", "warning")


                if not auth_users_list:
                     print("WARNING: No users found or extracted from the list_users response object.")

                for user in auth_users_list:
                    if hasattr(user, 'id') and hasattr(user, 'email') and user.id and user.email:
                        auth_users_map[str(user.id)] = {'email': user.email}
                    else:
                        print(f"WARNING: Skipping user object due to missing id/email or unexpected format: {user}")
                print(f"DEBUG: Fetched {len(auth_users_map)} users from Auth.")
            except AuthApiError as auth_error:
                flash(f'Error fetching authentication users: {auth_error.message}', 'danger')
                print(f"Supabase Auth Admin Error (List Users): {auth_error}")
            except Exception as e:
                flash('Unexpected error fetching authentication users.', 'danger')
                print(f"Unexpected Error fetching auth users: {e}")

        query = supabase.table('profiles').select('id, first_name, last_name, role')

        if role_filter:
            capitalized_role_filter = role_filter.capitalize()
            query = query.eq('role', capitalized_role_filter)

        query = query.order('last_name').order('first_name')
        profiles_response = query.execute()
        profiles_raw = profiles_response.data or []

        combined_users = []
        for profile in profiles_raw:
            user_id_str = str(profile.get('id'))
            user_data = {
                'id': user_id_str,
                'first_name': profile.get('first_name', ''),
                'last_name': profile.get('last_name', ''),
                'role': profile.get('role', ''),
                'email': auth_users_map.get(user_id_str, {}).get('email', 'N/A'),
                'display_name': f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip()
            }

            if search_query:
                name_match = search_query.lower() in user_data['display_name'].lower()
                email_match = search_query.lower() in user_data['email'].lower()
                if name_match or email_match:
                    combined_users.append(user_data)
            else:
                combined_users.append(user_data)

        users = combined_users

    except PostgrestAPIError as e:
        flash(f'Database error loading profiles: {e.message}', 'danger')
        print(f"Supabase DB Error (Admin User List - Profiles): {e}")
    except Exception as e:
        flash('An unexpected error occurred loading user data.', 'danger')
        print(f"Unexpected Error (Admin User List): {e}")

    return render_template(
        'AdminUserManagement.html',
        users=users,
        user_name=user_name,
        search_query=search_query,
        role_filter=role_filter
        )

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


@bp.route('/user/add', methods=['GET', 'POST'])
@login_required
@role_required('Admin')
def add_user():
    """Handles adding a new user (Auth + Profile)."""
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Admin')

    if not supabase:
        flash('Supabase client not initialized.', 'danger')
        return redirect(url_for('admin.admin_user_management'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        role = request.form.get('role')


        if not all([email, password, first_name, last_name, role]):
            flash('Email, Password, First Name, Last Name, and Role are required.', 'warning')
            profile_form_data = request.form.to_dict()
            return render_template('AdminUserAddEdit.html', profile=profile_form_data, user_name=user_name, action="Add")

        if role not in ['Student', 'Teacher', 'Admin']:
            flash('Invalid role selected.', 'danger')
            profile_form_data = request.form.to_dict()
            return render_template('AdminUserAddEdit.html', profile=profile_form_data, user_name=user_name, action="Add")

        new_user_id = None
        display_name = f"{first_name} {last_name}"


        supabase_admin_client = None
        try:
            admin_url = current_app.config.get("SUPABASE_URL")
            admin_key = current_app.config.get("SUPABASE_SERVICE_KEY")
            if not admin_url or not admin_key:
                 flash("Critical Error: Supabase URL or Service Key missing from config.", "danger")
                 print("CRITICAL ERROR: Supabase URL/Service Key missing in config for admin client creation.")
                 profile_form_data = request.form.to_dict()
                 return render_template('AdminUserAddEdit.html', profile=profile_form_data, user_name=user_name, action="Add")

            supabase_admin_client = create_client(admin_url, admin_key)
            print("DEBUG: Temporary admin client created successfully with service key.")
        except Exception as admin_client_ex:
             flash("Critical Error: Failed to create Supabase admin client.", "danger")
             print(f"CRITICAL ERROR: Failed to create admin client: {admin_client_ex}")
             profile_form_data = request.form.to_dict()
             return render_template('AdminUserAddEdit.html', profile=profile_form_data, user_name=user_name, action="Add")

        if not supabase_admin_client:
             profile_form_data = request.form.to_dict()
             return render_template('AdminUserAddEdit.html', profile=profile_form_data, user_name=user_name, action="Add")

        try:

            print(f"Attempting to create auth user for email: {email}")
            create_auth_user_response = supabase_admin_client.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {'first_name': first_name, 'last_name': last_name, 'role': role}
            })
            new_user = create_auth_user_response.user
            if not new_user or not new_user.id:
                 flash("Failed to retrieve new user ID from Supabase response.", "danger")
                 print(f"ERROR: Could not get user ID from create_user response: {create_auth_user_response}")

                 profile_form_data = request.form.to_dict()
                 return render_template('AdminUserAddEdit.html', profile=profile_form_data, user_name=user_name, action="Add")

            new_user_id = new_user.id
            print(f"Auth user created successfully with ID: {new_user_id}")

            print(f"Attempting to insert profile for user ID: {new_user_id} using admin's session")

            admin_access_token = session.get('access_token')
            admin_refresh_token = session.get('refresh_token')

            if not admin_access_token or not admin_refresh_token:
                flash("Admin session token not found. Cannot insert profile.", "danger")
                print("ERROR: Admin access_token or refresh_token missing from session.")
                try:
                    print(f"Attempting cleanup: Deleting orphaned auth user {new_user_id} due to missing admin token")
                    supabase_admin_client.auth.admin.delete_user(new_user_id)
                    print(f"Orphaned auth user {new_user_id} deleted.")
                except Exception as cleanup_error:
                    print(f"Failed to delete orphaned auth user {new_user_id}: {cleanup_error}")
                    flash("Critical error: Failed to clean up orphaned auth user after token error.", "danger")
                    profile_form_data = request.form.to_dict()
                    return render_template('AdminUserAddEdit.html', profile=profile_form_data, user_name=user_name, action="Add")

            try:
                url = current_app.config.get("SUPABASE_URL")
                anon_key = current_app.config.get("SUPABASE_ANON_KEY")
                if not url or not anon_key:
                    flash("Critical Error: Supabase URL or Anon Key missing for user client.", "danger")
                    print("CRITICAL ERROR: Supabase URL/Key missing for user client creation.")
                    try:
                        print(f"Attempting cleanup: Deleting orphaned auth user {new_user_id} due to missing user client config")
                        supabase_admin_client.auth.admin.delete_user(new_user_id)
                        print(f"Orphaned auth user {new_user_id} deleted.")
                    except Exception as cleanup_error:
                        print(f"Failed to delete orphaned auth user {new_user_id}: {cleanup_error}")
                        flash("Critical error: Failed to clean up orphaned auth user after user client config error.", "danger")
                    profile_form_data = request.form.to_dict()
                    return render_template('AdminUserAddEdit.html', profile=profile_form_data, user_name=user_name, action="Add")

                user_supabase = create_client(url, anon_key)
                user_supabase.auth.set_session(admin_access_token, admin_refresh_token)
                print(f"Temporary Supabase client created for admin user.")

                profile_insert_response = user_supabase.table('profiles').insert({
                    'id': new_user_id,
                    'first_name': first_name,
                    'last_name': last_name,
                    'role': role
                }).execute()
                print(f"Profile insert executed using admin context. Response status: {profile_insert_response.status_code if hasattr(profile_insert_response, 'status_code') else 'N/A'}")

            except Exception as user_client_error:
                flash(f"Error performing profile insert with admin context: {user_client_error}", "danger")
                print(f"ERROR: Failed during user-context profile insert for {new_user_id}: {user_client_error}")
                try:
                    print(f"Attempting cleanup: Deleting orphaned auth user {new_user_id} after user-context insert error")
                    supabase_admin_client.auth.admin.delete_user(new_user_id)
                    print(f"Orphaned auth user {new_user_id} deleted.")
                except Exception as cleanup_error:
                    print(f"Failed to delete orphaned auth user {new_user_id}: {cleanup_error}")
                    flash("Critical error: Failed to clean up orphaned auth user after profile insert failure.", "danger")
                profile_form_data = request.form.to_dict()
                return render_template('AdminUserAddEdit.html', profile=profile_form_data, user_name=user_name, action="Add")


            if profile_insert_response.data:
                print(f"Profile inserted successfully for user ID: {new_user_id}")
                flash(f"User '{display_name}' ({email}) created successfully!", "success")
                return redirect(url_for('admin.admin_user_management'))
            else:
                flash(f"Auth user created, but failed to insert profile for '{display_name}'. Manual cleanup required.", "danger")
                print(f"Failed profile insert after auth user creation for {new_user_id}. Response: {profile_insert_response}")
                try:
                    print(f"Attempting cleanup: Deleting orphaned auth user {new_user_id}")
                    supabase_admin_client.auth.admin.delete_user(new_user_id)
                    print(f"Orphaned auth user {new_user_id} deleted.")
                except Exception as cleanup_error:
                    print(f"Failed to delete orphaned auth user {new_user_id}: {cleanup_error}")
                    flash("Critical error: Failed to clean up orphaned auth user after profile insert failure.", "danger")
                return redirect(url_for('admin.admin_user_management'))

        except AuthApiError as auth_error:
            flash(f'Error creating authentication user: {auth_error.message}', 'danger')
            print(f"Supabase Auth Admin Error (Add User): {auth_error}")
        except PostgrestAPIError as db_error:
            flash(f'Database error creating user profile: {db_error.message}', 'danger')
            print(f"Supabase DB Error (Add User Profile): {db_error}")
            if new_user_id:
                 flash("Auth user might have been created before profile insert failed. Manual check recommended.", "warning")
        except Exception as e:
            flash('An unexpected error occurred adding the user.', 'danger')
            print(f"Unexpected Error (Add User): {e}")

        profile_form_data = request.form.to_dict()
        return render_template('AdminUserAddEdit.html', profile=profile_form_data, user_name=user_name, action="Add")

    return render_template('AdminUserAddEdit.html', profile={}, user_name=user_name, action="Add")



@bp.route('/user/edit/<user_id>', methods=['GET', 'POST'])
@login_required
@role_required('Admin')
def edit_user(user_id):
    """Handles editing user role and name (requires template)."""
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Admin')
    profile_data = None

    if not supabase:
        flash('Supabase client not initialized.', 'danger')
        return redirect(url_for('admin.admin_user_management'))

    try:
        profile_response = supabase.table('profiles') \
                                   .select('id, first_name, last_name, role') \
                                   .eq('id', user_id) \
                                   .maybe_single() \
                                   .execute()
        profile_data = profile_response.data
    except Exception as e:
        flash('Error fetching user profile details.', 'danger')
        print(f"Error fetching profile {user_id} for edit: {e}")
        return redirect(url_for('admin.admin_user_management'))

    if not profile_data:
        flash(f"User profile with ID {user_id} not found.", "warning")
        return redirect(url_for('admin.admin_user_management'))

    if request.method == 'POST':
        new_first_name = request.form.get('first_name', '').strip()
        new_last_name = request.form.get('last_name', '').strip()
        new_role = request.form.get('role')
        display_name = f"{new_first_name} {new_last_name}"

        if not new_first_name or not new_last_name or not new_role:
            flash('First Name, Last Name, and Role are required.', 'warning')
            return render_template('AdminUserAddEdit.html', profile=profile_data, user_name=user_name, action="Edit")

        if new_role not in ['Student', 'Teacher', 'Admin']:
            flash('Invalid role selected.', 'danger')
            return render_template('AdminUserAddEdit.html', profile=profile_data, user_name=user_name, action="Edit")

        try:
            update_data = {
                'first_name': new_first_name,
                'last_name': new_last_name,
                'role': new_role
            }
            update_response = supabase.table('profiles').update(update_data).eq('id', user_id).execute()

            if update_response.data:
                flash(f"User '{display_name}' profile updated successfully!", "success")

                return redirect(url_for('admin.admin_user_management'))
            else:
                flash("Failed to update user profile.", "danger")
                print(f"Failed Supabase profile update response: {update_response}")

        except PostgrestAPIError as e:
             flash(f'Database error updating profile: {e.message}', 'danger')
             print(f"Supabase DB Error (Edit User Profile {user_id}): {e}")
        except Exception as e:
            flash('An unexpected error occurred updating the profile.', 'danger')
            print(f"Unexpected Error (Edit User Profile {user_id}): {e}")

        return render_template('AdminUserAddEdit.html', profile=profile_data, user_name=user_name, action="Edit")

    return render_template('AdminUserAddEdit.html', profile=profile_data, user_name=user_name, action="Edit")


@bp.route('/user/delete/<user_id>', methods=['POST'])
@login_required
@role_required('Admin')
def delete_user(user_id):
    """Handles deleting a user from profiles and auth."""
    supabase: Client = current_app.supabase
    admin_user_id = session.get('user_id')

    if not supabase:
        flash('Supabase client not initialized.', 'danger')
        return redirect(url_for('admin.admin_user_management'))

    if str(admin_user_id) == str(user_id):
         flash("You cannot delete your own admin account.", "danger")
         return redirect(url_for('admin.admin_user_management'))

    profile_deleted = False
    auth_user_deleted = False
    display_name = f"User ID {user_id}"

    try:

        try:
            profile_info = supabase.table('profiles').select('first_name, last_name').eq('id', user_id).maybe_single().execute()
            if profile_info.data:
                 fname = profile_info.data.get('first_name', '')
                 lname = profile_info.data.get('last_name', '')
                 display_name = f"{fname} {lname}".strip() if fname or lname else display_name
        except Exception:
             pass

        print(f"Attempting to delete profile for user ID: {user_id} ({display_name})")
        profile_delete_response = supabase.table('profiles').delete().eq('id', user_id).execute()

        if profile_delete_response.data:
            profile_deleted = True
            print(f"Profile deleted successfully for {user_id}")
        else:
            print(f"Profile for {user_id} not found or not deleted. Response: {profile_delete_response.error or 'No data returned'}")
            if profile_info and not profile_info.data:
                 print(f"Confirmed profile {user_id} does not exist.")
                 profile_deleted = True
            elif not profile_info:
                 try:
                     profile_check = supabase.table('profiles').select('id').eq('id', user_id).maybe_single().execute()
                     if not profile_check.data:
                          print(f"Confirmed profile {user_id} does not exist.")
                          profile_deleted = True
                 except Exception:
                      print(f"Could not confirm if profile {user_id} exists.")

        if profile_deleted:
            print(f"Attempting to delete auth user ID: {user_id}")
            try:
                supabase_admin_client = None
                try:
                    admin_url = current_app.config.get("SUPABASE_URL")
                    admin_key = current_app.config.get("SUPABASE_SERVICE_KEY")
                    if not admin_url or not admin_key:
                        raise ValueError("Supabase URL or Service Key missing from config.")
                    supabase_admin_client = create_client(admin_url, admin_key)
                    print("DEBUG: Temporary admin client created successfully for user deletion.")
                except Exception as admin_client_ex:
                    print(f"CRITICAL ERROR: Failed to create admin client for deletion: {admin_client_ex}")
                    flash(f"Profile for '{display_name}' deleted, but failed to create admin client to delete auth user. Manual cleanup required.", "danger")
                    raise admin_client_ex

                supabase_admin_client.auth.admin.delete_user(user_id)
                auth_user_deleted = True
                print(f"Auth user deleted successfully for {user_id}")
                flash(f"User '{display_name}' deleted successfully from auth and profiles.", "success")

            except AuthApiError as auth_error:
                print(f"Supabase Auth Admin Error deleting user {user_id}: {auth_error}")
                flash(f"Profile for '{display_name}' deleted, but failed to delete authentication user: {auth_error.message}. Manual cleanup might be required.", "danger")
            except Exception as generic_auth_error:
                 print(f"Generic error deleting auth user {user_id}: {generic_auth_error}")
                 flash(f"Profile for '{display_name}' deleted, but an unexpected error occurred deleting authentication user.", "danger")
        else:
             flash(f"Failed to delete profile for user ID {user_id} ({display_name}). Cannot proceed with deleting authentication user.", "danger")


    except PostgrestAPIError as db_error:
        flash(f'Database error during user deletion process: {db_error.message}', 'danger')
        print(f"Supabase DB Error deleting profile {user_id}: {db_error}")
    except Exception as e:
        flash('An unexpected error occurred during the user deletion process.', 'danger')
        print(f"Unexpected Error deleting user {user_id}: {e}")

    return redirect(url_for('admin.admin_user_management'))



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