// Minimal DOM Mock for Node.js environment
// This allows running tests without jsdom or browser
const mockDOM = () => {
    class ClassList {
        constructor() { this.classes = new Set(); }
        add(c) { this.classes.add(c); }
        remove(c) { this.classes.delete(c); }
        toggle(c, force) {
            if (force === true) this.add(c);
            else if (force === false) this.remove(c);
            else if (this.contains(c)) this.remove(c);
            else this.add(c);
        }
        contains(c) { return this.classes.has(c); }
    }

    class Element {
        constructor(tagName) {
            this.tagName = tagName;
            this.classList = new ClassList();
            this.dataset = {};
            this.attributes = {};
            this.children = [];
            this.parentNode = null;
            this.listeners = {};
            this._innerHTML = '';
        }

        get innerHTML() { return this._innerHTML; }
        set innerHTML(html) {
            this._innerHTML = html;
            // Very basic parser for test purposes
            this.children = [];
            // Find payment-option divs
            const matches = html.matchAll(/class="payment-option"[^>]*data-method="([^"]+)"/g);
            for (const match of matches) {
                const el = new Element('div');
                el.classList.add('payment-option');
                el.dataset.method = match[1];
                el.parentNode = this;
                this.children.push(el);
            }
        }

        setAttribute(k, v) { this.attributes[k] = v; }
        getAttribute(k) { return this.attributes[k]; }

        addEventListener(event, callback) {
            if (!this.listeners[event]) this.listeners[event] = [];
            this.listeners[event].push(callback);
        }

        click() {
            if (this.listeners['click']) this.listeners['click'].forEach(cb => cb());
        }

        querySelector(selector) {
            if (selector.includes('[data-method="')) {
                const method = selector.match(/data-method="([^"]+)"/)[1];
                return this.children.find(c => c.dataset.method === method);
            }
            return null;
        }

        querySelectorAll(selector) {
            if (selector === '.payment-option') {
                return this.children; // Already filtered in mock parser
            }
            return [];
        }
    }

    global.document = {
        createElement: (tag) => new Element(tag),
        getElementById: (id) => new Element('div')
    };
    global.window = {};
};

// Initialize Mock
mockDOM();

// Import Component (which uses global.document)
const PaymentSelector = require('./payment-selector.js');
const assert = require('assert');

console.log('Running PaymentSelector Tests (with Mock DOM)...');

// Test 1: Render
try {
    const container = document.getElementById('container');
    const selector = new PaymentSelector(container, () => { });

    // Check if innerHTML was set
    assert.ok(container.innerHTML.includes('class="payment-selector"'), 'Should render main container');
    assert.ok(container.innerHTML.includes('data-method="pix"'), 'Should render PIX option');
    assert.ok(container.innerHTML.includes('data-method="credit_card"'), 'Should render Card option');

    console.log('✓ Test 1 Passed: Component renders HTML structure');
} catch (e) {
    console.error('✗ Test 1 Failed:', e.message);
}

// Test 2: Selection Logic
try {
    const container = document.getElementById('container');
    let selectedValue = null;
    const selector = new PaymentSelector(container, (val) => {
        selectedValue = val;
    });

    // Simulate finding elements (since our mock parser is very basic)
    const options = container.querySelectorAll('.payment-option');
    assert.strictEqual(options.length, 2, 'Should have 2 options parsed');

    const pixOption = options.find(o => o.dataset.method === 'pix');
    const cardOption = options.find(o => o.dataset.method === 'credit_card');

    // Test Click PIX
    pixOption.click();
    assert.strictEqual(selectedValue, 'pix', 'Clicking PIX should update callback value');
    assert.strictEqual(selector.getSelectedMethod(), 'pix', 'getSelectedMethod should return pix');
    assert.ok(pixOption.classList.contains('selected'), 'PIX option should have selected class');
    assert.ok(!cardOption.classList.contains('selected'), 'Card option should NOT have selected class');

    // Test Click Card
    cardOption.click();
    assert.strictEqual(selectedValue, 'credit_card', 'Clicking Card should update callback value');
    assert.strictEqual(selector.getSelectedMethod(), 'credit_card', 'getSelectedMethod should return credit_card');
    assert.ok(!pixOption.classList.contains('selected'), 'PIX option should NOT have selected class');
    assert.ok(cardOption.classList.contains('selected'), 'Card option should have selected class');

    console.log('✓ Test 2 Passed: Selection logic works correctly');
} catch (e) {
    console.error('✗ Test 2 Failed:', e.message);
}

console.log('All tests completed.');
