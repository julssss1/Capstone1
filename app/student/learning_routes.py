from flask import render_template, session, url_for, flash, redirect, current_app, request, jsonify
from . import bp  # Use . to import bp from the current package (student)
from app.utils import login_required, role_required
from supabase import Client, PostgrestAPIError

@bp.route('/my_progress')
@login_required
@role_required('Student')
def student_progress():
    user_name = session.get('user_name', 'Student')
    student_id = session.get('user_id')
    supabase: Client = current_app.supabase
    all_subjects = []
    
    if not student_id:
        flash('User session invalid. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))
    
    if not supabase:
        flash('Database connection not available.', 'danger')
        return render_template('StudentProgress.html', title='My Progress', user_name=user_name, all_subjects=all_subjects) 
    
    try:
        print(f"Fetching subjects for student {student_id} based on enrollments...")
        
        # Get subjects this student is enrolled in (subject-based enrollment)
        enrollments_response = supabase.table('enrollments') \
            .select('subject_id, subjects(id, name, description, teacher_id)') \
            .eq('student_id', student_id) \
            .eq('status', 'active') \
            .execute()
        
        if enrollments_response and enrollments_response.data:
            # Extract subjects from enrollments
            for enrollment in enrollments_response.data:
                subject_data = enrollment.get('subjects')
                if subject_data:
                    # Calculate overall progress for this subject
                    subject_progress = _calculate_subject_progress(student_id, subject_data['id'], supabase)
                    subject_data['overall_progress'] = subject_progress['percentage']
                    subject_data['completed_lessons'] = subject_progress['completed_lessons']
                    subject_data['total_lessons'] = subject_progress['total_lessons']
                    all_subjects.append(subject_data)
            
            if all_subjects:
                print(f"Found {len(all_subjects)} enrolled subjects for student")
            else:
                print("No subjects found in enrollments")
        else:
            # No enrollments found - student is not enrolled in any subjects
            print(f"No active enrollments found for student {student_id}")
            flash("You are not enrolled in any subjects yet. Please contact your administrator.", "info")
            
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
                # Calculate progress for this lesson
                progress_data = _calculate_lesson_progress(student_id, lesson['id'], supabase)
                lesson['progress_percentage'] = progress_data['percentage']
                lesson['completed_items'] = progress_data['completed_items']
                lesson['total_items'] = progress_data['total_items']
                lesson['viewed_items'] = progress_data['viewed_items']
                
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

@bp.route('/lesson/<int:lesson_id>/record-progress', methods=['POST'])
@login_required
@role_required('Student')
def record_lesson_progress(lesson_id):
    """Records student progress for a lesson content item"""
    supabase: Client = current_app.supabase
    student_id = session.get('user_id')
    
    if not student_id or not supabase:
        return jsonify({'success': False, 'error': 'Invalid session or database connection'}), 400
    
    data = request.get_json()
    content_index = data.get('content_index')
    progress_type = data.get('progress_type', 'page_view')
    
    try:
        # Insert progress record (will be ignored if duplicate due to UNIQUE constraint)
        supabase.table('lesson_progress').insert({
            'student_id': student_id,
            'lesson_id': lesson_id,
            'content_item_index': content_index,
            'progress_type': progress_type
        }).execute()
        
        # Calculate updated progress
        progress_data = _calculate_lesson_progress(student_id, lesson_id, supabase)
        
        return jsonify({
            'success': True,
            'progress_percentage': progress_data['percentage'],
            'completed_items': progress_data['completed_items'],
            'total_items': progress_data['total_items']
        })
        
    except Exception as e:
        print(f"Error recording progress: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/lesson/<int:lesson_id>/progress', methods=['GET'])
@login_required
@role_required('Student')
def get_lesson_progress(lesson_id):
    """Gets current progress for a lesson"""
    supabase: Client = current_app.supabase
    student_id = session.get('user_id')
    
    if not student_id or not supabase:
        return jsonify({'success': False, 'error': 'Invalid session or database connection'}), 400
    
    try:
        progress_data = _calculate_lesson_progress(student_id, lesson_id, supabase)
        return jsonify({
            'success': True,
            **progress_data
        })
    except Exception as e:
        print(f"Error getting progress: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def _calculate_lesson_progress(student_id, lesson_id, supabase):
    """Helper function to calculate lesson progress percentage"""
    try:
        # Get lesson content structure
        lesson_res = supabase.table('lessons').select('content').eq('id', lesson_id).maybe_single().execute()
        if not lesson_res or not lesson_res.data:
            return {'percentage': 0, 'completed_items': 0, 'total_items': 0, 'viewed_items': []}
        
        lesson_content = lesson_res.data.get('content', [])
        
        # Count total trackable items - simplified counting
        total_items = 1  # Lesson overview only
        
        # Check if there are any videos (counts as 1 item total, not per video)
        has_videos = False
        if lesson_content and isinstance(lesson_content, list):
            for item in lesson_content:
                if item.get('video_url'):
                    has_videos = True
                    break
        
        if has_videos:
            total_items += 1  # Video materials (all videos count as 1 item)
        
        # Count assignments for this lesson
        assignments_res = supabase.table('assignments').select('id', count='exact').eq('lesson_id', lesson_id).execute()
        assignment_count = assignments_res.count if assignments_res else 0
        total_items += assignment_count
        
        # Get completed progress items
        progress_res = supabase.table('lesson_progress') \
            .select('content_item_index, progress_type') \
            .eq('student_id', student_id) \
            .eq('lesson_id', lesson_id) \
            .execute()
        
        completed_items = 0
        viewed_items = []
        overview_viewed = False
        video_viewed = False
        
        if progress_res and progress_res.data:
            for item in progress_res.data:
                viewed_items.append({
                    'index': item['content_item_index'],
                    'type': item['progress_type']
                })
                
                # Count overview view (index -1)
                if item['content_item_index'] == -1 and item['progress_type'] == 'page_view':
                    if not overview_viewed:
                        completed_items += 1
                        overview_viewed = True
                
                # Count video view (index 0 for simplified video materials)
                elif item['content_item_index'] == 0 and item['progress_type'] == 'page_view' and has_videos:
                    if not video_viewed:
                        completed_items += 1
                        video_viewed = True
        
        # Count unique assignments completed (check submissions instead of progress records)
        if assignment_count > 0:
            # Get assignment IDs for this lesson
            lesson_assignments_res = supabase.table('assignments').select('id').eq('lesson_id', lesson_id).execute()
            if lesson_assignments_res and lesson_assignments_res.data:
                assignment_ids = [a['id'] for a in lesson_assignments_res.data]
                
                # Check which assignments have submissions
                submissions_res = supabase.table('submissions') \
                    .select('assignment_id') \
                    .eq('student_id', student_id) \
                    .in_('assignment_id', assignment_ids) \
                    .execute()
                
                if submissions_res and submissions_res.data:
                    # Count unique assignments that have been submitted
                    unique_assignments_completed = len(submissions_res.data)
                    completed_items += unique_assignments_completed
        
        # Calculate percentage
        percentage = round((completed_items / total_items * 100)) if total_items > 0 else 0
        
        return {
            'percentage': percentage,
            'completed_items': completed_items,
            'total_items': total_items,
            'viewed_items': viewed_items
        }
        
    except Exception as e:
        print(f"Error calculating progress: {e}")
        return {'percentage': 0, 'completed_items': 0, 'total_items': 0, 'viewed_items': []}

def _calculate_subject_progress(student_id, subject_id, supabase):
    """Calculate overall progress for a subject by averaging all lesson progress"""
    try:
        # Get all lessons for this subject
        lessons_res = supabase.table('lessons').select('id').eq('subject_id', subject_id).execute()
        
        if not lessons_res or not lessons_res.data:
            return {'percentage': 0, 'completed_lessons': 0, 'total_lessons': 0}
        
        lessons = lessons_res.data
        total_lessons = len(lessons)
        
        if total_lessons == 0:
            return {'percentage': 0, 'completed_lessons': 0, 'total_lessons': 0}
        
        # Calculate progress for each lesson and average them
        total_progress = 0
        completed_lessons = 0
        
        for lesson in lessons:
            lesson_progress = _calculate_lesson_progress(student_id, lesson['id'], supabase)
            total_progress += lesson_progress['percentage']
            
            # Consider a lesson "completed" if it's 100%
            if lesson_progress['percentage'] == 100:
                completed_lessons += 1
        
        # Average progress across all lessons
        average_progress = round(total_progress / total_lessons) if total_lessons > 0 else 0
        
        return {
            'percentage': average_progress,
            'completed_lessons': completed_lessons,
            'total_lessons': total_lessons
        }
        
    except Exception as e:
        print(f"Error calculating subject progress: {e}")
        return {'percentage': 0, 'completed_lessons': 0, 'total_lessons': 0}
