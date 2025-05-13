from functools import wraps
from flask import session, flash, redirect, url_for, abort

def login_required(f):
    """Decorator to ensure user is logged in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_role' not in session:
            flash('Please log in to access this page.', 'warning')
            # Use the correct endpoint name including blueprint
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(required_role):
    """Decorator to ensure user has the correct role."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_role' not in session:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login')) # Redirect to auth blueprint login

            user_role = session.get('user_role')
            if user_role != required_role:
                # flash(f'Access denied. You need the "{required_role}" role for this page.', 'danger') # Removed flash, 403 page will show message
                abort(403) # Trigger the 403 error handler

            return f(*args, **kwargs)
        return decorated_function
    return decorator

from datetime import datetime, timezone
from supabase import Client, PostgrestAPIError

# Define what statuses are considered "completed" for a submission
COMPLETED_SUBMISSION_STATUSES = ['Reviewed', 'Auto-Graded', 'Graded', 'Graded by Teacher'] 

def check_and_award_badges(submission_id: int, student_id: str, grade: float, status: str, supabase_client: Client):
    """
    Checks and awards badges to a student based on their submission.
    """
    if not all([submission_id, student_id, status, supabase_client]):
        print("Badge Check: Missing critical parameters.")
        return

    try:
        # --- Perfect Score Badge ---
        if grade is not None:
            try:
                current_grade = float(grade)
                if current_grade == 100.0:
                    # Fetch "Perfect Score!" badge details
                    perfect_score_badge_res = supabase_client.table('badges') \
                        .select('id') \
                        .eq('name', 'Perfect Score!') \
                        .maybe_single() \
                        .execute()

                    if perfect_score_badge_res.data:
                        perfect_score_badge_id = perfect_score_badge_res.data['id']
                        
                        # Check if this badge for this submission already awarded
                        existing_award_res = supabase_client.table('user_badges') \
                            .select('id', count='exact') \
                            .eq('user_id', student_id) \
                            .eq('badge_id', perfect_score_badge_id) \
                            .eq('submission_id', submission_id) \
                            .execute()

                        if existing_award_res.count == 0:
                            # Award the badge
                            supabase_client.table('user_badges').insert({
                                'user_id': student_id,
                                'badge_id': perfect_score_badge_id,
                                'submission_id': submission_id,
                                'earned_at': datetime.now(timezone.utc).isoformat()
                            }).execute()
                            print(f"Awarded 'Perfect Score!' badge to {student_id} for submission {submission_id}")
                            # flash('Perfect Score! badge awarded!', 'success') # Flashing here might be tricky from a util
                    else:
                        print("Badge Check: 'Perfect Score!' badge not found in database.")
            except ValueError:
                print(f"Badge Check: Could not convert grade '{grade}' to float for submission {submission_id}.")
            except PostgrestAPIError as e:
                print(f"Supabase error during 'Perfect Score!' badge check: {e.message}")


        # --- First Assignment Complete Badge ---
        print(f"FAC Badge Check: student_id={student_id}, submission_id={submission_id}, status='{status}'")
        if status in COMPLETED_SUBMISSION_STATUSES:
            print(f"FAC Badge Check: Status '{status}' is a completed status.")
            # Fetch "First Assignment Complete!" badge details
            first_complete_badge_res = supabase_client.table('badges') \
                .select('id') \
                .eq('name', 'First Assignment Complete!') \
                .maybe_single() \
                .execute()
            print(f"FAC Badge Check: Fetched badge 'First Assignment Complete!', data: {first_complete_badge_res.data}")

            if first_complete_badge_res.data:
                first_complete_badge_id = first_complete_badge_res.data['id']
                print(f"FAC Badge Check: Badge ID for 'First Assignment Complete!' is {first_complete_badge_id}.")

                # Check if student already has this badge
                already_has_first_badge_res = supabase_client.table('user_badges') \
                    .select('id', count='exact') \
                    .eq('user_id', student_id) \
                    .eq('badge_id', first_complete_badge_id) \
                    .execute()
                print(f"FAC Badge Check: Student already has badge? Count: {already_has_first_badge_res.count}, Data: {already_has_first_badge_res.data}")

                if already_has_first_badge_res.count == 0:
                    print(f"FAC Badge Check: Student does not have this badge yet.")
                    # Check if this is indeed their first completed assignment
                    completed_submissions_count_res = supabase_client.table('submissions') \
                        .select('id', count='exact') \
                        .eq('student_id', student_id) \
                        .in_('status', COMPLETED_SUBMISSION_STATUSES) \
                        .execute()
                    print(f"FAC Badge Check: Student's total completed submissions count: {completed_submissions_count_res.count}, Data: {completed_submissions_count_res.data}")
                    
                    # The count includes the current submission if its status was just updated to completed
                    if completed_submissions_count_res.count == 1:
                        print(f"FAC Badge Check: Conditions met! Attempting to award 'First Assignment Complete!' badge.")
                        supabase_client.table('user_badges').insert({
                            'user_id': student_id,
                            'badge_id': first_complete_badge_id,
                            'submission_id': submission_id, # Link to the submission that triggered it
                            'earned_at': datetime.now(timezone.utc).isoformat()
                        }).execute()
                        print(f"Awarded 'First Assignment Complete!' badge to {student_id} for submission {submission_id}")
                        # flash('First Assignment Complete! badge awarded!', 'success')
                    else: 
                        print(f"FAC Badge Check: Condition failed - completed_submissions_count_res.count ({completed_submissions_count_res.count}) is not 1.")
                else: 
                    print(f"FAC Badge Check: Condition failed - already_has_first_badge_res.count ({already_has_first_badge_res.count}) is not 0.")
            else: 
                print(f"FAC Badge Check: Condition failed - 'First Assignment Complete!' badge not found in database.")
        else: 
            print(f"FAC Badge Check: Condition failed - status '{status}' is not in COMPLETED_SUBMISSION_STATUSES {COMPLETED_SUBMISSION_STATUSES}.")
        
    except PostgrestAPIError as e:
        print(f"Supabase error during badge awarding process for submission {submission_id}: {e.message}")
    except Exception as e:
        print(f"Unexpected error in check_and_award_badges for submission {submission_id}: {e}")
