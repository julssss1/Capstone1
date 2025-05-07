// --- START OF FILE static/js/login.js ---

document.addEventListener('DOMContentLoaded', () => { // Use arrow function for consistency or stick to 'function()'

    // --- Elements for Transition ---
    const triggerButton = document.getElementById('show-login-trigger');
    const loginContainer = document.querySelector('.login-container');
    // loginFormContent not directly needed for this JS, but good practice to reference if complex interactions added later

    // --- Elements for Validation (from your code) ---
    const loginForm = document.getElementById('login-form');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const errorDiv = document.getElementById('login-error'); // Your error display element

    // --- Transition Logic ---
    if (triggerButton && loginContainer) {
        triggerButton.addEventListener('click', () => {
            loginContainer.classList.add('form-active');

            // Optional: Reset validation states when revealing the form
            if (errorDiv) {
                errorDiv.style.display = 'none';
                errorDiv.textContent = '';
            }
            if(emailInput) emailInput.style.borderColor = ''; // Reset border
            if(passwordInput) passwordInput.style.borderColor = ''; // Reset border
        });
    }

    // --- Validation Logic (Your provided code integrated) ---
    if (loginForm && emailInput && passwordInput && errorDiv) { // Ensure all elements exist
        loginForm.addEventListener('submit', function(event) { // Using 'function' as per your original code
            let isValid = true;
            let errorMessage = '';

            // Clear previous errors (from your code)
            errorDiv.style.display = 'none';
            errorDiv.textContent = ''; // Also clear text content
            emailInput.style.borderColor = ''; // Reset border
            passwordInput.style.borderColor = ''; // Reset border

            // Validate Email (from your code)
            if (!emailInput.value.trim()) {
                isValid = false;
                errorMessage = 'Please enter your email.';
                emailInput.style.borderColor = 'red';
            } else if (!/\S+@\S+\.\S+/.test(emailInput.value)) { // Basic email format check
                isValid = false;
                errorMessage = 'Please enter a valid email address.';
                emailInput.style.borderColor = 'red';
            }

            // Validate Password (from your code)
            // Check password only if email is valid so far to show one error at a time
            if (isValid && !passwordInput.value.trim()) {
                isValid = false;
                errorMessage = 'Please enter your password.';
                passwordInput.style.borderColor = 'red';
            }

            // If invalid, prevent submission and show error (from your code)
            if (!isValid) {
                event.preventDefault(); // Stop the form from submitting
                errorDiv.textContent = errorMessage;
                errorDiv.style.display = 'block'; // Show the error message

                // Focus the first invalid field (from your code)
                if (emailInput.style.borderColor === 'red') { // Check which field caused the error
                    emailInput.focus();
                } else if (passwordInput.style.borderColor === 'red') {
                    passwordInput.focus();
                }
            }
            // If valid, the form will submit as normal
        });
    } else {
        // Optional: Log an error if essential elements are missing
        console.error("Login form elements not found. Validation and transition might not work.");
    }

}); // End DOMContentLoaded