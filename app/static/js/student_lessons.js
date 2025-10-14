// Student Lessons Progress Tracking
// Handles recording and updating lesson progress

/**
 * Records student progress for a lesson content item
 * @param {number} lessonId - The ID of the lesson
 * @param {number} contentIndex - The index of the content item (-1 for overview)
 * @param {string} progressType - The type of progress ('page_view', 'quiz_complete', 'assignment_complete')
 */
function recordProgress(lessonId, contentIndex, progressType) {
    fetch(`/student/lesson/${lessonId}/record-progress`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            content_index: contentIndex,
            progress_type: progressType
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Progress recorded:', data);
            // Update progress bar and text for this lesson
            updateLessonProgress(lessonId, data.progress_percentage, data.completed_items, data.total_items);
        } else {
            console.error('Failed to record progress:', data.error);
        }
    })
    .catch(error => {
        console.error('Error recording progress:', error);
    });
    
    // Allow the link to navigate
    return true;
}

/**
 * Updates the progress bar UI for a specific lesson
 * @param {number} lessonId - The ID of the lesson
 * @param {number} percentage - The progress percentage
 * @param {number} completedItems - Number of completed items
 * @param {number} totalItems - Total number of items
 */
function updateLessonProgress(lessonId, percentage, completedItems, totalItems) {
    const lessonCard = document.querySelector(`[data-lesson-id="${lessonId}"]`);
    if (lessonCard) {
        const progressBar = lessonCard.querySelector('.progress-bar');
        const progressText = lessonCard.querySelector('.progress-text');
        
        if (progressBar) {
            progressBar.style.width = percentage + '%';
        }
        
        if (progressText) {
            progressText.textContent = `${percentage}% Complete (${completedItems}/${totalItems})`;
        }
    }
}

/**
 * Auto-record progress when viewing lesson content page
 * This function is called automatically when a lesson content page loads
 */
function autoRecordPageView() {
    // Check if we're on a lesson content page
    const lessonIdElement = document.getElementById('lesson-id');
    const contentIndexElement = document.getElementById('content-index');
    
    if (lessonIdElement && contentIndexElement) {
        const lessonId = parseInt(lessonIdElement.value);
        const contentIndex = parseInt(contentIndexElement.value);
        
        if (!isNaN(lessonId) && !isNaN(contentIndex)) {
            // Record page view automatically
            recordProgress(lessonId, contentIndex, 'page_view');
        }
    }
}

// Auto-record on page load if we're viewing lesson content
document.addEventListener('DOMContentLoaded', autoRecordPageView);

// Make recordProgress available globally for onclick handlers
window.recordProgress = recordProgress;
