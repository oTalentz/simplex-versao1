class CreditCardComponent {
    constructor(container) {
        this.container = container;
        this.render();
        this.bindEvents();
    }

    render() {
        this.container.innerHTML = `
            <div class="credit-card-wrapper">
                <div class="cc-visual">
                    <div class="cc-visual-brand">CARD</div>
                    <div class="cc-visual-chip"></div>
                    <div class="cc-visual-number" id="cc-visual-number">•••• •••• •••• ••••</div>
                    <div class="cc-visual-bottom">
                        <div class="cc-visual-name" id="cc-visual-name">NOME NO CARTÃO</div>
                        <div class="cc-visual-expiry" id="cc-visual-expiry">MM/AA</div>
                    </div>
                </div>

                <div class="cc-input-group">
                    <label>Número do Cartão</label>
                    <input type="text" class="cc-input" id="cc-number" placeholder="0000 0000 0000 0000" maxlength="19" autocomplete="cc-number">
                    <span class="cc-error-msg">Número inválido</span>
                </div>
                
                <div class="cc-input-group">
                    <label>Nome no Cartão</label>
                    <input type="text" class="cc-input" id="cc-name" placeholder="Como impresso no cartão" autocomplete="cc-name">
                    <span class="cc-error-msg">Nome inválido</span>
                </div>

                <div class="cc-row">
                    <div class="cc-input-group">
                        <label>Validade</label>
                        <input type="text" class="cc-input" id="cc-expiry" placeholder="MM/AA" maxlength="5" autocomplete="cc-exp">
                        <span class="cc-error-msg">Data inválida</span>
                    </div>
                    <div class="cc-input-group">
                        <label>CVV</label>
                        <input type="password" class="cc-input" id="cc-cvv" placeholder="123" maxlength="4" autocomplete="cc-csc">
                        <span class="cc-error-msg">CVV inválido</span>
                    </div>
                </div>
            </div>
        `;

        this.wrapper = this.container.querySelector('.credit-card-wrapper');
        this.numberInput = this.container.querySelector('#cc-number');
        this.nameInput = this.container.querySelector('#cc-name');
        this.expiryInput = this.container.querySelector('#cc-expiry');
        this.cvvInput = this.container.querySelector('#cc-cvv');

        this.visualNumber = this.container.querySelector('#cc-visual-number');
        this.visualName = this.container.querySelector('#cc-visual-name');
        this.visualExpiry = this.container.querySelector('#cc-visual-expiry');
        this.visualBrand = this.container.querySelector('.cc-visual-brand');
    }

    bindEvents() {
        this.numberInput.addEventListener('input', (e) => {
            let value = e.target.value.replace(/\D/g, '');
            let formattedValue = '';
            for (let i = 0; i < value.length; i++) {
                if (i > 0 && i % 4 === 0) {
                    formattedValue += ' ';
                }
                formattedValue += value[i];
            }
            e.target.value = formattedValue;
            this.visualNumber.textContent = formattedValue || '•••• •••• •••• ••••';
            
            // Detect brand
            if (value.startsWith('4')) this.visualBrand.textContent = 'VISA';
            else if (value.startsWith('5')) this.visualBrand.textContent = 'MASTERCARD';
            else if (value.startsWith('3')) this.visualBrand.textContent = 'AMEX';
            else this.visualBrand.textContent = 'CARD';

            e.target.classList.remove('error');
        });

        this.nameInput.addEventListener('input', (e) => {
            let value = e.target.value.toUpperCase();
            this.visualName.textContent = value || 'NOME NO CARTÃO';
            e.target.classList.remove('error');
        });

        this.expiryInput.addEventListener('input', (e) => {
            let value = e.target.value.replace(/\D/g, '');
            if (value.length >= 2) {
                value = value.substring(0, 2) + '/' + value.substring(2, 4);
            }
            e.target.value = value;
            this.visualExpiry.textContent = value || 'MM/AA';
            e.target.classList.remove('error');
        });

        this.cvvInput.addEventListener('input', (e) => {
            e.target.value = e.target.value.replace(/\D/g, '');
            e.target.classList.remove('error');
        });
    }

    show() {
        this.wrapper.classList.add('active');
    }

    hide() {
        this.wrapper.classList.remove('active');
    }

    validate() {
        let isValid = true;

        if (this.numberInput.value.replace(/\s/g, '').length < 13) {
            this.numberInput.classList.add('error');
            isValid = false;
        }

        if (this.nameInput.value.trim().length < 3) {
            this.nameInput.classList.add('error');
            isValid = false;
        }

        if (this.expiryInput.value.length < 5) {
            this.expiryInput.classList.add('error');
            isValid = false;
        } else {
            const [month, year] = this.expiryInput.value.split('/');
            const now = new Date();
            const currentYear = parseInt(now.getFullYear().toString().substring(2));
            const currentMonth = now.getMonth() + 1;
            
            if (parseInt(month) < 1 || parseInt(month) > 12 || 
                parseInt(year) < currentYear || 
                (parseInt(year) === currentYear && parseInt(month) < currentMonth)) {
                this.expiryInput.classList.add('error');
                isValid = false;
            }
        }

        if (this.cvvInput.value.length < 3) {
            this.cvvInput.classList.add('error');
            isValid = false;
        }

        return isValid;
    }

    getCardData() {
        return {
            number: this.numberInput.value.replace(/\s/g, ''),
            name: this.nameInput.value.trim(),
            expiry: this.expiryInput.value,
            cvv: this.cvvInput.value
        };
    }
}

// Export for global usage
window.CreditCardComponent = CreditCardComponent;
