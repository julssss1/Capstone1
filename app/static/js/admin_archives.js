// Admin Archives Page JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Auto-submit form when archive type changes
    const typeSelect = document.getElementById('type');
    if (typeSelect) {
        typeSelect.addEventListener('change', function() {
            this.form.submit();
        });
    }
    
    // Confirmation for viewing archive details
    const archiveLinks = document.querySelectorAll('.archive-detail-link');
    archiveLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            // Optional: Add loading indicator
            const row = this.closest('tr');
            if (row) {
                row.style.opacity = '0.6';
            }
        });
    });
    
    // Export functionality (future enhancement)
    function exportArchives() {
        // Get current filters
        const type = document.getElementById('type')?.value || 'users';
        const search = document.getElementById('search')?.value || '';
        const dateFrom = document.getElementById('date_from')?.value || '';
        const dateTo = document.getElementById('date_to')?.value || '';
        
        // Build export URL with filters
        const params = new URLSearchParams({
            type: type,
            search: search,
            date_from: dateFrom,
            date_to: dateTo,
            export: 'csv'
        });
        
        // Future: Implement CSV export endpoint
        console.log('Export with filters:', params.toString());
        alert('Export functionality will be implemented in a future update.');
    }
    
    // Make export function available globally
    window.exportArchives = exportArchives;
    
    // Search debounce functionality
    const searchInput = document.getElementById('search');
    let searchTimeout;
    
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            const form = this.form;
            
            // Only auto-submit if user stops typing for 500ms
            searchTimeout = setTimeout(() => {
                if (this.value.length >= 3 || this.value.length === 0) {
                    form.submit();
                }
            }, 500);
        });
    }
    
    // Date range validation
    const dateFromInput = document.getElementById('date_from');
    const dateToInput = document.getElementById('date_to');
    
    if (dateFromInput && dateToInput) {
        dateFromInput.addEventListener('change', function() {
            if (dateToInput.value && this.value > dateToInput.value) {
                alert('Start date cannot be after end date.');
                this.value = '';
            }
        });
        
        dateToInput.addEventListener('change', function() {
            if (dateFromInput.value && this.value < dateFromInput.value) {
                alert('End date cannot be before start date.');
                this.value = '';
            }
        });
    }
    
    // Table row hover effects
    const tableRows = document.querySelectorAll('.users-table tbody tr');
    tableRows.forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#f5f5f5';
        });
        
        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });
    });
    
    // Print functionality
    function printArchives() {
        window.print();
    }
    
    window.printArchives = printArchives;
    
    // Initialize tooltips (if needed)
    const badges = document.querySelectorAll('.archive-type-badge');
    badges.forEach(badge => {
        badge.title = 'Archive Type: ' + badge.textContent;
    });
    
    // Format dates for better display
    function formatDate(dateString) {
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString('en-US', { 
                year: 'numeric', 
                month: 'long', 
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (e) {
            return dateString;
        }
    }
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + F to focus search
        if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
            e.preventDefault();
            const searchInput = document.getElementById('search');
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        }
        
        // Escape to clear filters
        if (e.key === 'Escape') {
            const clearBtn = document.querySelector('.btn-clear');
            if (clearBtn && document.activeElement.tagName !== 'INPUT') {
                window.location.href = clearBtn.href;
            }
        }
    });
});
