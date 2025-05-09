document.addEventListener('DOMContentLoaded', () => {
    const triggerButton = document.getElementById('show-login-trigger');
    const loginContainer = document.querySelector('.login-container');
    const loginForm = document.getElementById('login-form');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const errorDiv = document.getElementById('login-error');
  
    // --- Transition Logic ---
    if (triggerButton && loginContainer) {
        triggerButton.addEventListener('click', () => {
            loginContainer.classList.add('form-active');

            if (errorDiv) {
                errorDiv.style.display = 'none';
                errorDiv.textContent = '';
            }
            if(emailInput) emailInput.style.borderColor = '';
            if(passwordInput) passwordInput.style.borderColor = '';
        });
    }

    if (loginForm && emailInput && passwordInput && errorDiv) {
        loginForm.addEventListener('submit', function(event) {
            let isValid = true;
            let errorMessage = '';

            errorDiv.style.display = 'none';
            errorDiv.textContent = '';
            emailInput.style.borderColor = '';
            passwordInput.style.borderColor = '';
            // Validate Email
            if (!emailInput.value.trim()) {
                isValid = false;
                errorMessage = 'Please enter your email.';
                emailInput.style.borderColor = 'red';
            } else if (!/\S+@\S+\.\S+/.test(emailInput.value)) {
                isValid = false;
                errorMessage = 'Please enter a valid email address.';
                emailInput.style.borderColor = 'red';
            }
        // Validate Password
            if (isValid && !passwordInput.value.trim()) {
                isValid = false;
                errorMessage = 'Please enter your password.';
                passwordInput.style.borderColor = 'red';
            }
        // If invalid, prevent submission and show error            
            if (!isValid) {
                event.preventDefault();
                errorDiv.textContent = errorMessage;
                errorDiv.style.display = 'block';

                if (emailInput.style.borderColor === 'red') {
                    emailInput.focus();
                } else if (passwordInput.style.borderColor === 'red') {
                    passwordInput.focus();
                }
            }
        });
    } else {
        console.error("Login form elements not found. Validation and transition might not work as expected.");
    }
});