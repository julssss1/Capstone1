from flask import render_template, session, url_for, flash, redirect, current_app
from . import bp  # Use . to import bp from the current package (student)
from app.utils import login_required, role_required
from supabase import Client, PostgrestAPIError

@bp.route('/my_progress')
@login_required
@role_required('Student')
def student_progress():
    user_name = session.get('user_name', 'Student')
    supabase: Client = current_app.supabase
    all_subjects = []
    if not supabase:
        flash('Database connection not available.', 'danger')
        return render_template('StudentProgress.html', title='My Progress', user_name=user_name, all_subjects=all_subjects) 
    
    try:
        print("Attempting to fetch all subjects for progress page...")
        subjects_response = supabase.table('subjects').select('id, name, description').order('name').execute()
        
        if subjects_response and subjects_response.data:
            all_subjects = subjects_response.data
        elif hasattr(subjects_response, 'error') and subjects_response.error:
            flash(f"Error fetching subjects for progress: {subjects_response.error.message}", "warning")
            print(f"Error fetching subjects for progress page: {subjects_response.error}")
            
    except Exception as e:
        flash(f"Error loading subjects: {e}", "warning")
        print(f"Error in student_progress fetching subjects: {e}")
            
    return render_template('StudentProgress.html', title='My Progress', user_name=user_name, all_subjects=all_subjects)

@bp.route('/subject/<int:subject_id>/lessons')
@login_required
@role_required('Student')
def view_subject_lessons(subject_id):
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Student')
    student_id = session.get('user_id') 
    subject = None
    lessons_with_assignment_status = []

    if not student_id:
        flash("User session not found.", "danger")
        return redirect(url_for('auth.login'))
    if not supabase:
        flash('Database connection not available.', 'danger')
        return render_template('StudentLessons.html', subject=subject, lessons=lessons_with_assignment_status, user_name=user_name, subject_name="Lessons")

    try:
        subject_res = supabase.table('subjects').select('*').eq('id', subject_id).maybe_single().execute()
        if not (subject_res and subject_res.data): 
            flash('Subject not found.', 'warning'); return redirect(url_for('student.student_progress'))
        subject = subject_res.data
        
        lessons_res = supabase.table('lessons').select('*, assignments(*)').eq('subject_id', subject_id).order('id').execute()
        
        if lessons_res and lessons_res.data:
            for lesson in lessons_res.data:
                if lesson.get('assignments'):
                    assignment_ids_for_lesson = [asn['id'] for asn in lesson['assignments']]
                    if assignment_ids_for_lesson:
                        submissions_res = supabase.table('submissions') \
                            .select('assignment_id, id') \
                            .eq('student_id', student_id) \
                            .in_('assignment_id', assignment_ids_for_lesson) \
                            .execute()
                        
                        submissions_map = {}
                        if submissions_res and submissions_res.data:
                            submissions_map = {sub['assignment_id']: sub['id'] for sub in submissions_res.data}

                        for asn in lesson['assignments']:
                            asn['student_submission_id'] = submissions_map.get(asn['id'])
                lessons_with_assignment_status.append(lesson)
        
    except Exception as e:
        flash(f"Error loading lessons: {e}", 'danger')
        print(f"Error in view_subject_lessons: {e}")
        
    return render_template('StudentLessons.html', subject=subject, lessons=lessons_with_assignment_status, user_name=user_name, subject_name=subject.get('name') if subject else "Lessons")

@bp.route('/lesson/<int:lesson_id>/content')
@login_required
@role_required('Student')
def view_lesson_content(lesson_id):
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Student')
    lesson = None
    try:
        lesson_res = supabase.table('lessons').select('*, subjects(name)').eq('id', lesson_id).maybe_single().execute()
        if not (lesson_res and lesson_res.data): 
            flash('Lesson not found.', 'warning'); return redirect(url_for('student.student_progress'))
        lesson = lesson_res.data
    except Exception as e:
        flash(f"Error loading lesson content: {e}", 'danger')
        print(f"Error in view_lesson_content: {e}")
    subject_name_from_join = lesson.get('subjects', {}).get('name') if lesson and lesson.get('subjects') else "Lesson"
    subject_id = lesson.get('subject_id') if lesson else None
    return render_template('StudentLessonView.html', lesson_data=lesson, user_name=user_name, subject_name=subject_name_from_join, subject_id=subject_id)

@bp.route('/lesson/<int:lesson_id>/videos')
@login_required
@role_required('Student')
def lesson_video_materials(lesson_id):
    """Display video materials for a specific lesson"""
    supabase: Client = current_app.supabase
    user_name = session.get('user_name', 'Student')
    video_materials = []
    lesson_title = "Lesson Videos"
    subject_name = ""
    
    if not supabase:
        flash('Database connection not available.', 'danger')
        return render_template('StudentVideoMaterials.html', user_name=user_name, video_materials=video_materials, lesson_title=lesson_title, subject_name=subject_name)
    
    try:
        # Fetch the specific lesson with its subject
        lesson_res = supabase.table('lessons').select('id, title, description, content, subject_id, subjects(name)').eq('id', lesson_id).maybe_single().execute()
        
        if not (lesson_res and lesson_res.data):
            flash('Lesson not found.', 'warning')
            return redirect(url_for('student.student_progress'))
        
        lesson = lesson_res.data
        lesson_title = lesson.get('title', 'Untitled Lesson')
        subject_name = lesson.get('subjects', {}).get('name', 'Unknown Subject')
        subject_id = lesson.get('subject_id')
        
        if lesson.get('content') and isinstance(lesson['content'], list):
            # Extract only items that have video_url
            for item in lesson['content']:
                if item.get('video_url'):
                    video_materials.append({
                        'item_name': item.get('name', 'Unnamed Video'),
                        'description': item.get('description', ''),
                        'video_url': item['video_url'],
                        'image_url': item.get('image_url') or item.get('media_url')  # Optional thumbnail
                    })
        
    except Exception as e:
        flash(f"Error loading video materials: {e}", 'danger')
        print(f"Error in lesson_video_materials route: {e}")
    
    return render_template('StudentVideoMaterials.html', user_name=user_name, video_materials=video_materials, lesson_title=lesson_title, subject_name=subject_name, subject_id=subject_id)
