from flask import render_template, session, url_for, request, flash, redirect, current_app
from . import bp  # Use . to import bp from the current package (student)
from app.utils import login_required, role_required
from supabase import Client, PostgrestAPIError, AuthApiError # Added AuthApiError
from werkzeug.utils import secure_filename
import os
from datetime import datetime

@bp.route('/account_profile')
@login_required
@role_required('Student')
def student_account_profile():
    supabase: Client = current_app.supabase
    user_id = session.get('user_id')
    profile_data = {}
    badges = []
    user_level = "Neophyte" 
    progress_to_next_level = 25 
    user_grade = "N/A"

    if not user_id or not supabase:
        flash('User session or database connection invalid. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))

    try:
        profile_res = supabase.table('profiles').select('*').eq('id', user_id).maybe_single().execute()
        if profile_res and profile_res.data:
            profile_data = profile_res.data
            avatar_path = profile_data.get('avatar_path')
            if avatar_path and not avatar_path.startswith('http') and not avatar_path.startswith('/static/'):
                try:
                    profile_data['avatar_path'] = supabase.storage.from_('avatars').get_public_url(avatar_path)
                except Exception as e:
                    print(f"Error getting public URL for avatar '{avatar_path}': {e}")
                    profile_data['avatar_path'] = url_for('static', filename='Images/default_avatar.png')
            elif not avatar_path:
                profile_data['avatar_path'] = url_for('static', filename='Images/default_avatar.png')

            access_token = session.get('access_token')
            refresh_token = session.get('refresh_token') # Get refresh token
            user_email_fetched = False

            if access_token:
                try:
                    user_auth_details = supabase.auth.get_user(jwt=access_token)
                    if user_auth_details and user_auth_details.user:
                        profile_data['email'] = user_auth_details.user.email or "Email not set"
                        user_email_fetched = True
                except AuthApiError as e: # Catch Supabase specific auth errors
                    print(f"Supabase auth error with current access token: {e}. Attempting refresh.")
                    if "invalid token" in str(e).lower() or "token is expired" in str(e).lower() or "jwt expired" in str(e).lower() and refresh_token:
                        try:
                            # Attempt to refresh the session using the refresh token
                            # Note: The exact method for supabase-py might be slightly different,
                            # e.g., client.auth.set_session(access_token, refresh_token) and then it auto-refreshes,
                            # or a more direct refresh method. refresh_session is a common pattern.
                            new_auth_response = supabase.auth.refresh_session(refresh_token)
                            if new_auth_response and new_auth_response.session:
                                print("Supabase session refreshed successfully.")
                                session['access_token'] = new_auth_response.session.access_token
                                if new_auth_response.session.refresh_token: # Update refresh token if a new one is provided
                                    session['refresh_token'] = new_auth_response.session.refresh_token
                                
                                # Retry get_user with the new token
                                user_auth_details = supabase.auth.get_user(jwt=new_auth_response.session.access_token)
                                if user_auth_details and user_auth_details.user:
                                    profile_data['email'] = user_auth_details.user.email or "Email not set"
                                    user_email_fetched = True
                                else:
                                    print("Failed to get user details even after token refresh.")
                            else:
                                print("Supabase token refresh failed or returned no session.")
                        except AuthApiError as refresh_e:
                            print(f"Error during Supabase token refresh: {refresh_e}")
                        except Exception as general_refresh_e:
                             print(f"Unexpected error during Supabase token refresh: {general_refresh_e}")
                    else:
                        print(f"Supabase auth error not JWT expiry related or no refresh token: {e}")
                except Exception as e_gen:
                    print(f"Generic error fetching user with token: {e_gen}")

            if not user_email_fetched:
                profile_data['email'] = "Could not fetch email (auth issue)"
                # If tokens are bad and refresh failed, consider redirecting to login
                if not access_token or (access_token and not user_email_fetched and "Supabase auth error" in locals().get('e', '') ): # Heuristic
                    flash('Your session may have expired. Please log in again.', 'warning')
                    # Potentially clear stale session tokens here before redirect
                    session.pop('access_token', None)
                    session.pop('refresh_token', None)
                    return redirect(url_for('auth.login')) # Redirect if auth fails critically
        else:
            profile_data['avatar_path'] = url_for('static', filename='Images/default_avatar.png')
            profile_data['email'] = "Profile not found"

        badges_res = supabase.table('user_badges') \
            .select('badges(name, icon_url, description)') \
            .eq('user_id', user_id) \
            .execute()
        if badges_res and badges_res.data:
            raw_badges = [item.get('badges') for item in badges_res.data if item.get('badges')]
            for badge_data in raw_badges:
                if badge_data:
                    db_icon_path = badge_data.get('icon_url')
                    if db_icon_path:
                        try:
                            badge_data['icon_url'] = supabase.storage.from_('badges').get_public_url(db_icon_path)
                        except Exception as e:
                            print(f"Error getting public URL for badge icon '{db_icon_path}' from 'badges' bucket: {e}")
                            badge_data['icon_url'] = url_for('static', filename='Images/default_badge.png') 
                    else:
                        badge_data['icon_url'] = url_for('static', filename='Images/default_badge.png')
                    badges.append(badge_data)
        
        profile_data['first_name'] = profile_data.get('first_name', '')
        profile_data['last_name'] = profile_data.get('last_name', '')
        profile_data['middle_name'] = profile_data.get('middle_name', '')

    except Exception as e:
        flash(f'Error fetching account profile details: {str(e)}', 'danger')
        print(f"Error in student_account_profile: {e}")
        if not profile_data.get('avatar_path'):
            profile_data['avatar_path'] = url_for('static', filename='Images/default_avatar.png')
        if not profile_data.get('email'):
            profile_data['email'] = "Error fetching email"
        profile_data.setdefault('first_name', 'N/A')
        profile_data.setdefault('last_name', '')
    
    profile_data['student_id'] = user_id
    display_user_name = f"{profile_data.get('first_name','')} {profile_data.get('last_name','')} ".strip() or session.get('user_name', 'Student')

    return render_template(
        'StudentAccountProfile.html',
        user=profile_data,
        badges=badges,
        user_level=user_level,
        progress_to_next_level=progress_to_next_level,
        user_grade=user_grade,
        user_name=display_user_name
    )

@bp.route('/edit_account_settings')
@login_required
@role_required('Student')
def student_edit_account_settings():
    user_name = session.get('user_name', 'Student')
    user_email = "Not available"
    access_token = session.get('access_token')
    supabase: Client = current_app.supabase
    user_id = session.get('user_id')
    profile_data = {} 

    if access_token and supabase and user_id:
        try:
            user_auth_details = supabase.auth.get_user(jwt=access_token)
            if user_auth_details and user_auth_details.user: 
                user_email = user_auth_details.user.email or "Email not set"
            
            profile_res = supabase.table('profiles').select('*').eq('id', user_id).maybe_single().execute()
            if profile_res and profile_res.data:
                profile_data = profile_res.data
                db_first_name = profile_data.get('first_name','')
                db_last_name = profile_data.get('last_name','')
                if db_first_name or db_last_name:
                    user_name = f"{db_first_name} {db_last_name}".strip()
                session['user_name'] = user_name 
        except Exception as e:
            flash(f'Error fetching profile details: {e}', 'warning')
            print(f"Error in student_settings profile fetch: {e}")
    else:
        flash('Session invalid. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))

    avatar_url = profile_data.get('avatar_path')
    if avatar_url and not avatar_url.startswith('http') and not avatar_url.startswith('/static/'): 
        try:
            avatar_url = supabase.storage.from_('avatars').get_public_url(avatar_url)
        except Exception as e: 
            print(f"Error getting public URL for avatar: {e}")
            avatar_url = url_for('static', filename='Images/yvan.png') # Default fallback
    elif not avatar_url:
        avatar_url = url_for('static', filename='Images/yvan.png') # Default fallback

    return render_template(
        'StudentSettings.html', 
        profile_first_name=profile_data.get('first_name'),
        profile_middle_name=profile_data.get('middle_name'),
        profile_last_name=profile_data.get('last_name'),
        user_name=user_name, 
        user_email=user_email, 
        avatar_url=avatar_url
    )

@bp.route('/update_profile', methods=['POST'])
@login_required
@role_required('Student')
def update_profile():
    supabase: Client = current_app.supabase
    user_id = session.get('user_id')
    bucket_name = "avatars"

    # --- Start Debugging ---
    print(f"DEBUG update_profile: User ID from session: {user_id}")
    if not user_id:
        print("DEBUG update_profile: Critical error - User ID not found in session.")
        flash('Critical error: User ID not found in session. Please re-login.', 'danger')
        return redirect(url_for('student.student_edit_account_settings'))
    # --- End Debugging ---
    file = request.files.get('profile_picture')

    if not file or file.filename == '':
        flash('No file selected.', 'warning'); return redirect(url_for('student.student_edit_account_settings'))

    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
    if '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions:
        filename = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        storage_path = f"{user_id}/{timestamp}_{filename}"

        # --- Start Debugging ---
        print(f"DEBUG update_profile: Attempting to upload to bucket='{bucket_name}', path='{storage_path}'")
        # --- End Debugging ---

        try:
            file_content = file.read()
            # It's good practice to seek(0) if you might read a file multiple times,
            # but here it's read once before upload.
            # file.seek(0) 
            
            upload_api_response = supabase.storage.from_(bucket_name).upload(
                path=storage_path, file=file_content,
                file_options={"content-type": file.content_type, "cache-control": "3600", "upsert": "false"}
            )
            # --- Start Debugging ---
            # The supabase-py storage client might raise an exception on HTTP error,
            # or return a response object. The error message suggests an exception is caught.
            # If it returns a response object, we might log it here.
            # print(f"DEBUG update_profile: Raw storage upload API response: {upload_api_response}")
            # --- End Debugging ---

            # If the upload fails due to RLS, it often raises an exception that is caught below.
            # If it didn't raise an exception but still failed, the following DB update might be an issue,
            # but the error message points to the upload ("new row" in storage.objects).

            update_profiles_response = supabase.table('profiles').update({'avatar_path': storage_path}).eq('id', user_id).execute()
            
            if update_profiles_response and hasattr(update_profiles_response, 'error') and update_profiles_response.error:
                 flash(f'Database update failed: {update_profiles_response.error.message}', 'danger')
                 print(f"DEBUG update_profile: Database update error: {update_profiles_response.error}")
            elif update_profiles_response and update_profiles_response.data:
                 flash('Profile picture updated successfully!', 'success')
            else:
                 flash('Profile picture uploaded, but database update response was unexpected or returned no data.', 'warning')
                 print(f"DEBUG update_profile: Unexpected DB update response: {update_profiles_response}")

        except PostgrestAPIError as pg_e: # Catch database specific errors first
            flash(f'Database error after upload: {pg_e.message}', 'danger')
            print(f"DEBUG update_profile: Database update PostgrestAPIError: {pg_e}")
        except Exception as e: # Catch other errors, including potential storage errors
            # This is where the RLS error from storage is likely caught
            flash(f'Error uploading file: {str(e)}', 'danger')
            print(f"DEBUG update_profile: Upload error (Exception type: {type(e)}): {e}")
    else:
        flash('Invalid file type.', 'danger')
    return redirect(url_for('student.student_edit_account_settings'))

@bp.route('/change_password', methods=['POST'])
@login_required
@role_required('Student')
def change_password():
    new_password = request.form.get('new_password')
    supabase: Client = current_app.supabase
    access_token = session.get('access_token') 

    if not new_password or len(new_password) < 6:
        flash('New password must be at least 6 characters long.', 'danger')
        return redirect(url_for('student.student_edit_account_settings'))
    if not access_token or not supabase: 
        flash('Session or connection error. Please re-login.', 'danger')
        return redirect(url_for('auth.login'))

    try:
        supabase.auth.update_user({"password": new_password}) 
        flash('Password updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating password: {e}', 'danger')
        print(f"Password update error: {e}")

    return redirect(url_for('student.student_edit_account_settings'))
