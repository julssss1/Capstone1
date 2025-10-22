/**
 * Student Assignment Filter Functionality
 * Handles filtering assignments by subject and lesson
 */

document.addEventListener('DOMContentLoaded', function() {
    const table = document.querySelector('.assignments-table tbody');
    const subjectFilter = document.getElementById('subject-filter');
    const lessonFilter = document.getElementById('lesson-filter');
    const statusFilter = document.getElementById('status-filter');
    const resetBtn = document.getElementById('reset-filters');

    // Only initialize if table exists (there are assignments)
    if (!table) return;

    // Populate filter dropdowns with unique values from table
    function populateFilters() {
        const subjects = new Set();
        const lessons = new Set();
        const rows = table.querySelectorAll('tr');

        rows.forEach(row => {
            const subjectCell = row.cells[0]; // Subject column
            const lessonCell = row.cells[1];   // Lesson column

            if (subjectCell && lessonCell) {
                const subjectText = subjectCell.textContent.trim();
                const lessonText = lessonCell.textContent.trim();

                if (subjectText && subjectText !== 'N/A') {
                    subjects.add(subjectText);
                }
                if (lessonText && lessonText !== 'N/A' && lessonText !== 'N/A (General)') {
                    lessons.add(lessonText);
                }
            }
        });

        // Sort and populate subject dropdown
        Array.from(subjects).sort().forEach(subject => {
            const option = document.createElement('option');
            option.value = subject;
            option.textContent = subject;
            subjectFilter.appendChild(option);
        });

        // Sort and populate lesson dropdown
        Array.from(lessons).sort().forEach(lesson => {
            const option = document.createElement('option');
            option.value = lesson;
            option.textContent = lesson;
            lessonFilter.appendChild(option);
        });
    }

    // Filter table based on selected filters
    function filterTable() {
        const selectedSubject = subjectFilter.value.toLowerCase();
        const selectedLesson = lessonFilter.value.toLowerCase();
        const selectedStatus = statusFilter.value.toLowerCase();
        const rows = table.querySelectorAll('tr');
        let visibleCount = 0;

        rows.forEach(row => {
            const subjectCell = row.cells[0];
            const lessonCell = row.cells[1];
            const statusCell = row.cells[4]; // Status is in the 5th column (index 4)

            if (!subjectCell || !lessonCell || !statusCell) return;

            const subjectText = subjectCell.textContent.trim().toLowerCase();
            const lessonText = lessonCell.textContent.trim().toLowerCase();
            const statusText = statusCell.textContent.trim().toLowerCase();

            // Check if row matches filters
            const subjectMatch = !selectedSubject || subjectText.includes(selectedSubject);
            const lessonMatch = !selectedLesson || lessonText.includes(selectedLesson);
            const statusMatch = !selectedStatus || statusText.includes(selectedStatus);

            // Show/hide row based on filter match
            if (subjectMatch && lessonMatch && statusMatch) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        });

        // Show message if no results
        showNoResultsMessage(visibleCount === 0);
    }

    // Show/hide "no results" message
    function showNoResultsMessage(show) {
        let noResultsMsg = document.querySelector('.no-results-message');
        
        if (show) {
            if (!noResultsMsg) {
                noResultsMsg = document.createElement('div');
                noResultsMsg.className = 'no-results-message';
                noResultsMsg.innerHTML = '<p><i class="fas fa-search"></i> No assignments match your filters. Try adjusting your selection.</p>';
                table.parentElement.appendChild(noResultsMsg);
            }
            noResultsMsg.style.display = 'block';
        } else {
            if (noResultsMsg) {
                noResultsMsg.style.display = 'none';
            }
        }
    }

    // Reset all filters
    function resetFilters() {
        subjectFilter.value = '';
        lessonFilter.value = '';
        statusFilter.value = '';
        filterTable();
    }

    // Event listeners
    if (subjectFilter) {
        subjectFilter.addEventListener('change', filterTable);
    }
    
    if (lessonFilter) {
        lessonFilter.addEventListener('change', filterTable);
    }
    
    if (statusFilter) {
        statusFilter.addEventListener('change', filterTable);
    }
    
    if (resetBtn) {
        resetBtn.addEventListener('click', resetFilters);
    }

    // Initialize filters on page load
    populateFilters();
});
