 document.addEventListener('DOMContentLoaded', function() {
            const hamburgerButton = document.querySelector('.hamburger-button');
            const sideMenu = document.querySelector('.side-menu');

            if (hamburgerButton && sideMenu) {
                hamburgerButton.addEventListener('click', function() {
                    sideMenu.classList.toggle('is-open');
                    const isOpen = sideMenu.classList.contains('is-open');
                    hamburgerButton.setAttribute('aria-expanded', isOpen);
                    if (isOpen) {
                        hamburgerButton.setAttribute('aria-label', 'Close menu');
                    } else {
                        hamburgerButton.setAttribute('aria-label', 'Open menu');
                    }
                });

                // Optional: Close menu when clicking outside of it on mobile
                document.addEventListener('click', function(event) {
                    if (sideMenu.classList.contains('is-open') && 
                        !sideMenu.contains(event.target) && 
                        !hamburgerButton.contains(event.target)) {
                        sideMenu.classList.remove('is-open');
                        hamburgerButton.setAttribute('aria-expanded', 'false');
                        hamburgerButton.setAttribute('aria-label', 'Open menu');
                    }
                });
            }
        });