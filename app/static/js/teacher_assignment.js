document.addEventListener('DOMContentLoaded', function() {
    const subjectSelect = document.getElementById('assignment-subject');
    const lessonGroup = document.getElementById('lesson-group');
    const lessonSelect = document.getElementById('assignment-lesson');
    const dueDateInput = document.getElementById('assignment-due-date');
    const assignmentTypeSelect = document.getElementById('assignment-type');
    const textAnswersGroup = document.getElementById('text-answers-group');
    const correctAnswersTextarea = document.getElementById('correct-answers');
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
            if (selectedSubjectId) {
                // Fetch lessons for the selected subject without page refresh
                fetch(`/teacher/api/get-lessons-by-subject/${selectedSubjectId}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.success && data.lessons) {
                            populateLessonDropdown(data.lessons, null);
                        } else {
                            populateLessonDropdown([], null);
                        }
                    })
                    .catch(error => {
                        console.error('Error fetching lessons:', error);
                        populateLessonDropdown([], null);
                    });
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

    // Add form validation before submission
    const assignmentForm = document.querySelector('.assignment-form');
    if (assignmentForm) {
        assignmentForm.addEventListener('submit', function(e) {
            const title = document.getElementById('assignment-title').value.trim();
            const description = document.getElementById('assignment-description').value.trim();
            const subjectId = document.getElementById('assignment-subject').value;
            const dueDate = document.getElementById('assignment-due-date').value;
            const correctAnswers = document.getElementById('correct-answers').value.trim();

            if (!title || !description || !subjectId || !dueDate || !correctAnswers) {
                e.preventDefault();
                alert('Please fill in all required fields:\n- Assignment Title\n- Description\n- Subject\n- Due Date\n- Expected Answer/Words');
                return false;
            }

            if (title.length < 3) {
                e.preventDefault();
                alert('Assignment title must be at least 3 characters long.');
                return false;
            }

            if (description.length < 10) {
                e.preventDefault();
                alert('Assignment description must be at least 10 characters long.');
                return false;
            }

            if (correctAnswers.length < 2) {
                e.preventDefault();
                alert('Expected Answer/Words must be at least 2 characters long.');
                return false;
            }
        });
    }
});
