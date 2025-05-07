document.addEventListener('DOMContentLoaded', function() {
    const profileForm = document.getElementById('profilePictureForm');
    const fileInput = document.getElementById('profile_picture_upload');
    const chooseBtn = document.getElementById('choosePictureBtn');
    const uploadBtn = document.getElementById('uploadPictureBtn'); // Added ID for upload button

    if (chooseBtn && fileInput) {
        chooseBtn.addEventListener('click', function() {
            console.log('Choose Picture button clicked.');
            fileInput.click(); // Trigger the hidden file input
        });
    } else {
        console.error('Could not find Choose Picture button or file input.');
    }

    if (uploadBtn && profileForm) {
        uploadBtn.addEventListener('click', function(event) {
            event.preventDefault(); // Prevent default button behavior
            console.log('Upload Picture button clicked. Attempting form submission via JS.');
            if (fileInput.files.length === 0) {
                alert('Please choose a picture first.'); // Basic validation
                return;
            }
            profileForm.submit(); // Manually submit the form
        });
    } else {
        console.error('Could not find Upload Picture button or profile form.');
    }
});
