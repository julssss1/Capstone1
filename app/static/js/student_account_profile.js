// Bio editing functionality for student account profile
document.addEventListener('DOMContentLoaded', function() {
    const noteDisplay = document.getElementById('noteDisplay');
    const noteEditor = document.getElementById('noteEditor');
    const noteActions = document.querySelector('.note-actions');
    const saveBtn = document.getElementById('saveNote');
    const cancelBtn = document.getElementById('cancelNote');
    
    // Get current bio from the display element's data attribute
    const currentBio = noteDisplay.getAttribute('data-bio') || '';
    
    // Click on display to edit
    noteDisplay.addEventListener('click', function() {
        noteEditor.value = currentBio;
        noteDisplay.style.display = 'none';
        noteEditor.style.display = 'block';
        noteActions.style.display = 'block';
        noteEditor.focus();
    });
    
    // Cancel editing
    cancelBtn.addEventListener('click', function() {
        noteEditor.style.display = 'none';
        noteActions.style.display = 'none';
        noteDisplay.style.display = 'block';
    });
    
    // Save bio
    saveBtn.addEventListener('click', async function() {
        const bioText = noteEditor.value.trim();
        
        try {
            const response = await fetch('/student/update_bio', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ bio: bioText })
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Update display
                if (bioText) {
                    noteDisplay.textContent = bioText;
                    noteDisplay.setAttribute('data-bio', bioText);
                } else {
                    noteDisplay.innerHTML = '<span class="plus-icon">+</span> Add Note Here';
                    noteDisplay.setAttribute('data-bio', '');
                }
                
                // Hide editor
                noteEditor.style.display = 'none';
                noteActions.style.display = 'none';
                noteDisplay.style.display = 'block';
                
                // Show success message
                alert('Bio updated successfully!');
            } else {
                alert('Error: ' + result.error);
            }
        } catch (error) {
            console.error('Error updating bio:', error);
            alert('Failed to update bio. Please try again.');
        }
    });
});
