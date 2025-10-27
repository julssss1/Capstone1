document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('userDetailsForm');
    if (!form) {
        console.error('User details form not found.');
        return;
    }

    // Password generation function
    const generatePassword = () => {
        const uppercaseChars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
        const lowercaseChars = 'abcdefghijklmnopqrstuvwxyz';
        const numberChars = '0123456789';
        const atSymbol = '@';
        
        // Generate 9 random characters (uppercase, lowercase, and numbers)
        let password = '';
        const allChars = uppercaseChars + lowercaseChars + numberChars;
        
        // Ensure at least one of each type
        password += uppercaseChars[Math.floor(Math.random() * uppercaseChars.length)];
        password += lowercaseChars[Math.floor(Math.random() * lowercaseChars.length)];
        password += numberChars[Math.floor(Math.random() * numberChars.length)];
        
        // Fill remaining 6 characters randomly
        for (let i = 0; i < 6; i++) {
            password += allChars[Math.floor(Math.random() * allChars.length)];
        }
        
        // Shuffle the password (except the last character which will be @)
        password = password.split('').sort(() => Math.random() - 0.5).join('');
        
        // Add @ at the end
        password += atSymbol;
        
        return password;
    };

    // Handle generate password button clicks
    const generatePasswordBtns = document.querySelectorAll('.generate-password-btn');
    generatePasswordBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            
            const generatedPassword = generatePassword();
            
            // Find the appropriate password fields based on the context
            const passwordField = document.getElementById('password'); // Add mode
            const newPasswordField = document.getElementById('new_password'); // Edit mode
            const confirmPasswordField = document.getElementById('confirm_password'); // Edit mode
            
            if (passwordField) {
                // Add mode - single password field
                passwordField.value = generatedPassword;
            } else if (newPasswordField && confirmPasswordField) {
                // Edit mode - new password and confirm password fields
                newPasswordField.value = generatedPassword;
                confirmPasswordField.value = generatedPassword;
                
                // Trigger input event to update password match message
                const event = new Event('input', { bubbles: true });
                confirmPasswordField.dispatchEvent(event);
            }
            
            // Visual feedback
            btn.textContent = '✓ Generated!';
            btn.style.backgroundColor = '#4CAF50';
            setTimeout(() => {
                btn.textContent = 'Generate Password';
                btn.style.backgroundColor = '';
            }, 2000);
        });
    });

    // Handle grade level visibility based on role selection
    const roleSelect = document.getElementById('role');
    const gradeFieldContainer = document.getElementById('gradeFieldContainer');
    
    if (roleSelect && gradeFieldContainer) {
        roleSelect.addEventListener('change', function() {
            if (this.value === 'Student') {
                gradeFieldContainer.style.display = 'flex';
            } else {
                gradeFieldContainer.style.display = 'none';
                // Clear grade selection when role changes to non-Student
                const gradeSelect = document.getElementById('grade_level');
                if (gradeSelect) {
                    gradeSelect.value = '';
                }
            }
        });
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

        // 5. Grade Level Validation (for Students)
        const gradeLevel = document.getElementById('grade_level');
        if (role.value === 'Student' && gradeLevel) {
            if (!gradeLevel.value) {
                showError(gradeLevel, 'Grade level is required for students.');
                isValid = false;
            }
        }

        // 6. Password Validation ('Add' mode)
        if (password && !password.value) { // Check if the element exists and is empty
            showError(password, 'Password is required.');
            isValid = false;
        } else if (password && password.value.length < 8) {
            showError(password, 'Password must be at least 8 characters long.');
            isValid = false;
        }

        // 7. New Password Validation ('Edit' mode)
        // Only validate if the field is present and has a value
        if (newPassword && newPassword.value && newPassword.value.length < 8) {
            showError(newPassword, 'Password must be at least 8 characters long.');
            isValid = false;
        }

        // 8. Confirm Password Validation ('Edit' mode)
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
