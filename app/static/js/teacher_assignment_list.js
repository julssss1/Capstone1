// Teacher Assignment List - Due Date Editing Functionality

document.addEventListener('DOMContentLoaded', function() {
    // Set minimum date to today for all date inputs
    const today = new Date().toISOString().split('T')[0];
    
    // Get all due date cells
    const dueDateCells = document.querySelectorAll('.due-date-cell');
    
    dueDateCells.forEach(cell => {
        const assignmentId = cell.dataset.assignmentId;
        const displaySpan = cell.querySelector('.due-date-display');
        const dateInput = cell.querySelector('.due-date-input');
        const editBtn = cell.querySelector('.edit-due-date-btn');
        const saveBtn = cell.querySelector('.save-due-date-btn');
        const cancelBtn = cell.querySelector('.cancel-due-date-btn');
        
        let originalValue = dateInput.value;
        
        // Edit button click
        editBtn.addEventListener('click', function() {
            originalValue = dateInput.value; // Store original value
            dateInput.setAttribute('min', today); // Set minimum date to today
            displaySpan.style.display = 'none';
            dateInput.style.display = 'inline-block';
            editBtn.style.display = 'none';
            saveBtn.style.display = 'inline-block';
            cancelBtn.style.display = 'inline-block';
            dateInput.focus();
        });
        
        // Cancel button click
        cancelBtn.addEventListener('click', function() {
            dateInput.value = originalValue; // Restore original value
            displaySpan.style.display = 'inline';
            dateInput.style.display = 'none';
            editBtn.style.display = 'inline-block';
            saveBtn.style.display = 'none';
            cancelBtn.style.display = 'none';
        });
        
        // Save button click
        saveBtn.addEventListener('click', function() {
            const newDueDate = dateInput.value;
            
            if (!newDueDate) {
                alert('Please select a valid date.');
                return;
            }
            
            // Disable buttons during save
            saveBtn.disabled = true;
            cancelBtn.disabled = true;
            
            // Send update request to server
            fetch(`/teacher/assignment/update-due-date/${assignmentId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    due_date: newDueDate
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Update the display
                    displaySpan.textContent = newDueDate;
                    originalValue = newDueDate;
                    
                    // Reset UI
                    displaySpan.style.display = 'inline';
                    dateInput.style.display = 'none';
                    editBtn.style.display = 'inline-block';
                    saveBtn.style.display = 'none';
                    cancelBtn.style.display = 'none';
                    
                    // Show success message
                    showMessage('Due date updated successfully!', 'success');
                } else {
                    alert('Error: ' + (data.message || 'Failed to update due date.'));
                }
            })
            .catch(error => {
                console.error('Error updating due date:', error);
                alert('An error occurred while updating the due date. Please try again.');
            })
            .finally(() => {
                // Re-enable buttons
                saveBtn.disabled = false;
                cancelBtn.disabled = false;
            });
        });
    });
});

// Helper function to show messages
function showMessage(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;
    alertDiv.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999; padding: 15px; border-radius: 5px; box-shadow: 0 2px 10px rgba(0,0,0,0.2);';
    
    if (type === 'success') {
        alertDiv.style.backgroundColor = '#d4edda';
        alertDiv.style.color = '#155724';
        alertDiv.style.border = '1px solid #c3e6cb';
    }
    
    document.body.appendChild(alertDiv);
    
    // Auto-remove after 3 seconds
    setTimeout(() => {
        alertDiv.remove();
    }, 3000);
}
