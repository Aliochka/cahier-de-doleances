/**
 * Auto-hide/show header on scroll direction
 */
(function() {
    'use strict';
    
    function initScrollHeader() {
        const header = document.getElementById('main-header');
        if (!header) {
            return;
        }
        
        let lastScrollY = window.scrollY;
        let ticking = false;
        const scrollThreshold = 10; // Minimum scroll distance to trigger
        
        function updateHeader() {
            const currentScrollY = window.scrollY;
            const scrollDiff = currentScrollY - lastScrollY;
            
            // Only act if we've scrolled enough
            if (Math.abs(scrollDiff) < scrollThreshold) {
                ticking = false;
                return;
            }
            
            if (scrollDiff > 0 && currentScrollY > 80) {
                // Scrolling down - hide header
                header.classList.add('header-hidden');
                header.classList.remove('header-visible');
            } else if (scrollDiff < 0) {
                // Scrolling up - show header  
                header.classList.remove('header-hidden');
                header.classList.add('header-visible');
            }
            
            lastScrollY = currentScrollY;
            ticking = false;
        }
        
        function requestTick() {
            if (!ticking) {
                requestAnimationFrame(updateHeader);
                ticking = true;
            }
        }
        
        // Listen to scroll events
        window.addEventListener('scroll', requestTick, { passive: true });
        
        // Handle touch/mobile scrolling
        let touchStartY = 0;
        document.addEventListener('touchstart', function(e) {
            touchStartY = e.touches[0].clientY;
        }, { passive: true });
        
        document.addEventListener('touchmove', function(e) {
            const touchY = e.touches[0].clientY;
            const touchDiff = touchStartY - touchY;
            
            if (Math.abs(touchDiff) > 20) {
                requestTick();
                touchStartY = touchY;
            }
        }, { passive: true });
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initScrollHeader);
    } else {
        initScrollHeader();
    }
})();