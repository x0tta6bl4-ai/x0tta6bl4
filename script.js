// script.js
document.addEventListener('DOMContentLoaded', () => {
    // Smooth scrolling for navigation links
    document.querySelectorAll('nav a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();

            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });

    // Simple form submission feedback (can be enhanced with actual AJAX)
    const handleFormSubmission = async (event, successMessage) => {
        event.preventDefault();
        const emailInput = event.target.querySelector('input[type="email"]');
        const email = emailInput.value;

        try {
            const response = await fetch('/signup/email', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ email: email }),
            });

            if (response.ok) {
                alert(successMessage);
                event.target.reset();
            } else {
                const errorData = await response.json();
                alert(`Ошибка при отправке: ${errorData.detail || response.statusText}`);
            }
        } catch (error) {
            alert(`Произошла ошибка сети: ${error.message}`);
        }
    };

    const betaForm = document.querySelector('.beta-form');
    if (betaForm) {
        betaForm.addEventListener('submit', (e) => handleFormSubmission(e, 'Спасибо за ваш интерес! Мы свяжемся с вами в ближайшее время.'));
    }

    const newsletterForm = document.querySelector('.newsletter-form');
    if (newsletterForm) {
        newsletterForm.addEventListener('submit', (e) => handleFormSubmission(e, 'Вы успешно подписались на наши новости!'));
    }

    // You can add more interactive elements here if needed
    // For example, a simple animation on scroll, etc.
});
