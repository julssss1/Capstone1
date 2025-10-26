// Teacher Archived Assignments - Restore Functionality

document.addEventListener('DOMContentLoaded', function() {
    const restoreButtons = document.querySelectorAll('.restore-btn');
    
    restoreButtons.forEach(button => {
        button.addEventListener('click', function() {
            const archiveId = this.dataset.archiveId;
            const assignmentTitle = this.dataset.assignmentTitle;
            
            // Show confirmation dialog
            if (confirm(`Are you sure you want to restore the assignment "${assignmentTitle}"?\n\nThis will move it back to your active assignments list.`)) {
                // Disable button during restore
                button.disabled = true;
                button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Restoring...';
                
                // Send restore request to server
                fetch(`/teacher/assignment/restore/${archiveId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Remove the row from the table
                        const row = button.closest('tr');
                        row.style.transition = 'opacity 0.3s';
                        row.style.opacity = '0';
                        
                        setTimeout(() => {
                            row.remove();
                            
                            // Check if table is now empty
                            const tbody = document.querySelector('.assignments-table tbody');
                            if (tbody && tbody.querySelectorAll('tr').length === 0) {
                                // Reload page to show "no archives" message
                                location.reload();
                            }
                        }, 300);
                        
                        showMessage('Assignment restored successfully!', 'success');
                    } else {
                        alert('Error: ' + (data.message || 'Failed to restore assignment.'));
                        button.disabled = false;
                        button.innerHTML = '<i class="fas fa-undo"></i> Restore';
                    }
                })
                .catch(error => {
                    console.error('Error restoring assignment:', error);
                    alert('An error occurred while restoring the assignment. Please try again.');
                    button.disabled = false;
                    button.innerHTML = '<i class="fas fa-undo"></i> Restore';
                });
            }
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
