/**
 * Spherix Clinic - Universal Floating Label Interactive Engine
 * Provides butter-smooth, accessible floating label animations across all
 * login, registration, password recovery, and auth forms.
 */
(function () {
    'use strict';

    function isStaticControl(input) {
        if (!input) return false;
        const tag = input.tagName.toLowerCase();
        if (tag === 'select' || tag === 'textarea') return true;
        const type = (input.getAttribute('type') || 'text').toLowerCase();
        return ['file', 'date', 'datetime-local', 'time', 'checkbox', 'radio', 'color'].includes(type);
    }

    function checkHasValue(input) {
        if (!input) return false;
        // Check standard value
        if (input.value && input.value.trim().length > 0) return true;
        // Check placeholder-shown pseudo match via CSS or native check
        if (input.matches && input.matches(':-webkit-autofill')) return true;
        return false;
    }

    function updateWrapState(wrap) {
        const input = wrap.querySelector('.minimal-input, .floating-input, input, select, textarea');
        if (!input) return;

        if (isStaticControl(input)) {
            if (!wrap.classList.contains('static-label')) {
                wrap.classList.add('static-label');
            }
            return;
        }

        const hasVal = checkHasValue(input);
        const curHasVal = wrap.classList.contains('has-val');
        if (curHasVal !== hasVal) {
            wrap.classList.toggle('has-val', hasVal);
        }

        const label = wrap.querySelector('.minimal-label, .floating-label, label');
        if (label) {
            const curActive = label.classList.contains('floating-active');
            if (curActive !== hasVal) {
                label.classList.toggle('floating-active', hasVal);
            }
        }
    }

    function bindWrap(wrap) {
        const input = wrap.querySelector('.minimal-input, .floating-input, input, select, textarea');
        const label = wrap.querySelector('.minimal-label, .floating-label, label');
        if (!input) return;

        if (isStaticControl(input)) {
            if (!wrap.classList.contains('static-label')) {
                wrap.classList.add('static-label');
            }
            return;
        }

        // When label is clicked, ensure the input is explicitly focused
        if (label && !label.dataset.floatingBound) {
            label.dataset.floatingBound = 'true';
            label.addEventListener('click', function () {
                input.focus();
            });
        }

        // Bind input focus/blur/input events
        if (!input.dataset.floatingBound) {
            input.dataset.floatingBound = 'true';

            input.addEventListener('focus', function () {
                wrap.classList.add('is-focused');
                if (label) label.classList.add('is-focused');
            });

            input.addEventListener('blur', function () {
                wrap.classList.remove('is-focused');
                if (label) label.classList.remove('is-focused');
                updateWrapState(wrap);
            });

            input.addEventListener('input', function () {
                updateWrapState(wrap);
            });

            input.addEventListener('change', function () {
                updateWrapState(wrap);
            });
        }

        updateWrapState(wrap);
    }

    let isScheduled = false;
    function scheduleInit() {
        if (isScheduled) return;
        isScheduled = true;
        if (typeof window.requestAnimationFrame === 'function') {
            window.requestAnimationFrame(function () {
                isScheduled = false;
                initAll();
            });
        } else {
            setTimeout(function () {
                isScheduled = false;
                initAll();
            }, 16);
        }
    }

    function initAll() {
        const wraps = document.querySelectorAll('.minimal-input-wrap, .floating-input-wrap, .minimal-auth-input-group');
        for (let i = 0; i < wraps.length; i++) {
            bindWrap(wraps[i]);
        }
    }

    // Lifecycle hooks
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', scheduleInit);
    } else {
        scheduleInit();
    }

    window.addEventListener('load', function () {
        scheduleInit();
        setTimeout(scheduleInit, 100);
        setTimeout(scheduleInit, 400);
        setTimeout(scheduleInit, 1000);
    });

    window.addEventListener('pageshow', scheduleInit);

    // Watch for dynamic elements added to the DOM (child additions only, safe from loops)
    if (typeof MutationObserver !== 'undefined') {
        const observer = new MutationObserver(function (mutations) {
            let hasAddedNodes = false;
            for (let i = 0; i < mutations.length; i++) {
                if (mutations[i].addedNodes && mutations[i].addedNodes.length > 0) {
                    hasAddedNodes = true;
                    break;
                }
            }
            if (hasAddedNodes) {
                scheduleInit();
            }
        });

        const startObserver = function () {
            if (document.body) {
                observer.observe(document.body, {
                    childList: true,
                    subtree: true
                });
            }
        };

        if (document.body) {
            startObserver();
        } else {
            document.addEventListener('DOMContentLoaded', startObserver);
        }
    }
})();
