document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('userDetailsForm');
    if (!form) {
        console.error('User details form not found.');
        return;
    }

    // Function to create or get the error message element for a field
    const getErrorElement = (inputElement) => {
        const fieldContainer = inputElement.closest('.form-group');
        let errorElement = fieldContainer.querySelector('.error-message');
        if (!errorElement) {
            errorElement = document.createElement('span');
            errorElement.className = 'error-message';
            fieldContainer.appendChild(errorElement);
        }
        return errorElement;
    };

    // Function to show an error message
    const showError = (inputElement, message) => {
        const errorElement = getErrorElement(inputElement);
        errorElement.textContent = message;
        inputElement.classList.add('is-invalid');
    };

    // Function to clear an error message
    const clearError = (inputElement) => {
        const errorElement = getErrorElement(inputElement);
        errorElement.textContent = '';
        inputElement.classList.remove('is-invalid');
    };

    // Real-time password matching feedback
    const newPassword = document.getElementById('new_password');
    const confirmPassword = document.getElementById('confirm_password');
    const passwordMatchMessage = document.getElementById('password-match-message');

    if (newPassword && confirmPassword && passwordMatchMessage) {
        const checkPasswordMatch = () => {
            if (confirmPassword.value === '') {
                passwordMatchMessage.textContent = '';
                passwordMatchMessage.style.color = '';
            } else if (newPassword.value === confirmPassword.value) {
                passwordMatchMessage.textContent = '✓ Passwords match';
                passwordMatchMessage.style.color = 'green';
            } else {
                passwordMatchMessage.textContent = '✗ Passwords do not match';
                passwordMatchMessage.style.color = 'red';
            }
        };

        newPassword.addEventListener('input', checkPasswordMatch);
        confirmPassword.addEventListener('input', checkPasswordMatch);
    }

    // Real-time validation as user types
    form.addEventListener('input', function(e) {
        const input = e.target;
        // Clear error on input for better UX
        clearError(input);
    });

    form.addEventListener('submit', function (event) {
        let isValid = true;

        // --- Field Definitions ---
        const firstName = document.getElementById('first_name');
        const lastName = document.getElementById('last_name');
        const middleName = document.getElementById('middle_name');
        const email = document.getElementById('email');
        const role = document.getElementById('role');
        const password = document.getElementById('password'); // For 'Add' mode
        const newPassword = document.getElementById('new_password'); // For 'Edit' mode
        const confirmPassword = document.getElementById('confirm_password'); // For 'Edit' mode

        // --- Clear all previous errors ---
        form.querySelectorAll('input, select').forEach(input => clearError(input));

        // --- Validation Logic ---

        // 1. Name Validation (First, Last, and Middle)
        const nameRegex = /^[a-zA-Z\s'-]+$/; // Allows letters, spaces, hyphens, apostrophes
        const nameErrorMsg = 'Names can only contain letters, spaces, hyphens (-), and apostrophes (\').';

        if (!firstName.value.trim()) {
            showError(firstName, 'First name is required.');
            isValid = false;
        } else if (!nameRegex.test(firstName.value)) {
            showError(firstName, nameErrorMsg);
            isValid = false;
        }

        if (!lastName.value.trim()) {
            showError(lastName, 'Last name is required.');
            isValid = false;
        } else if (!nameRegex.test(lastName.value)) {
            showError(lastName, nameErrorMsg);
            isValid = false;
        }

        // Middle name is optional, but if filled, it must be valid
        if (middleName.value.trim() && !nameRegex.test(middleName.value)) {
            showError(middleName, nameErrorMsg);
            isValid = false;
        }

        // 2. Email Validation
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!email.value.trim()) {
            showError(email, 'Email is required.');
            isValid = false;
        } else if (!emailRegex.test(email.value)) {
            showError(email, 'Please enter a valid email address.');
            isValid = false;
        }

        // 4. Role Validation
        if (!role.value) {
            showError(role, 'Please select a role.');
            isValid = false;
        }

        // 5. Password Validation ('Add' mode)
        if (password && !password.value) { // Check if the element exists and is empty
            showError(password, 'Password is required.');
            isValid = false;
        } else if (password && password.value.length < 8) {
            showError(password, 'Password must be at least 8 characters long.');
            isValid = false;
        }

        // 6. New Password Validation ('Edit' mode)
        // Only validate if the field is present and has a value
        if (newPassword && newPassword.value && newPassword.value.length < 8) {
            showError(newPassword, 'Password must be at least 8 characters long.');
            isValid = false;
        }

        // 7. Confirm Password Validation ('Edit' mode)
        // Only validate if new password has a value
        if (newPassword && confirmPassword && newPassword.value) {
            if (!confirmPassword.value) {
                showError(confirmPassword, 'Please confirm your new password.');
                isValid = false;
            } else if (newPassword.value !== confirmPassword.value) {
                showError(confirmPassword, 'Passwords do not match.');
                isValid = false;
            }
        }

        // --- Prevent form submission if invalid ---
        if (!isValid) {
            event.preventDefault();
            // Find the first invalid field and focus it for better accessibility
            const firstInvalidField = form.querySelector('.is-invalid');
            if (firstInvalidField) {
                firstInvalidField.focus();
            }
        }
    });
});
