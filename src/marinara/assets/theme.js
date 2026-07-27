// Sync app-container theme class to document.body
const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        if (mutation.attributeName === 'class') {
            const className = mutation.target.className;
            if (className.includes('dark-theme')) {
                document.body.classList.add('dark-theme');
                document.body.classList.remove('light-theme');
            } else {
                document.body.classList.add('light-theme');
                document.body.classList.remove('dark-theme');
            }
        }
    });
});

document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('app-container');
    if (container) {
        observer.observe(container, { attributes: true });
        // Set initial theme
        if (container.className.includes('dark-theme')) {
            document.body.classList.add('dark-theme');
            document.body.classList.remove('light-theme');
        } else {
            document.body.classList.add('light-theme');
            document.body.classList.remove('dark-theme');
        }
    } else {
        // Fallback check if container loads late
        const checkInterval = setInterval(() => {
            const containerLate = document.getElementById('app-container');
            if (containerLate) {
                observer.observe(containerLate, { attributes: true });
                if (containerLate.className.includes('dark-theme')) {
                    document.body.classList.add('dark-theme');
                    document.body.classList.remove('light-theme');
                } else {
                    document.body.classList.add('light-theme');
                    document.body.classList.remove('dark-theme');
                }
                clearInterval(checkInterval);
            }
        }, 100);
    }
});
