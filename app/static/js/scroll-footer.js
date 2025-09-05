/**
 * Auto-show/hide floating footer on scroll direction (infinite scroll pages)
 */
(function() {
    'use strict';
    
    function initScrollFooter() {
        // Only run on pages with infinite scroll
        if (!document.body.classList.contains('has-infinite-scroll')) {
            return;
        }
        
        const footer = document.getElementById('floating-footer');
        if (!footer) {
            return;
        }
        
        let lastScrollY = window.scrollY;
        let ticking = false;
        const scrollThreshold = 15; // Minimum scroll distance to trigger
        const showAfterScroll = 200; // Show footer after scrolling this much
        
        function updateFooter() {
            const currentScrollY = window.scrollY;
            const scrollDiff = currentScrollY - lastScrollY;
            
            // Only act if we've scrolled enough
            if (Math.abs(scrollDiff) < scrollThreshold) {
                ticking = false;
                return;
            }
            
            // Show footer when scrolling up after a certain point (like header)
            if (scrollDiff < 0 && currentScrollY > showAfterScroll) {
                // Scrolling up - show footer
                footer.classList.add('footer-visible');
            } else if (scrollDiff > 0) {
                // Scrolling down - hide footer
                footer.classList.remove('footer-visible');
            }
            
            // Hide footer when near top
            if (currentScrollY < showAfterScroll) {
                footer.classList.remove('footer-visible');
            }
            
            lastScrollY = currentScrollY;
            ticking = false;
        }
        
        function requestTick() {
            if (!ticking) {
                requestAnimationFrame(updateFooter);
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
            
            if (Math.abs(touchDiff) > 25) {
                requestTick();
                touchStartY = touchY;
            }
        }, { passive: true });
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initScrollFooter);
    } else {
        initScrollFooter();
    }
})();