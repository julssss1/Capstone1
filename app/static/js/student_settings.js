document.addEventListener('DOMContentLoaded', function() {
    // Profile Picture Upload Functionality
    const profileForm = document.getElementById('profilePictureForm');
    const fileInput = document.getElementById('profile_picture_upload');
    const chooseBtn = document.getElementById('choosePictureBtn');
    const uploadBtn = document.getElementById('uploadPictureBtn');

    if (chooseBtn && fileInput) {
        chooseBtn.addEventListener('click', function() {
            console.log('Choose Picture button clicked.');
            fileInput.click();
        });
    } else {
        console.error('Could not find Choose Picture button or file input.');
    }

    if (uploadBtn && profileForm) {
        uploadBtn.addEventListener('click', function(event) {
            event.preventDefault();
            console.log('Upload Picture button clicked. Attempting form submission via JS.');
            if (fileInput.files.length === 0) {
                alert('Please choose a picture first.');
                return;
            }
            profileForm.submit();
        });
    } else {
        console.error('Could not find Upload Picture button or profile form.');
    }

    // Password Change Validation
    const passwordForm = document.getElementById('passwordChangeForm');
    const newPasswordInput = document.getElementById('new_password');
    const confirmPasswordInput = document.getElementById('confirm_password');
    const matchMessage = document.getElementById('password-match-message');

    // Real-time password match validation
    function validatePasswordMatch() {
        const newPassword = newPasswordInput.value;
        const confirmPassword = confirmPasswordInput.value;

        if (confirmPassword === '') {
            matchMessage.textContent = '';
            matchMessage.style.color = '';
            return true;
        }

        if (newPassword === confirmPassword) {
            matchMessage.textContent = '✓ Passwords match';
            matchMessage.style.color = '#28a745';
            return true;
        } else {
            matchMessage.textContent = '✗ Passwords do not match';
            matchMessage.style.color = '#dc3545';
            return false;
        }
    }

    // Add event listeners for real-time validation
    if (confirmPasswordInput) {
        confirmPasswordInput.addEventListener('input', validatePasswordMatch);
        newPasswordInput.addEventListener('input', validatePasswordMatch);
    }

    // Form submission validation
    if (passwordForm) {
        passwordForm.addEventListener('submit', function(event) {
            const newPassword = newPasswordInput.value;
            const confirmPassword = confirmPasswordInput.value;

            // Check password length
            if (newPassword.length < 6) {
                event.preventDefault();
                alert('Password must be at least 6 characters long.');
                newPasswordInput.focus();
                return false;
            }

            // Check if passwords match
            if (newPassword !== confirmPassword) {
                event.preventDefault();
                alert('Passwords do not match. Please confirm your new password correctly.');
                confirmPasswordInput.focus();
                return false;
            }

            // All validations passed
            return true;
        });
    }
});
