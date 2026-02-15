document.addEventListener('DOMContentLoaded', () => {
    // --- GENERIC MODAL LOGIC ---

    function setupModal(triggerId, modalId) {
        const trigger = document.getElementById(triggerId);
        const modal = document.getElementById(modalId);

        if (!trigger || !modal) return;

        const closeBtn = modal.querySelector('.modal-close');

        // Open
        trigger.addEventListener('click', () => {
            modal.classList.add('active');
            modal.setAttribute('aria-hidden', 'false');
        });

        // Close (X button)
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                closeModal(modal);
            });
        }

        // Close (Outside click)
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal(modal);
            }
        });

        // Form Logic
        setupForm(modal);
    }

    function closeModal(modal) {
        modal.classList.remove('active');
        modal.setAttribute('aria-hidden', 'true');
        // Reset form on close
        const form = modal.querySelector('form');
        if (form) {
            form.reset();
            const btn = form.querySelector('button[type="submit"]');
            // if (btn) btn.disabled = true;
            const input = form.querySelector('input');
            if (input) input.classList.remove('valid');
            const img = modal.querySelector('.avatar-preview-img');
            // Simplified reset to just a default steve head or just keep whatever
            if (img) img.src = `https://mc-heads.net/body/Steve/right`;
        }
    }

    // Initialize Modals
    setupModal('kit-lord-card', 'modal-kit-lord');
    setupModal('kit-knight-card', 'modal-kit-knight');
    setupModal('kit-guardian-card', 'modal-kit-guardian');
    setupModal('kit-champion-card', 'modal-kit-champion');

    // Close on ESC
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-overlay.active').forEach(modal => {
                closeModal(modal);
            });
        }
    });

    // --- FORM VALIDATION & AVATAR PREVIEW ---

    function startCountdown() {
        const timerElements = document.querySelectorAll('.timer-display');
        if (timerElements.length === 0) return;

        // Use the first element to determine the start time
        // Assuming all start with the same time in HTML
        const firstTimer = timerElements[0];
        const timeText = firstTimer.innerText.trim();
        let hours = 4, minutes = 59, seconds = 59; // Default fallback

        if (timeText.includes(':')) {
            const parts = timeText.split(':').map(p => parseInt(p, 10));
            if (parts.length === 3 && !parts.some(isNaN)) {
                [hours, minutes, seconds] = parts;
            }
        }

        let totalSeconds = hours * 3600 + minutes * 60 + seconds;

        const interval = setInterval(() => {
            if (totalSeconds <= 0) {
                clearInterval(interval);
                timerElements.forEach(el => el.innerText = "00:00:00");
                return;
            }

            totalSeconds--;

            const h = Math.floor(totalSeconds / 3600);
            const m = Math.floor((totalSeconds % 3600) / 60);
            const s = totalSeconds % 60;

            const timeString = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;

            timerElements.forEach(el => el.innerText = timeString);
        }, 1000);
    }

    startCountdown();

    function setupForm(modalContext) {
        const nicknameInput = modalContext.querySelector('.nickname-input');
        // Update selector to include origin-btn
        const buyButton = modalContext.querySelector('.btn-buy-yellow') || modalContext.querySelector('.btn-buy') || modalContext.querySelector('.origin-btn');
        const form = modalContext.querySelector('.purchase-form');
        const avatarPreviewImg = modalContext.querySelector('.avatar-preview-img');

        // Removed skinOptions listener logic as we only support 'nick' now
        let typingTimer;
        const doneTypingInterval = 800;

        if (!nicknameInput || !buyButton || !form) return;

        // Create feedback element if not exists
        let feedbackMsg = modalContext.querySelector('.nick-feedback');
        if (!feedbackMsg) {
            feedbackMsg = document.createElement('div');
            feedbackMsg.className = 'nick-feedback';
            feedbackMsg.style.fontSize = '0.8rem';
            feedbackMsg.style.marginTop = '5px';
            feedbackMsg.style.height = '1.2em'; // Reserve space
            nicknameInput.parentNode.appendChild(feedbackMsg);
        }

        nicknameInput.addEventListener('input', () => {
            const value = nicknameInput.value.trim();
            const isValidFormat = /^[a-zA-Z0-9_]{3,16}$/.test(value);

            // Reset state
            nicknameInput.classList.remove('valid', 'invalid');
            // buyButton.disabled = true;
            feedbackMsg.textContent = '';

            // All modals now have yellow highlight box
            const isChampion = modalContext.classList.contains('champion-modal');
            const neutralColor = '#4a2c1d';

            feedbackMsg.style.color = neutralColor;

            clearTimeout(typingTimer);

            if (isValidFormat) {
                feedbackMsg.textContent = 'Verificando disponibilidade...';
                // Ensure visibility on yellow background
                feedbackMsg.style.color = '#d35400';

                typingTimer = setTimeout(() => {
                    // Simulate API check
                    const isAvailable = true;

                    if (isAvailable) {
                        nicknameInput.classList.add('valid');
                        buyButton.disabled = false;
                        feedbackMsg.textContent = '✓ Nick disponível';
                        feedbackMsg.style.color = '#27ae60'; // Darker green for visibility on yellow

                        if (avatarPreviewImg) updateAvatar(avatarPreviewImg, value);
                    } else {
                        nicknameInput.classList.add('invalid');
                        feedbackMsg.textContent = '✕ Nick indisponível';
                        feedbackMsg.style.color = '#e74c3c'; // Red
                    }
                }, doneTypingInterval);
            } else {
                if (value.length > 0) {
                    feedbackMsg.textContent = 'Formato inválido (3-16 caracteres, letras/números/_)';
                    feedbackMsg.style.color = '#e74c3c';
                }

                if (value === '') {
                    if (avatarPreviewImg) updateAvatar(avatarPreviewImg, 'Steve');
                }
            }
        });

        form.addEventListener('submit', (e) => {
            e.preventDefault();
            const nickname = nicknameInput.value.trim();
            const kitNameEl = modalContext.querySelector('.kit-title-modal');
            const kitName = kitNameEl ? kitNameEl.innerText.replace('KIT ', '') : 'VIP';

            // Simulação de compra
            const originalText = buyButton.textContent;
            buyButton.textContent = 'PROCESSANDO...';
            buyButton.disabled = true;

            setTimeout(() => {
                alert(`Redirecionando para pagamento do ${kitName} para: ${nickname}`);
                buyButton.textContent = 'CONTINUAR PARA PAGAMENTO';
                buyButton.disabled = false;
                closeModal(modalContext);
            }, 1500);
        });
    }

    function updateAvatar(imgElement, username) {
        imgElement.src = `https://mc-heads.net/body/${username}/right`;
    }

});
