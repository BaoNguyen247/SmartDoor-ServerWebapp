let currentSection = 'face-recognition';

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    // initializeParticles is optional — guard its call
    if (typeof initializeParticles === 'function') {
        initializeParticles();
    }
    // initializeCamera may be implemented elsewhere; only call if available
    if (typeof initializeCamera === 'function') {
        try {
            initializeCamera();
        } catch (e) {
            console.warn('initializeCamera failed:', e);
        }
    }
});

// Navigation function
function showSection(sectionId) {
    // Hide all sections
    document.querySelectorAll('main > section').forEach(section => {
        section.classList.add('hidden');
    });

    // Show selected section
    const el = document.getElementById(sectionId);
    if (el) el.classList.remove('hidden');

    // Update sidebar active state (find the sidebar item by onclick attribute)
    document.querySelectorAll('.sidebar-item').forEach(item => {
        item.classList.remove('active');
    });
    const sidebarItem = document.querySelector(`.sidebar-item[onclick*="${sectionId}"]`);
    if (sidebarItem) sidebarItem.classList.add('active');

    currentSection = sectionId;

    // Initialize section-specific features if available
    if (sectionId === 'face-recognition' && typeof startFaceRecognition === 'function') {
        startFaceRecognition();
    } else if (sectionId === 'face-registration' && typeof initializeRegistrationCamera === 'function') {
        initializeRegistrationCamera();
    }
}

// Particles.js initialization
function initializeParticles() {
    particlesJS('particles-js', {
        particles: {
            number: { value: 50 },
            color: { value: '#007BFF' },
            shape: { type: 'circle' },
            opacity: { value: 0.3 },
            size: { value: 3 },
            move: {
                enable: true,
                speed: 2,
                direction: 'none',
                random: true,
                out_mode: 'out'
            }
        },
        interactivity: {
            detect_on: 'canvas',
            events: {
                onhover: { enable: true, mode: 'repulse' },
                onclick: { enable: true, mode: 'push' }
            }
        }
    });
}