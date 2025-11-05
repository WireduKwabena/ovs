// Function to handle theme management
function initTheme() {
    const themeController = document.querySelector('.theme-controller');
    
    // Function to set theme
    function setTheme(isDark) {
        document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
        themeController.checked = isDark;
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
    }

    // Initial theme setup
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        setTheme(savedTheme === 'dark');
    } else {
        setTheme(window.matchMedia('(prefers-color-scheme: dark)').matches);
    }

    // Listen for theme toggle
    themeController.addEventListener('change', (e) => {
        setTheme(e.target.checked);
    });

    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        if (!localStorage.getItem('theme')) {
            setTheme(e.matches);
        }
    });
}

// Initialize theme when DOM is loaded
document.addEventListener('DOMContentLoaded', initTheme);