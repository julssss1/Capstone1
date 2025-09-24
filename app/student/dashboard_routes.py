from flask import render_template, session, url_for, current_app
from . import bp  # Use . to import bp from the current package (student)
from app.utils import login_required, role_required
from app.sign_logic import get_available_signs # Only get_available_signs is needed here
from supabase import Client, PostgrestAPIError
from datetime import datetime, timezone

@bp.route('/dashboard')
@login_required
@role_required('Student')
def student_dashboard():
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Student')
    student_id = session.get('user_id')
    
    model_signs = get_available_signs()
    available_signs = model_signs if model_signs else sorted(list(set([chr(i) for i in range(ord('A'), ord('Z') + 1)] + ['Hello', 'Thank You', 'I Love You'])))
    
    dashboard_assignments = []

    if student_id and supabase:
        try:
            # Fetch, for example, the 5 most recent assignments or those due soonest
            # For now, let's fetch a few assignments, ordered by due date
            assignments_response = supabase.table('assignments') \
                                       .select('id, title, due_date, lessons(title)') \
                                       .order('due_date', desc=True) \
                                       .limit(10) \
                                       .execute()

            if assignments_response and assignments_response.data:
                assignment_ids = [a['id'] for a in assignments_response.data]
                submissions_map = {}
                if assignment_ids:
                    submissions_response = supabase.table('submissions') \
                                               .select('assignment_id, id, status, grade, submitted_at') \
                                               .eq('student_id', student_id) \
                                               .in_('assignment_id', assignment_ids) \
                                               .execute()
                    if submissions_response and submissions_response.data:
                        submissions_map = {
                            sub['assignment_id']: {
                                'submission_id': sub['id'],
                                'status': sub.get('status', 'Submitted'),
                                'submitted_at': sub.get('submitted_at') # For "Completed at"
                            } for sub in submissions_response.data
                        }

                for assignment_item in assignments_response.data:
                    submission_info = submissions_map.get(assignment_item['id'])
                    item_status = 'Not Submitted'
                    url = url_for('student.view_assignment_student', assignment_id=assignment_item['id'])
                    completed_at_display = None

                    if submission_info:
                        item_status = submission_info.get('status', 'Submitted') # Default to 'Submitted' if status is missing

                        # Populate completed_at_display if there's a submission timestamp
                        if submission_info.get('submitted_at'):
                            try:
                                # Simplified date formatting for dashboard
                                submitted_dt_utc = datetime.fromisoformat(submission_info['submitted_at'].replace('Z', '+00:00'))
                                completed_at_display = submitted_dt_utc.strftime("%b %d, %Y")
                            except ValueError:
                                completed_at_display = "Date N/A"
                        
                        # Now, simplify status to 'Completed' for dashboard overview if applicable
                        if item_status in ['Graded by Teacher', 'Reviewed', 'Auto-Graded', 'Completed']: # Add 'Completed' if you use it
                            item_status = 'Completed' # Simplify for dashboard
                        # If item_status was, e.g., 'Submitted', it remains so here.

                        url = url_for('student.view_submission_details', submission_id=submission_info['submission_id'])
                    
                    due_date_display = None
                    is_past_due = False
                    if assignment_item.get('due_date'):
                        try:
                            due_dt = datetime.fromisoformat(assignment_item['due_date'])
                            due_date_display = due_dt.strftime("%b %d, %Y")
                            if datetime.now(timezone.utc) > due_dt and not submission_info:
                                is_past_due = True
                        except (ValueError, TypeError):
                            due_date_display = "Date N/A"

                    dashboard_assignments.append({
                        'id': assignment_item['id'],
                        'title': assignment_item['title'],
                        'due_date': due_date_display,
                        'completed_at': completed_at_display,
                        'status': item_status,
                        'url': url,
                        'is_past_due': is_past_due
                    })
            
            elif hasattr(assignments_response, 'error') and assignments_response.error:
                print(f"Dashboard assignments fetch error: {assignments_response.error.message}")

        except PostgrestAPIError as e:
            print(f"Supabase DB Error (Dashboard Assignments): {e}")
        except Exception as e:
            print(f"Error loading dashboard assignments: {e}")

    return render_template(
        'StudentDashboard.html',
        available_signs=available_signs,
        user_name=user_name,
        assignments=dashboard_assignments # Pass the new variable
    )
