from flask import render_template, request, session, redirect, url_for, flash, current_app
import re
from . import bp
from app.utils import login_required, role_required
from supabase import create_client, Client, PostgrestAPIError
from gotrue.errors import AuthApiError

@bp.route('/users')
@login_required
@role_required('Admin')
def admin_user_management():
    print(f"Accessing Admin User Management BP for user: {session.get('user_name')}")
    
    # Clear pending reset request if coming from cancel button
    if request.args.get('clear_reset') == '1':
        session.pop('pending_reset_request_id', None)
    
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

        query = supabase.table('profiles').select('id, first_name, last_name, middle_name, role') # Added middle_name

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
                'middle_name': profile.get('middle_name', ''), # Get middle_name
                'role': profile.get('role', ''),
                'email': auth_users_map.get(user_id_str, {}).get('email', 'N/A')
            }
            
            # Construct display_name with middle initial
            fn = user_data['first_name']
            ln = user_data['last_name']
            mn = user_data['middle_name']
            middle_initial = f" {mn[0]}." if mn else ""
            user_data['display_name'] = f"{fn}{middle_initial} {ln}".strip().replace("  ", " ")

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
        middle_name = request.form.get('middle_name', '').strip()
        role = request.form.get('role')
        
        # --- Server-side Validation ---
        errors = {}
        name_regex = r"^[a-zA-Z\s'-]+$"
        name_error_msg = "Names can only contain letters, spaces, hyphens (-), and apostrophes (')."

        if not first_name:
            errors['first_name'] = 'First name is required.'
        elif not re.match(name_regex, first_name):
            errors['first_name'] = name_error_msg
        
        if not last_name:
            errors['last_name'] = 'Last name is required.'
        elif not re.match(name_regex, last_name):
            errors['last_name'] = name_error_msg

        if middle_name and not re.match(name_regex, middle_name):
            errors['middle_name'] = name_error_msg
        if not email:
            errors['email'] = 'Email is required.'
        elif not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            errors['email'] = 'Please enter a valid email address.'
        if not password:
            errors['password'] = 'Password is required.'
        elif len(password) < 8:
            errors['password'] = 'Password must be at least 8 characters long.'
        if not role:
            errors['role'] = 'Please select a role.'
        elif role not in ['Student', 'Teacher', 'Admin']:
            errors['role'] = 'Invalid role selected.'

        if errors:
            for field, msg in errors.items():
                flash(f"{msg}", 'danger') # Flash each error
            profile_form_data = request.form.to_dict()
            return render_template('AdminUserAddEdit.html', profile=profile_form_data, user_name=user_name, action="Add", errors=errors)

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
    # Clear pending reset request when leaving the page via cancel or after saving
    # This is handled in the template's cancel button and after successful save
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Admin')
    current_user_id = session.get('user_id') # Get current admin's ID
    profile_data = None

    if not supabase:
        flash('Supabase client not initialized.', 'danger')
        return redirect(url_for('admin.admin_user_management'))

    try:
        # Fetch profile details, now including middle_name
        profile_response = supabase.table('profiles') \
                                   .select('id, first_name, last_name, role, avatar_path, middle_name') \
                                   .eq('id', user_id) \
                                   .maybe_single() \
                                   .execute()
        profile_data = profile_response.data

        if profile_data:
            # Ensure middle_name key exists if it's null from DB, for template safety
            profile_data.setdefault('middle_name', None)

            # Fetch email from Auth
            try:
                admin_url = current_app.config.get("SUPABASE_URL")
                admin_key = current_app.config.get("SUPABASE_SERVICE_KEY")
                if not admin_url or not admin_key:
                    flash("Critical Error: Supabase URL or Service Key missing. Cannot fetch user email.", "danger")
                    profile_data['email'] = 'N/A (Config Error)'
                else:
                    supabase_admin_client = create_client(admin_url, admin_key)
                    auth_user_response = supabase_admin_client.auth.admin.get_user_by_id(user_id)
                    if auth_user_response.user and auth_user_response.user.email:
                        profile_data['email'] = auth_user_response.user.email
                    else:
                        profile_data['email'] = 'N/A (Not Found)'
                        print(f"Could not retrieve email for user {user_id} from auth.")
            except Exception as auth_e:
                print(f"Error fetching email for user {user_id} from auth: {auth_e}")
                profile_data['email'] = 'N/A (Auth Error)'

            # Avatar URL logic
            if profile_data.get('avatar_path'):
                try:
                    public_url_response = supabase.storage.from_('avatars').get_public_url(profile_data['avatar_path'])
                    profile_data['avatar_url'] = public_url_response
                except Exception as e_storage:
                    print(f"Error getting public URL for avatar {profile_data['avatar_path']}: {e_storage}")
                    profile_data['avatar_url'] = None # Fallback
            else:
                profile_data['avatar_url'] = None
        else:
            # profile_data is None, handled further down
            pass

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
        # Retrieve middle_name from form
        new_middle_name = request.form.get('middle_name', '').strip()
        new_role = request.form.get('role')
        new_password = request.form.get('new_password', '') # For optional password change

        display_name = f"{new_first_name} {new_last_name}"

        # --- Server-side Validation ---
        errors = {}
        name_regex = r"^[a-zA-Z\s'-]+$"
        name_error_msg = "Names can only contain letters, spaces, hyphens (-), and apostrophes (')."

        if not new_first_name:
            errors['first_name'] = 'First name is required.'
        elif not re.match(name_regex, new_first_name):
            errors['first_name'] = name_error_msg

        if not new_last_name:
            errors['last_name'] = 'Last name is required.'
        elif not re.match(name_regex, new_last_name):
            errors['last_name'] = name_error_msg
            
        if new_middle_name and not re.match(name_regex, new_middle_name):
            errors['middle_name'] = name_error_msg
        if not new_role:
            errors['role'] = 'Please select a role.'
        elif new_role not in ['Student', 'Teacher', 'Admin']:
            errors['role'] = 'Invalid role selected.'
        
        # Validate new password only if it's provided
        if new_password and len(new_password) < 8:
            errors['new_password'] = 'Password must be at least 8 characters long.'

        if errors:
            for field, msg in errors.items():
                flash(f"{msg}", 'danger')
            # Repopulate form data with attempted changes
            profile_data.update(request.form.to_dict())
            return render_template('AdminUserAddEdit.html', profile=profile_data, user_name=user_name, action="Edit", current_user_id=current_user_id, errors=errors)

        try:
            update_data = {
                'first_name': new_first_name,
                'last_name': new_last_name,
                'middle_name': new_middle_name if new_middle_name else None, # Add middle_name to update
                'role': new_role
            }
            # Update profile in Supabase
            update_response = supabase.table('profiles').update(update_data).eq('id', user_id).execute()

            if not update_response.data:
                flash("Failed to update user profile details.", "danger")
                print(f"Failed Supabase profile update response: {update_response}")
                # Still try to update password if provided
            
            password_updated_msg = ""
            if new_password:
                supabase_admin_client = None
                try:
                    admin_url = current_app.config.get("SUPABASE_URL")
                    admin_key = current_app.config.get("SUPABASE_SERVICE_KEY")
                    if not admin_url or not admin_key:
                        raise ValueError("Supabase URL or Service Key missing for admin client.")
                    supabase_admin_client = create_client(admin_url, admin_key)
                    
                    supabase_admin_client.auth.admin.update_user_by_id(
                        user_id, {"password": new_password}
                    )
                    password_updated_msg = " Password updated."
                    print(f"Admin updated password for user {user_id}")
                except Exception as e_pwd:
                    flash(f"Profile details updated, but failed to update password: {e_pwd}", "warning")
                    print(f"Error updating password for user {user_id} by admin: {e_pwd}")

            if update_response.data: # Check if profile update was successful
                flash(f"User '{display_name}' profile updated successfully!{password_updated_msg}", "success")
                # Stay on the same page by redirecting to edit_user with the same user_id
                return redirect(url_for('admin.edit_user', user_id=user_id))
            # If only password update failed but profile was ok, it would have flashed above.
            # If profile update failed, it flashed above.

        except PostgrestAPIError as e:
             flash(f'Database error updating profile: {e.message}', 'danger')
             print(f"Supabase DB Error (Edit User Profile {user_id}): {e}")
        except Exception as e:
            flash(f'An unexpected error occurred updating the profile: {e}', 'danger')
            print(f"Unexpected Error (Edit User Profile {user_id}): {e}")

        return render_template('AdminUserAddEdit.html', profile=profile_data, user_name=user_name, action="Edit", current_user_id=current_user_id)

    return render_template('AdminUserAddEdit.html', profile=profile_data, user_name=user_name, action="Edit", current_user_id=current_user_id)

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
