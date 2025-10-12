document.addEventListener('DOMContentLoaded', function() {
    const subjectSelect = document.getElementById('assignment-subject');
    const lessonGroup = document.getElementById('lesson-group');
    const lessonSelect = document.getElementById('assignment-lesson');
    const dueDateInput = document.getElementById('assignment-due-date');
    const createAssignmentUrl = subjectSelect ? subjectSelect.dataset.createAssignmentUrl : null; // Get URL from data attribute

    // Set minimum date to today to prevent selecting past dates
    if (dueDateInput) {
        const today = new Date().toISOString().split('T')[0];
        dueDateInput.setAttribute('min', today);
    }

    // Data passed via data attributes on the lessonSelect element
    let lessonsForCurrentlySelectedSubject = [];
    if (lessonSelect && lessonSelect.dataset.lessons) {
        try {
            lessonsForCurrentlySelectedSubject = JSON.parse(lessonSelect.dataset.lessons);
        } catch (e) {
            console.error("Error parsing lessons data:", e);
            lessonsForCurrentlySelectedSubject = [];
        }
    }

    let preSelectedLessonId = null;
    if (lessonSelect && lessonSelect.dataset.preSelectedLessonId) {
        preSelectedLessonId = lessonSelect.dataset.preSelectedLessonId; // Keep as string for comparison with option.value
    }

    function populateLessonDropdown(lessons, lessonToSelect) {
        lessonSelect.innerHTML = ''; // Clear existing options
        
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = 'Select Lesson';
        lessonSelect.appendChild(defaultOption);

        if (lessons && lessons.length > 0) {
            lessons.forEach(function(lesson) {
                const option = document.createElement('option');
                option.value = lesson.id.toString(); // Ensure value is string for consistency
                option.textContent = lesson.title;
                // Check if lessonToSelect is not null and matches current lesson's ID
                if (lessonToSelect && lesson.id.toString() === lessonToSelect) {
                    option.selected = true;
                }
                lessonSelect.appendChild(option);
            });
            lessonGroup.style.display = 'block';
        } else {
            const noLessonsOption = document.createElement('option');
            noLessonsOption.value = '';
            noLessonsOption.textContent = 'No lessons available for this subject';
            noLessonsOption.disabled = true;
            lessonSelect.appendChild(noLessonsOption);
            defaultOption.textContent = 'No lessons available';
            lessonSelect.value = ''; 
            lessonGroup.style.display = 'block';
        }
    }

    // Initial population of lesson dropdown
    if (subjectSelect && subjectSelect.value) { // If a subject is initially selected
        populateLessonDropdown(lessonsForCurrentlySelectedSubject, preSelectedLessonId);
    } else if (lessonGroup) {
        lessonGroup.style.display = 'none'; // No subject selected, hide lesson dropdown
    }

    if (subjectSelect) {
        subjectSelect.addEventListener('change', function() {
            const selectedSubjectId = this.value;
            if (selectedSubjectId && createAssignmentUrl) {
                window.location.href = createAssignmentUrl + "?subject_id=" + selectedSubjectId;
            } else if (lessonGroup) {
                lessonSelect.innerHTML = '';
                const option = document.createElement('option');
                option.value = '';
                option.textContent = 'Select Lesson (Optional)';
                lessonSelect.appendChild(option);
                lessonGroup.style.display = 'none';
            }
        });
    }
});
