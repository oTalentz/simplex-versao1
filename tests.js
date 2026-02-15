
// Simple Unit Tests for VIP Modal Functionality

const runTests = () => {
    console.log('%c RUNNING TESTS ', 'background: #222; color: #bada55');
    let passed = 0;
    let failed = 0;

    const assert = (condition, message) => {
        if (condition) {
            console.log(`✅ PASS: ${message}`);
            passed++;
        } else {
            console.error(`❌ FAIL: ${message}`);
            failed++;
        }
    };

    // Test 1: Check if Modals exist
    const modals = ['modal-kit-lord', 'modal-kit-knight', 'modal-kit-guardian', 'modal-kit-champion'];
    modals.forEach(id => {
        const el = document.getElementById(id);
        assert(el !== null, `Modal #${id} exists in DOM`);
    });

    // Test 2: Check Installment Calculation Text - REMOVED per user request
    const lordInstallmentText = document.querySelector('#modal-kit-lord .installment-text');
    assert(lordInstallmentText === null, 'Installment text successfully removed');

    // Test 3: Check Countdown Timer
    const timer = document.getElementById('countdown-timer');
    if (timer) {
        assert(timer.innerText.includes(':'), 'Countdown timer has valid format');
    }

    // Test 4: Check Buttons Removed
    const giftBtns = document.querySelectorAll('.btn-gift');
    assert(giftBtns.length === 0, 'Gift buttons removed');

    const compareBtns = document.querySelectorAll('.btn-compare');
    assert(compareBtns.length === 0, 'Compare buttons removed');

    // Test 5: Check Skin Selectors Simplification
    // Should still have skin-selector div but only one option or just "Nick"
    const skinOptions = document.querySelectorAll('.skin-opt');
    // We expect 4 active options (one per modal) if we kept just the Nick button
    // Or 0 if we removed buttons entirely.
    // In my edit, I kept one button per modal: <button type="button" class="skin-opt active" data-type="nick">Nick</button>
    assert(skinOptions.length === 4, 'Only "Nick" skin option remains (1 per modal)');

    // Test 6: Check Origin Realms Style Elements
    const originInputs = document.querySelectorAll('.origin-input');
    assert(originInputs.length >= 4, 'Origin inputs present (at least 4)');

    const originBtns = document.querySelectorAll('.origin-btn');
    assert(originBtns.length >= 4, 'Origin buttons present (at least 4)');

    const helpSections = document.querySelectorAll('.help-text-section');
    assert(helpSections.length >= 4, 'Help text sections present (at least 4)');

    // Test 7: Check Checkout Section
    const checkoutSections = document.querySelectorAll('.checkout-section');
    assert(checkoutSections.length >= 4, 'Checkout sections present (at least 4)');

    const totalPrices = document.querySelectorAll('.total-price');
    assert(totalPrices.length >= 4, 'Total prices displayed (at least 4)');

    // Test 8: Check Title/Subtitle Structure (New Mold)
    const kitTitles = document.querySelectorAll('.modal-highlight-box .kit-title-modal');
    assert(kitTitles.length >= 4, 'Kit titles inside highlight box (at least 4)');

    const kitSubtitles = document.querySelectorAll('.modal-highlight-box .kit-subtitle-modal');
    assert(kitSubtitles.length >= 4, 'Kit subtitles inside highlight box (at least 4)');

    // Test 9: Check Benefits List Removed (Per User Request)
    const benefitsLists = document.querySelectorAll('.benefits-list');
    assert(benefitsLists.length === 0, 'Benefits lists successfully removed from all modals');

    console.log(`%c TESTS COMPLETED: ${passed} Passed, ${failed} Failed `, 'background: #222; color: #fff');
};

// Expose to window for manual run
window.runVipTests = runTests;

// Run automatically after a delay to ensure DOM load
setTimeout(runTests, 2000);
