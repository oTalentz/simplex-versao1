class PaymentSelector {
    constructor(container, onSelect) {
        this.container = container;
        this.onSelect = onSelect;
        this.selectedMethod = null;
        this.render();
    }

    render() {
        this.container.innerHTML = `
            <div class="payment-selector" role="radiogroup" aria-label="Forma de Pagamento">
                <button type="button" class="payment-option" data-method="pix" role="radio" aria-checked="false" tabindex="0">
                    <i class="fa-brands fa-pix payment-icon"></i>
                    <span>PIX</span>
                </button>
                <button type="button" class="payment-option" data-method="credit_card" role="radio" aria-checked="false" tabindex="0">
                    <i class="fa-sharp fa-solid fa-credit-card payment-icon"></i>
                    <span>CARTÃO</span>
                </button>
            </div>
        `;

        this.options = this.container.querySelectorAll('.payment-option');
        this.options.forEach(option => {
            option.addEventListener('click', () => this.select(option.dataset.method));
            // Keydown support for accessibility
            option.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.select(option.dataset.method);
                }
            });
        });
    }

    select(method) {
        this.selectedMethod = method;
        this.options.forEach(opt => {
            const isSelected = opt.dataset.method === method;
            opt.classList.toggle('selected', isSelected);
            opt.setAttribute('aria-checked', isSelected);
        });
        if (this.onSelect) this.onSelect(method);
    }

    getSelectedMethod() {
        return this.selectedMethod;
    }
}

// Export for testing if module environment, otherwise global
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PaymentSelector;
} else {
    window.PaymentSelector = PaymentSelector;
}
