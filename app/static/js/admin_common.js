

function initializeDeleteConfirmations() {
    const deleteForms = document.querySelectorAll('form.delete-confirm-form');

    deleteForms.forEach(form => {
        form.addEventListener('submit', function(event) {
            const message = form.dataset.confirmMessage || 'Are you sure you want to delete this item? This action cannot be undone.';

         
            if (!confirm(message)) {
                event.preventDefault(); 
                console.log('Delete action cancelled by user.');
            } else {
                console.log('Delete action confirmed by user. Submitting form...');
            }
        });
    });
}

document.addEventListener('DOMContentLoaded', initializeDeleteConfirmations);