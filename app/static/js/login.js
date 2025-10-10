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

    // --- Forgot Password Modal Logic ---
    const forgotPasswordLink = document.getElementById('forgot-password-link');
    const forgotPasswordModal = document.getElementById('forgot-password-modal');
    const closeModal = document.querySelector('.close-modal');
    const forgotPasswordForm = document.getElementById('forgot-password-form');
    const resetEmailInput = document.getElementById('reset-email');
    const forgotPasswordMessage = document.getElementById('forgot-password-message');

    // Open modal
    if (forgotPasswordLink && forgotPasswordModal) {
        forgotPasswordLink.addEventListener('click', (e) => {
            e.preventDefault();
            forgotPasswordModal.classList.add('show');
            if (forgotPasswordMessage) {
                forgotPasswordMessage.textContent = '';
                forgotPasswordMessage.className = '';
            }
            if (resetEmailInput) {
                resetEmailInput.value = '';
            }
        });
    }

    // Close modal
    if (closeModal && forgotPasswordModal) {
        closeModal.addEventListener('click', () => {
            forgotPasswordModal.classList.remove('show');
        });
    }

    // Close modal when clicking outside
    if (forgotPasswordModal) {
        window.addEventListener('click', (e) => {
            if (e.target === forgotPasswordModal) {
                forgotPasswordModal.classList.remove('show');
            }
        });
    }

    // Handle forgot password form submission
    if (forgotPasswordForm && resetEmailInput && forgotPasswordMessage) {
        forgotPasswordForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const email = resetEmailInput.value.trim();

            // Validate email
            if (!email) {
                forgotPasswordMessage.textContent = 'Please enter your email address.';
                forgotPasswordMessage.className = 'error';
                return;
            }

            if (!/\S+@\S+\.\S+/.test(email)) {
                forgotPasswordMessage.textContent = 'Please enter a valid email address.';
                forgotPasswordMessage.className = 'error';
                return;
            }

            try {
                const response = await fetch('/auth/forgot-password', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ email: email })
                });

                const data = await response.json();

                if (response.ok) {
                    forgotPasswordMessage.textContent = data.message || 'Password reset request submitted successfully. An admin will review your request.';
                    forgotPasswordMessage.className = 'success';
                    resetEmailInput.value = '';

                    // Close modal after 3 seconds
                    setTimeout(() => {
                        if (forgotPasswordModal) {
                            forgotPasswordModal.classList.remove('show');
                        }
                    }, 3000);
                } else {
                    forgotPasswordMessage.textContent = data.error || 'An error occurred. Please try again.';
                    forgotPasswordMessage.className = 'error';
                }
            } catch (error) {
                console.error('Error submitting password reset request:', error);
                forgotPasswordMessage.textContent = 'Network error. Please try again later.';
                forgotPasswordMessage.className = 'error';
            }
        });
    }
});
