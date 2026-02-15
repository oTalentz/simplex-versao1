document.addEventListener('DOMContentLoaded', () => {
    // --- CONFIGURATION ---
    const API_BASE_URL = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
        ? 'http://localhost:5000'
        : '/api';

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
        const emailInput = modalContext.querySelector('.email-input');
        const cpfInput = modalContext.querySelector('.cpf-input');
        // Cellphone removed
        // Update selector to include origin-btn
        const buyButton = modalContext.querySelector('.btn-buy-footer');
        const form = modalContext.querySelector('.purchase-form');
        const avatarPreviewImg = modalContext.querySelector('.avatar-preview-img');

        let typingTimer;
        const doneTypingInterval = 800;

        if (!nicknameInput || !buyButton || !form) return;

        // Helper to create feedback element
        const createFeedback = (input, className) => {
            let feedback = modalContext.querySelector(`.${className}`);
            if (!feedback) {
                feedback = document.createElement('div');
                feedback.className = className;
                feedback.style.fontSize = '0.8rem';
                feedback.style.marginTop = '5px';
                feedback.style.height = '1.2em';
                input.parentNode.insertBefore(feedback, input.nextSibling);
            }
            return feedback;
        };

        const nickFeedback = createFeedback(nicknameInput, 'nick-feedback');
        const emailFeedback = emailInput ? createFeedback(emailInput, 'email-feedback') : null;
        const cpfFeedback = cpfInput ? createFeedback(cpfInput, 'cpf-feedback') : null;

        // Validation State
        const validationState = {
            nick: false,
            email: false,
            cpf: false,
            paymentMethod: false
        };

        const updateButtonState = () => {
            const isValid = validationState.nick &&
                (!emailInput || validationState.email) &&
                (!cpfInput || validationState.cpf) &&
                validationState.paymentMethod;
            buyButton.disabled = !isValid;
        };

        // Payment Selector Integration
        let paymentSelectorInstance;
        const paymentContainer = modalContext.querySelector('.payment-selector-container');
        if (paymentContainer && window.PaymentSelector) {
            paymentSelectorInstance = new window.PaymentSelector(paymentContainer, (method) => {
                validationState.paymentMethod = !!method;
                updateButtonState();
            });
        }

        // Nickname Validation
        nicknameInput.addEventListener('input', () => {
            const value = nicknameInput.value.trim();
            const isValidFormat = /^[a-zA-Z0-9_]{3,16}$/.test(value);

            nicknameInput.classList.remove('valid', 'invalid');
            nickFeedback.textContent = '';
            nickFeedback.style.color = '#4a2c1d'; // Neutral

            clearTimeout(typingTimer);
            validationState.nick = false;
            updateButtonState();

            if (isValidFormat) {
                nickFeedback.textContent = 'Verificando disponibilidade...';
                nickFeedback.style.color = '#d35400';

                typingTimer = setTimeout(() => {
                    // Simulate API check
                    const isAvailable = true; // Mock availability

                    if (isAvailable) {
                        nicknameInput.classList.add('valid');
                        nickFeedback.textContent = '✓ Nick disponível';
                        nickFeedback.style.color = '#27ae60';
                        validationState.nick = true;
                        if (avatarPreviewImg) updateAvatar(avatarPreviewImg, value);
                    } else {
                        nicknameInput.classList.add('invalid');
                        nickFeedback.textContent = '✕ Nick indisponível';
                        nickFeedback.style.color = '#e74c3c';
                        validationState.nick = false;
                    }
                    updateButtonState();
                }, doneTypingInterval);
            } else {
                if (value.length > 0) {
                    nickFeedback.textContent = 'Formato inválido (3-16 caracteres, letras/números/_)';
                    nickFeedback.style.color = '#e74c3c';
                }
                if (value === '' && avatarPreviewImg) updateAvatar(avatarPreviewImg, 'Steve');
            }
        });

        // Email Validation
        if (emailInput) {
            emailInput.addEventListener('input', () => {
                const value = emailInput.value.trim();
                const isValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);

                emailInput.classList.remove('valid', 'invalid');
                emailFeedback.textContent = '';

                if (isValid) {
                    emailInput.classList.add('valid');
                    validationState.email = true;
                } else {
                    if (value.length > 0) {
                        emailInput.classList.add('invalid');
                        emailFeedback.textContent = 'E-mail inválido';
                        emailFeedback.style.color = '#e74c3c';
                    }
                    validationState.email = false;
                }
                updateButtonState();
            });
        }

        // CPF Validation
        if (cpfInput) {
            cpfInput.addEventListener('input', () => {
                let value = cpfInput.value.replace(/\D/g, ''); // Remove non-digits
                if (value.length > 11) value = value.slice(0, 11);
                cpfInput.value = value;

                const isValid = value.length === 11;

                cpfInput.classList.remove('valid', 'invalid');
                cpfFeedback.textContent = '';

                if (isValid) {
                    cpfInput.classList.add('valid');
                    validationState.cpf = true;
                } else {
                    if (value.length > 0) {
                        cpfInput.classList.add('invalid');
                        cpfFeedback.textContent = 'CPF deve ter 11 dígitos';
                        cpfFeedback.style.color = '#e74c3c';
                    }
                    validationState.cpf = false;
                }
                updateButtonState();
            });
        }

        // Cellphone Validation Removed


        // Handle Enter key in form
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            if (!buyButton.disabled) buyButton.click();
        });

        // Helper to show PIX Modal
        const showPixModal = (modal, pixData) => {
            const highlightBox = modal.querySelector('.modal-highlight-box');
            const checkoutSection = modal.querySelector('.checkout-section');
            const footerSection = modal.querySelector('.checkout-footer');
            const helpSection = modal.querySelector('.help-text-section');
            const comparisonSection = modal.querySelector('.comparison-section-container');
            const topBar = modal.querySelector('.modal-top-bar');
            const countdownBanner = modal.querySelector('.countdown-banner');

            // Hide other sections
            if (checkoutSection) checkoutSection.style.display = 'none';
            if (footerSection) footerSection.style.display = 'none';
            if (helpSection) helpSection.style.display = 'none';
            if (comparisonSection) comparisonSection.style.display = 'none';
            if (countdownBanner) countdownBanner.style.display = 'none';

            // Ensure base64 prefix
            const base64Src = pixData.brCodeBase64.startsWith('data:')
                ? pixData.brCodeBase64
                : `data:image/png;base64,${pixData.brCodeBase64}`;

            // Update Highlight Box with PIX Content
            highlightBox.innerHTML = `
                <div class="pix-container" style="color: #eee;">
                    <div class="pix-title" style="color: #ffc107; font-weight: 900; font-size: 1.5rem; text-shadow: 2px 2px 0px rgba(0,0,0,0.8); margin-bottom: 15px; font-family: 'Press Start 2P', cursive;">PAGAMENTO VIA PIX</div>
                    <div style="background: white; padding: 10px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.5);">
                        <img src="${base64Src}" alt="QR Code PIX" class="pix-qr-image" style="width: 200px; height: 200px; display: block;">
                    </div>
                    
                    <p class="pix-instructions" style="color: #ddd; font-weight: 500; margin-top: 15px; text-align: center; line-height: 1.6; font-size: 0.9rem;">
                        1. Abra o app do seu banco.<br>
                        2. Escolha pagar via PIX > Ler QR Code.<br>
                        3. Escaneie a imagem ou cole o código abaixo.
                    </p>

                    <div class="pix-copy-container" style="display: flex; gap: 10px; margin-top: 15px; width: 100%; max-width: 400px;">
                        <input type="text" class="pix-copy-input" value="${pixData.brCode}" readonly style="flex: 1; padding: 10px; border: 1px solid #444; border-radius: 6px; font-weight: bold; color: #fff; background: #1a1a1a;">
                        <button class="pix-copy-btn" title="Copiar Código" style="background: #ffc107; color: #000; border: none; padding: 0 20px; font-weight: bold; border-radius: 6px; cursor: pointer; font-family: 'Press Start 2P', cursive; font-size: 0.7rem;">
                            COPIAR
                        </button>
                    </div>
                    
                    <div style="margin-top: 20px; color: #aaa; font-weight: 500; font-size: 0.8rem; text-align: center; background: rgba(0,0,0,0.3); padding: 10px; border-radius: 6px; border: 1px solid #333;">
                        Após o pagamento, seu VIP será ativado automaticamente em até 5 minutos.
                    </div>
                </div>
            `;

            // Re-style highlight box for better fit and dark theme
            highlightBox.style.background = '#111';
            highlightBox.style.border = '1px solid #333';
            highlightBox.style.flexDirection = 'column';
            highlightBox.style.height = 'auto';
            highlightBox.style.padding = '20px';

            // Add Copy Functionality
            const copyBtn = highlightBox.querySelector('.pix-copy-btn');
            const copyInput = highlightBox.querySelector('.pix-copy-input');

            if (copyBtn && copyInput) {
                copyBtn.addEventListener('click', () => {
                    copyInput.select();
                    copyInput.setSelectionRange(0, 99999); // Mobile
                    navigator.clipboard.writeText(copyInput.value).then(() => {
                        const originalText = copyBtn.textContent;
                        copyBtn.textContent = 'COPIADO!';
                        copyBtn.style.background = '#27ae60';
                        setTimeout(() => {
                            copyBtn.textContent = originalText;
                            copyBtn.style.background = '';
                        }, 2000);
                    }).catch(err => {
                        console.error('Failed to copy: ', err);
                        // Fallback
                        document.execCommand('copy');
                        copyBtn.textContent = 'COPIADO!';
                    });
                });
            }
        };

        // Change from form submit to button click because button is outside form
        buyButton.addEventListener('click', async (e) => {
            e.preventDefault();

            if (buyButton.disabled) return;

            const selectedMethod = paymentSelectorInstance ? paymentSelectorInstance.getSelectedMethod() : null;

            if (selectedMethod === 'credit_card') {
                alert('Pagamento via Cartão de Crédito selecionado. Redirecionando para gateway seguro...');
                // Implement Card logic here
                return;
            }

            // Default to PIX logic below

            const nickname = nicknameInput.value.trim();
            const email = emailInput ? emailInput.value.trim() : '';
            const cpf = cpfInput ? cpfInput.value.trim() : '';
            // Cellphone removed
            const kitNameEl = modalContext.querySelector('.kit-title-modal');
            // Use data-product attribute if available, otherwise fallback to parsing text
            const kitName = kitNameEl ? (kitNameEl.getAttribute('data-product') || kitNameEl.innerText.replace('KIT ', '')) : 'VIP';

            const originalText = buyButton.textContent;
            buyButton.textContent = 'GERANDO PIX...';
            buyButton.disabled = true;

            try {
                // Use Transparent PIX Checkout
                const endpoint = `${API_BASE_URL}/create-pix-payment`;

                console.log(`Initiating PIX payment to ${endpoint}`);

                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        nickname,
                        email,
                        cpf,
                        product: kitName
                    })
                });

                const data = await response.json();

                if (response.ok) {
                    if (data.brCodeBase64) {
                        // Success! Show PIX QR Code inside modal
                        showPixModal(modalContext, data);
                    } else {
                        throw new Error('Dados do PIX não retornados.');
                    }
                } else {
                    throw new Error(data.error || 'Erro ao criar pagamento');
                }
            } catch (error) {
                console.error(error);
                alert('Erro ao processar pagamento: ' + error.message);
                buyButton.textContent = originalText;
                buyButton.disabled = false;
                // Force re-validation check to ensure button state is correct
                updateButtonState();
            }
        });

        // Initial button state check
        updateButtonState();
    }

    function updateAvatar(imgElement, username) {
        imgElement.src = `https://mc-heads.net/body/${username}/right`;
    }

});
