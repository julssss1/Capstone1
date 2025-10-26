"""
Archive utility functions for moving records to archive tables instead of deleting them.
This preserves student records, assignments, subjects, and lessons as per educational compliance requirements.
"""
from flask import current_app, session
from supabase import Client
from datetime import datetime


def archive_user(user_id: str, archived_by: str, reason: str = "Manual archive") -> dict:
    """
    Archive a user profile to archived_profiles table.
    
    Args:
        user_id: UUID of the user to archive
        archived_by: UUID of the admin performing the archive
        reason: Reason for archiving
        
    Returns:
        dict with success status and message
    """
    try:
        supabase: Client = current_app.supabase
        
        # IMPORTANT: Fetch email FIRST before any deletion, as deleting from profiles
        # triggers deletion from auth.users too
        email = None
        try:
            # Query auth.users directly for the email while user still exists
            from supabase import create_client
            # Create a client with service role key to access auth.users
            service_supabase = create_client(
                current_app.config.get('SUPABASE_URL'),
                current_app.config.get('SUPABASE_SERVICE_KEY') or current_app.config.get('SUPABASE_ANON_KEY')
            )
            
            # Try to get email from auth admin API
            try:
                user = service_supabase.auth.admin.get_user_by_id(user_id)
                if user and user.user:
                    email = user.user.email
            except:
                pass
        except Exception as e:
            print(f"Could not fetch email for user {user_id}: {e}")
        
        # Fetch the user profile
        profile_response = supabase.table('profiles').select('*').eq('id', user_id).execute()
        
        if not profile_response.data:
            return {'success': False, 'message': 'User not found'}
        
        profile = profile_response.data[0]
        
        # Fallback: try to get email from profile if it exists there
        if not email:
            email = profile.get('email', None)
        
        # Insert into archived_profiles
        archive_data = {
            'id': profile['id'],
            'email': email,
            'role': profile.get('role'),
            'created_at': profile.get('created_at'),
            'first_name': profile.get('first_name'),
            'last_name': profile.get('last_name'),
            'middle_name': profile.get('middle_name'),
            'bio': profile.get('bio'),
            'grade_level': profile.get('grade_level'),
            'avatar_path': profile.get('avatar_path'),
            'archived_by': archived_by,
            'archive_reason': reason
        }
        
        archive_response = supabase.table('archived_profiles').insert(archive_data).execute()
        
        if archive_response.data:
            # Delete from profiles table
            supabase.table('profiles').delete().eq('id', user_id).execute()
            return {'success': True, 'message': 'User archived successfully'}
        else:
            return {'success': False, 'message': 'Failed to archive user'}
            
    except Exception as e:
        print(f"Error archiving user {user_id}: {e}")
        return {'success': False, 'message': str(e)}


def archive_subject(subject_id: int, archived_by: str, reason: str = "Manual archive") -> dict:
    """
    Archive a subject and all related data (lessons, assignments, submissions, enrollments).
    
    Args:
        subject_id: ID of the subject to archive
        archived_by: UUID of the admin performing the archive
        reason: Reason for archiving
        
    Returns:
        dict with success status and message
    """
    try:
        supabase: Client = current_app.supabase
        
        # Fetch the subject
        subject_response = supabase.table('subjects').select('*').eq('id', subject_id).execute()
        
        if not subject_response.data:
            return {'success': False, 'message': 'Subject not found'}
        
        subject = subject_response.data[0]
        
        # Get teacher name
        teacher_name = None
        if subject.get('teacher_id'):
            teacher_response = supabase.table('profiles').select('first_name, last_name').eq('id', subject['teacher_id']).execute()
            if teacher_response.data:
                teacher = teacher_response.data[0]
                teacher_name = f"{teacher.get('first_name', '')} {teacher.get('last_name', '')}".strip()
        
        # Archive all lessons for this subject
        lessons_response = supabase.table('lessons').select('*').eq('subject_id', subject_id).execute()
        for lesson in lessons_response.data:
            archive_lesson(lesson['id'], archived_by, f"Parent subject archived: {reason}")
        
        # Archive all assignments for this subject
        assignments_response = supabase.table('assignments').select('*').eq('subject_id', subject_id).execute()
        for assignment in assignments_response.data:
            archive_assignment(assignment['id'], archived_by, f"Parent subject archived: {reason}")
        
        # Archive all enrollments for this subject
        enrollments_response = supabase.table('enrollments').select('*').eq('subject_id', subject_id).execute()
        for enrollment in enrollments_response.data:
            archive_enrollment(enrollment['id'], archived_by, f"Parent subject archived: {reason}")
        
        # Archive the subject
        archive_data = {
            'original_id': subject['id'],
            'name': subject.get('name'),
            'description': subject.get('description'),
            'teacher_id': subject.get('teacher_id'),
            'teacher_name': teacher_name,
            'created_at': subject.get('created_at'),
            'archived_by': archived_by,
            'archive_reason': reason
        }
        
        archive_response = supabase.table('archived_subjects').insert(archive_data).execute()
        
        if archive_response.data:
            # Delete from subjects table
            supabase.table('subjects').delete().eq('id', subject_id).execute()
            return {'success': True, 'message': 'Subject and all related data archived successfully'}
        else:
            return {'success': False, 'message': 'Failed to archive subject'}
            
    except Exception as e:
        print(f"Error archiving subject {subject_id}: {e}")
        return {'success': False, 'message': str(e)}


def archive_lesson(lesson_id: int, archived_by: str, reason: str = "Manual archive") -> dict:
    """
    Archive a lesson and its related assignments and submissions.
    
    Args:
        lesson_id: ID of the lesson to archive
        archived_by: UUID of the admin performing the archive
        reason: Reason for archiving
        
    Returns:
        dict with success status and message
    """
    try:
        supabase: Client = current_app.supabase
        
        # Fetch the lesson
        lesson_response = supabase.table('lessons').select('*').eq('id', lesson_id).execute()
        
        if not lesson_response.data:
            return {'success': False, 'message': 'Lesson not found'}
        
        lesson = lesson_response.data[0]
        
        # Get subject name
        subject_name = None
        if lesson.get('subject_id'):
            subject_response = supabase.table('subjects').select('name').eq('id', lesson['subject_id']).execute()
            if subject_response.data:
                subject_name = subject_response.data[0].get('name')
        
        # Archive all assignments for this lesson
        assignments_response = supabase.table('assignments').select('*').eq('lesson_id', lesson_id).execute()
        for assignment in assignments_response.data:
            archive_assignment(assignment['id'], archived_by, f"Parent lesson archived: {reason}")
        
        # Archive the lesson
        archive_data = {
            'original_id': lesson['id'],
            'subject_id': lesson.get('subject_id'),
            'subject_name': subject_name,
            'title': lesson.get('title'),
            'description': lesson.get('description'),
            'content': lesson.get('content'),
            'created_by': lesson.get('created_by'),
            'created_at': lesson.get('created_at'),
            'updated_at': lesson.get('updated_at'),
            'archived_by': archived_by,
            'archive_reason': reason
        }
        
        archive_response = supabase.table('archived_lessons').insert(archive_data).execute()
        
        if archive_response.data:
            # Delete from lessons table
            supabase.table('lessons').delete().eq('id', lesson_id).execute()
            return {'success': True, 'message': 'Lesson archived successfully'}
        else:
            return {'success': False, 'message': 'Failed to archive lesson'}
            
    except Exception as e:
        print(f"Error archiving lesson {lesson_id}: {e}")
        return {'success': False, 'message': str(e)}


def archive_assignment(assignment_id: int, archived_by: str, reason: str = "Manual archive") -> dict:
    """
    Archive an assignment and all its submissions and sign attempts.
    
    Args:
        assignment_id: ID of the assignment to archive
        archived_by: UUID of the admin/teacher performing the archive
        reason: Reason for archiving
        
    Returns:
        dict with success status and message
    """
    try:
        supabase: Client = current_app.supabase
        
        # Fetch the assignment
        assignment_response = supabase.table('assignments').select('*').eq('id', assignment_id).execute()
        
        if not assignment_response.data:
            return {'success': False, 'message': 'Assignment not found'}
        
        assignment = assignment_response.data[0]
        
        # Get subject name
        subject_name = None
        if assignment.get('subject_id'):
            subject_response = supabase.table('subjects').select('name').eq('id', assignment['subject_id']).execute()
            if subject_response.data:
                subject_name = subject_response.data[0].get('name')
        
        # Get lesson title
        lesson_title = None
        if assignment.get('lesson_id'):
            lesson_response = supabase.table('lessons').select('title').eq('id', assignment['lesson_id']).execute()
            if lesson_response.data:
                lesson_title = lesson_response.data[0].get('title')
        
        # Archive all submissions for this assignment
        submissions_response = supabase.table('submissions').select('*').eq('assignment_id', assignment_id).execute()
        for submission in submissions_response.data:
            archive_submission(submission['id'], archived_by, f"Parent assignment archived: {reason}")
        
        # Archive all sign attempts related to this assignment
        sign_attempts_response = supabase.table('sign_attempts').select('*').eq('related_assignment_id', assignment_id).execute()
        for attempt in sign_attempts_response.data:
            archive_sign_attempt(attempt['id'], archived_by, f"Parent assignment archived: {reason}")
        
        # Archive the assignment
        archive_data = {
            'original_id': assignment['id'],
            'subject_id': assignment.get('subject_id'),
            'subject_name': subject_name,
            'lesson_id': assignment.get('lesson_id'),
            'lesson_title': lesson_title,
            'title': assignment.get('title'),
            'description': assignment.get('description'),
            'due_date': assignment.get('due_date'),
            'correct_answers': assignment.get('correct_answers'),
            'created_at': assignment.get('created_at'),
            'archived_by': archived_by,
            'archive_reason': reason
        }
        
        archive_response = supabase.table('archived_assignments').insert(archive_data).execute()
        
        if archive_response.data:
            # Delete from assignments table
            supabase.table('assignments').delete().eq('id', assignment_id).execute()
            return {'success': True, 'message': 'Assignment archived successfully'}
        else:
            return {'success': False, 'message': 'Failed to archive assignment'}
            
    except Exception as e:
        print(f"Error archiving assignment {assignment_id}: {e}")
        return {'success': False, 'message': str(e)}


def archive_submission(submission_id: int, archived_by: str, reason: str = "Manual archive") -> dict:
    """
    Archive a submission and its related sign attempts.
    
    Args:
        submission_id: ID of the submission to archive
        archived_by: UUID of the admin/teacher performing the archive
        reason: Reason for archiving
        
    Returns:
        dict with success status and message
    """
    try:
        supabase: Client = current_app.supabase
        
        # Fetch the submission
        submission_response = supabase.table('submissions').select('*').eq('id', submission_id).execute()
        
        if not submission_response.data:
            return {'success': False, 'message': 'Submission not found'}
        
        submission = submission_response.data[0]
        
        # Get assignment title
        assignment_title = None
        if submission.get('assignment_id'):
            assignment_response = supabase.table('assignments').select('title').eq('id', submission['assignment_id']).execute()
            if assignment_response.data:
                assignment_title = assignment_response.data[0].get('title')
        
        # Get student name
        student_name = None
        if submission.get('student_id'):
            student_response = supabase.table('profiles').select('first_name, last_name').eq('id', submission['student_id']).execute()
            if student_response.data:
                student = student_response.data[0]
                student_name = f"{student.get('first_name', '')} {student.get('last_name', '')}".strip()
        
        # Archive all sign attempts for this submission
        sign_attempts_response = supabase.table('sign_attempts').select('*').eq('submission_id', submission_id).execute()
        for attempt in sign_attempts_response.data:
            archive_sign_attempt(attempt['id'], archived_by, f"Parent submission archived: {reason}")
        
        # Archive the submission
        archive_data = {
            'original_id': submission['id'],
            'assignment_id': submission.get('assignment_id'),
            'assignment_title': assignment_title,
            'student_id': submission.get('student_id'),
            'student_name': student_name,
            'submission_content': submission.get('submission_content'),
            'submitted_at': submission.get('submitted_at'),
            'grade': submission.get('grade'),
            'feedback': submission.get('feedback'),
            'average_confidence': submission.get('average_confidence'),
            'status': submission.get('status'),
            'archived_by': archived_by,
            'archive_reason': reason
        }
        
        archive_response = supabase.table('archived_submissions').insert(archive_data).execute()
        
        if archive_response.data:
            # Delete from submissions table
            supabase.table('submissions').delete().eq('id', submission_id).execute()
            return {'success': True, 'message': 'Submission archived successfully'}
        else:
            return {'success': False, 'message': 'Failed to archive submission'}
            
    except Exception as e:
        print(f"Error archiving submission {submission_id}: {e}")
        return {'success': False, 'message': str(e)}


def archive_enrollment(enrollment_id: int, archived_by: str, reason: str = "Manual archive") -> dict:
    """
    Archive an enrollment record.
    
    Args:
        enrollment_id: ID of the enrollment to archive
        archived_by: UUID of the admin performing the archive
        reason: Reason for archiving
        
    Returns:
        dict with success status and message
    """
    try:
        supabase: Client = current_app.supabase
        
        # Fetch the enrollment
        enrollment_response = supabase.table('enrollments').select('*').eq('id', enrollment_id).execute()
        
        if not enrollment_response.data:
            return {'success': False, 'message': 'Enrollment not found'}
        
        enrollment = enrollment_response.data[0]
        
        # Get student name
        student_name = None
        if enrollment.get('student_id'):
            student_response = supabase.table('profiles').select('first_name, last_name').eq('id', enrollment['student_id']).execute()
            if student_response.data:
                student = student_response.data[0]
                student_name = f"{student.get('first_name', '')} {student.get('last_name', '')}".strip()
        
        # Get teacher name
        teacher_name = None
        if enrollment.get('teacher_id'):
            teacher_response = supabase.table('profiles').select('first_name, last_name').eq('id', enrollment['teacher_id']).execute()
            if teacher_response.data:
                teacher = teacher_response.data[0]
                teacher_name = f"{teacher.get('first_name', '')} {teacher.get('last_name', '')}".strip()
        
        # Get subject name
        subject_name = None
        if enrollment.get('subject_id'):
            subject_response = supabase.table('subjects').select('name').eq('id', enrollment['subject_id']).execute()
            if subject_response.data:
                subject_name = subject_response.data[0].get('name')
        
        # Archive the enrollment
        archive_data = {
            'original_id': enrollment['id'],
            'student_id': enrollment.get('student_id'),
            'student_name': student_name,
            'teacher_id': enrollment.get('teacher_id'),
            'teacher_name': teacher_name,
            'subject_id': enrollment.get('subject_id'),
            'subject_name': subject_name,
            'enrolled_at': enrollment.get('enrolled_at'),
            'created_by': enrollment.get('created_by'),
            'status': enrollment.get('status'),
            'archived_by': archived_by,
            'archive_reason': reason
        }
        
        archive_response = supabase.table('archived_enrollments').insert(archive_data).execute()
        
        if archive_response.data:
            # Delete from enrollments table
            supabase.table('enrollments').delete().eq('id', enrollment_id).execute()
            return {'success': True, 'message': 'Enrollment archived successfully'}
        else:
            return {'success': False, 'message': 'Failed to archive enrollment'}
            
    except Exception as e:
        print(f"Error archiving enrollment {enrollment_id}: {e}")
        return {'success': False, 'message': str(e)}


def archive_sign_attempt(attempt_id: int, archived_by: str, reason: str = "Manual archive") -> dict:
    """
    Archive a sign attempt record.
    
    Args:
        attempt_id: ID of the sign attempt to archive
        archived_by: UUID of the admin/teacher performing the archive
        reason: Reason for archiving
        
    Returns:
        dict with success status and message
    """
    try:
        supabase: Client = current_app.supabase
        
        # Fetch the sign attempt
        attempt_response = supabase.table('sign_attempts').select('*').eq('id', attempt_id).execute()
        
        if not attempt_response.data:
            return {'success': False, 'message': 'Sign attempt not found'}
        
        attempt = attempt_response.data[0]
        
        # Get student name
        student_name = None
        if attempt.get('student_id'):
            student_response = supabase.table('profiles').select('first_name, last_name').eq('id', attempt['student_id']).execute()
            if student_response.data:
                student = student_response.data[0]
                student_name = f"{student.get('first_name', '')} {student.get('last_name', '')}".strip()
        
        # Archive the sign attempt
        archive_data = {
            'original_id': attempt['id'],
            'student_id': attempt.get('student_id'),
            'student_name': student_name,
            'sign_recognized': attempt.get('sign_recognized'),
            'confidence_score': attempt.get('confidence_score'),
            'timestamp': attempt.get('timestamp'),
            'related_assignment_id': attempt.get('related_assignment_id'),
            'submission_id': attempt.get('submission_id'),
            'archived_by': archived_by,
            'archive_reason': reason
        }
        
        archive_response = supabase.table('archived_sign_attempts').insert(archive_data).execute()
        
        if archive_response.data:
            # Delete from sign_attempts table
            supabase.table('sign_attempts').delete().eq('id', attempt_id).execute()
            return {'success': True, 'message': 'Sign attempt archived successfully'}
        else:
            return {'success': False, 'message': 'Failed to archive sign attempt'}
            
    except Exception as e:
        print(f"Error archiving sign attempt {attempt_id}: {e}")
        return {'success': False, 'message': str(e)}


def unarchive_user(archive_id: str, restored_by: str) -> dict:
    """
    Users cannot be automatically restored due to auth.users foreign key constraint.
    The admin must create a new user account manually through the user management interface.
    This function returns an error message explaining the process.
    
    Args:
        archive_id: UUID of the archived user (the id field, not an auto-increment)
        restored_by: UUID of the admin performing the restore
        
    Returns:
        dict with success status and message
    """
    try:
        supabase: Client = current_app.supabase
        
        # Fetch the archived profile to show user info
        archive_response = supabase.table('archived_profiles').select('*').eq('id', archive_id).execute()
        
        if not archive_response.data:
            return {'success': False, 'message': 'Archived user not found'}
        
        archived_profile = archive_response.data[0]
        first_name = archived_profile.get('first_name', '')
        last_name = archived_profile.get('last_name', '')
        role = archived_profile.get('role', 'Unknown')
        
        # Cannot restore users automatically due to auth.users foreign key constraint
        return {
            'success': False, 
            'message': f'User restoration not supported: {first_name} {last_name} ({role}). To restore this user, please create a new user account manually in User Management with the same details. The archived profile will remain in archives for reference.'
        }
            
    except Exception as e:
        print(f"Error checking archived user {archive_id}: {e}")
        return {'success': False, 'message': str(e)}


def unarchive_subject(archive_id: int, restored_by: str) -> dict:
    """
    Restore a subject from archived_subjects back to subjects table.
    
    Args:
        archive_id: ID of the archived record
        restored_by: UUID of the admin performing the restore
        
    Returns:
        dict with success status and message
    """
    try:
        supabase: Client = current_app.supabase
        
        # Fetch the archived subject
        archive_response = supabase.table('archived_subjects').select('*').eq('id', archive_id).execute()
        
        if not archive_response.data:
            return {'success': False, 'message': 'Archived subject not found'}
        
        archived_subject = archive_response.data[0]
        
        # Restore the subject (without id since it will auto-generate)
        restore_data = {
            'name': archived_subject.get('name'),
            'description': archived_subject.get('description'),
            'teacher_id': archived_subject.get('teacher_id'),
        }
        
        restore_response = supabase.table('subjects').insert(restore_data).execute()
        
        if restore_response.data:
            new_subject_id = restore_response.data[0]['id']
            
            # Delete from archive
            supabase.table('archived_subjects').delete().eq('id', archive_id).execute()
            
            return {'success': True, 'message': f'Subject restored successfully with new ID: {new_subject_id}'}
        else:
            return {'success': False, 'message': 'Failed to restore subject'}
            
    except Exception as e:
        print(f"Error unarchiving subject {archive_id}: {e}")
        return {'success': False, 'message': str(e)}


def unarchive_lesson(archive_id: int, restored_by: str) -> dict:
    """
    Restore a lesson from archived_lessons back to lessons table.
    Requires the parent subject to exist. If the original subject was archived and restored,
    it will have a new ID - the admin must manually reassign lessons to the new subject.
    
    Args:
        archive_id: ID of the archived record
        restored_by: UUID of the admin performing the restore
        
    Returns:
        dict with success status and message
    """
    try:
        supabase: Client = current_app.supabase
        
        # Fetch the archived lesson
        archive_response = supabase.table('archived_lessons').select('*').eq('id', archive_id).execute()
        
        if not archive_response.data:
            return {'success': False, 'message': 'Archived lesson not found'}
        
        archived_lesson = archive_response.data[0]
        original_subject_name = archived_lesson.get('subject_name', 'Unknown')
        
        # Check if parent subject exists
        subject_id = archived_lesson.get('subject_id')
        
        if not subject_id:
            return {
                'success': False, 
                'message': f'Cannot restore lesson: No parent subject information. This lesson was from "{original_subject_name}". Please restore or create the parent subject first.'
            }
        
        subject_check = supabase.table('subjects').select('id', 'name').eq('id', subject_id).execute()
        
        if not subject_check.data:
            # Original subject no longer exists - check if there's a subject with the same name
            subject_by_name = supabase.table('subjects').select('id', 'name').eq('name', original_subject_name).execute()
            
            if subject_by_name.data:
                # Found a subject with the same name - use it automatically
                suggested_subject = subject_by_name.data[0]
                subject_id = suggested_subject['id']
                subject_warning = f' Note: Original subject (ID {archived_lesson.get("subject_id")}) no longer exists, but a subject with the same name "{original_subject_name}" was found (ID {subject_id}). The lesson has been restored to this subject.'
            else:
                return {
                    'success': False,
                    'message': f'Cannot restore lesson: Original subject "{original_subject_name}" (ID {subject_id}) no longer exists. Please restore or create the parent subject first, then try restoring this lesson.'
                }
        else:
            subject_warning = ''
        
        # Subject exists (or we found one with the same name), restore the lesson
        restore_data = {
            'subject_id': subject_id,
            'title': archived_lesson.get('title'),
            'description': archived_lesson.get('description'),
            'content': archived_lesson.get('content'),
            'created_by': archived_lesson.get('created_by'),
        }
        
        restore_response = supabase.table('lessons').insert(restore_data).execute()
        
        if restore_response.data:
            new_lesson_id = restore_response.data[0]['id']
            
            # Delete from archive
            supabase.table('archived_lessons').delete().eq('id', archive_id).execute()
            
            return {'success': True, 'message': f'Lesson restored successfully with new ID: {new_lesson_id}.{subject_warning}'}
        else:
            return {'success': False, 'message': 'Failed to restore lesson'}
            
    except Exception as e:
        print(f"Error unarchiving lesson {archive_id}: {e}")
        return {'success': False, 'message': str(e)}


def unarchive_assignment(archive_id: int, restored_by: str) -> dict:
    """
    Restore an assignment from archived_assignments back to assignments table.
    Automatically reconnects to parent subject by name if original subject was restored with new ID.
    
    Args:
        archive_id: ID of the archived record
        restored_by: UUID of the admin performing the restore
        
    Returns:
        dict with success status and message
    """
    try:
        supabase: Client = current_app.supabase
        
        # Fetch the archived assignment
        archive_response = supabase.table('archived_assignments').select('*').eq('id', archive_id).execute()
        
        if not archive_response.data:
            return {'success': False, 'message': 'Archived assignment not found'}
        
        archived_assignment = archive_response.data[0]
        original_subject_name = archived_assignment.get('subject_name', 'Unknown')
        subject_id = archived_assignment.get('subject_id')
        lesson_id = archived_assignment.get('lesson_id')
        warning_messages = []
        
        # Check if parent subject exists
        if subject_id:
            subject_check = supabase.table('subjects').select('id', 'name').eq('id', subject_id).execute()
            
            if not subject_check.data:
                # Original subject no longer exists - check if there's a subject with the same name
                subject_by_name = supabase.table('subjects').select('id', 'name').eq('name', original_subject_name).execute()
                
                if subject_by_name.data:
                    # Found a subject with the same name - use it automatically
                    suggested_subject = subject_by_name.data[0]
                    old_subject_id = subject_id
                    subject_id = suggested_subject['id']
                    warning_messages.append(f'Original subject (ID {old_subject_id}) no longer exists, reconnected to subject "{original_subject_name}" (ID {subject_id})')
                else:
                    return {
                        'success': False,
                        'message': f'Cannot restore assignment: Original subject "{original_subject_name}" (ID {subject_id}) no longer exists. Please restore or create the parent subject first.'
                    }
        
        # Check if lesson exists (lessons are optional for assignments)
        if lesson_id:
            lesson_check = supabase.table('lessons').select('id').eq('id', lesson_id).execute()
            if not lesson_check.data:
                # Lesson doesn't exist - this is OK, we'll restore without it
                old_lesson_id = lesson_id
                lesson_id = None
                warning_messages.append(f'Original lesson (ID {old_lesson_id}) no longer exists, assignment restored without lesson assignment')
        
        # Restore the assignment
        restore_data = {
            'subject_id': subject_id,
            'lesson_id': lesson_id,
            'title': archived_assignment.get('title'),
            'description': archived_assignment.get('description'),
            'due_date': archived_assignment.get('due_date'),
            'correct_answers': archived_assignment.get('correct_answers'),
        }
        
        restore_response = supabase.table('assignments').insert(restore_data).execute()
        
        if restore_response.data:
            new_assignment_id = restore_response.data[0]['id']
            
            # Delete from archive
            supabase.table('archived_assignments').delete().eq('id', archive_id).execute()
            
            message = f'Assignment restored successfully with new ID: {new_assignment_id}'
            if warning_messages:
                message += '. Note: ' + '; '.join(warning_messages)
            
            return {'success': True, 'message': message}
        else:
            return {'success': False, 'message': 'Failed to restore assignment'}
            
    except Exception as e:
        print(f"Error unarchiving assignment {archive_id}: {e}")
        return {'success': False, 'message': str(e)}
