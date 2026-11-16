/* Mensajes compartidos: toasts y diálogo de confirmación. */

(function () {
    const STYLES = {
        success: { name: 'Listo' },
        error: { name: 'Error' },
        warning: { name: 'Atención' },
        info: { name: 'Aviso' }
    };

    const ICONS = {
        success: '<path d="M20 6 9 17l-5-5"/>',
        error: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
        warning: '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
        info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>'
    };

    // Los estilos van en CSS propio: el CDN de Tailwind no genera clases que
    // aparecen recién cuando se crea el toast o el diálogo.
    const CSS = `
        #toast-container {
            position: fixed; right: 1rem; bottom: 1rem; z-index: 50;
            display: flex; flex-direction: column; align-items: flex-end; gap: 0.5rem;
        }
        .ui-toast {
            pointer-events: auto; display: flex; align-items: flex-start; gap: 0.75rem;
            width: 22rem; max-width: calc(100vw - 2rem);
            padding: 0.75rem 1rem; border-radius: 1rem; border: 1px solid;
            box-shadow: 0 20px 40px -20px rgba(0, 0, 0, 0.8);
            backdrop-filter: blur(4px);
            transform: translateY(0.75rem);
            transition: transform 0.3s ease, opacity 0.3s ease;
        }
        .ui-toast.is-visible { transform: none; opacity: 1; }
        .ui-toast.is-hiding { transform: translateY(0.5rem); opacity: 0; }
        .ui-toast__icon {
            display: flex; align-items: center; justify-content: center;
            width: 2.25rem; height: 2.25rem; flex-shrink: 0;
            margin-top: 0.125rem; border-radius: 9999px; color: #fff;
        }
        .ui-toast__body { min-width: 0; flex: 1; }
        .ui-toast__label {
            margin: 0; font-size: 11px; font-weight: 700;
            letter-spacing: 0.18em; text-transform: uppercase;
        }
        .ui-toast__text {
            margin: 0.25rem 0 0; font-size: 0.875rem; line-height: 1.35;
            word-break: break-word;
        }
        .ui-toast__close {
            flex-shrink: 0; padding: 0.25rem; border: 0; border-radius: 0.375rem;
            background: transparent; color: rgba(255, 255, 255, 0.5); cursor: pointer;
            transition: background 0.15s ease, color 0.15s ease;
        }
        .ui-toast__close:hover { background: rgba(255, 255, 255, 0.1); color: #fff; }

        .ui-toast--success { background: rgba(2, 44, 34, 0.96); border-color: rgba(4, 120, 87, 0.6); }
        .ui-toast--success .ui-toast__icon { background: #10b981; }
        .ui-toast--success .ui-toast__label { color: #6ee7b7; }
        .ui-toast--success .ui-toast__text { color: #ecfdf5; }

        .ui-toast--error { background: rgba(69, 10, 10, 0.96); border-color: rgba(185, 28, 28, 0.6); }
        .ui-toast--error .ui-toast__icon { background: #ef4444; }
        .ui-toast--error .ui-toast__label { color: #fca5a5; }
        .ui-toast--error .ui-toast__text { color: #fef2f2; }

        .ui-toast--warning { background: rgba(69, 26, 3, 0.96); border-color: rgba(217, 119, 6, 0.6); }
        .ui-toast--warning .ui-toast__icon { background: #f59e0b; }
        .ui-toast--warning .ui-toast__label { color: #fcd34d; }
        .ui-toast--warning .ui-toast__text { color: #fffbeb; }

        .ui-toast--info { background: rgba(23, 23, 23, 0.96); border-color: rgba(67, 56, 202, 0.6); }
        .ui-toast--info .ui-toast__icon { background: #6366f1; }
        .ui-toast--info .ui-toast__label { color: #a5b4fc; }
        .ui-toast--info .ui-toast__text { color: #f5f5f5; }

        .ui-overlay {
            position: fixed; inset: 0; z-index: 60;
            display: flex; align-items: center; justify-content: center;
            padding: 1rem; background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(4px);
            transition: opacity 0.15s ease;
        }
        .ui-dialog {
            width: 100%; max-width: 28rem;
            background: #171717; border: 1px solid #404040; border-radius: 1rem;
            padding: 1.5rem; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6);
            transition: transform 0.15s ease, opacity 0.15s ease;
        }
        .ui-overlay.is-closing { opacity: 0; }
        .ui-overlay.is-closing .ui-dialog { transform: scale(0.96); opacity: 0; }
        .ui-dialog__head { display: flex; align-items: flex-start; gap: 0.75rem; }
        .ui-dialog__badge {
            display: flex; align-items: center; justify-content: center;
            width: 2.5rem; height: 2.5rem; flex-shrink: 0; border-radius: 9999px;
        }
        .ui-dialog__badge--danger { background: rgba(239, 68, 68, 0.15); color: #f87171; }
        .ui-dialog__badge--info { background: rgba(99, 102, 241, 0.15); color: #818cf8; }
        .ui-dialog__title {
            margin: 0.375rem 0 0; font-size: 1rem; font-weight: 600; color: #fff;
        }
        .ui-dialog__text {
            margin: 0.75rem 0 0; font-size: 0.875rem; line-height: 1.5; color: #a3a3a3;
        }
        .ui-dialog__actions {
            display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 1.5rem;
        }
        .ui-btn {
            padding: 0.5rem 1rem; border: 1px solid transparent; border-radius: 0.5rem;
            font-size: 0.875rem; font-weight: 500; cursor: pointer;
            transition: background 0.15s ease, border-color 0.15s ease;
        }
        .ui-btn:focus-visible, .ui-toast__close:focus-visible {
            outline: 2px solid #818cf8; outline-offset: 2px;
        }
        .ui-btn--ghost { background: transparent; border-color: #404040; color: #e5e5e5; }
        .ui-btn--ghost:hover { background: #262626; }
        .ui-btn--danger { background: #dc2626; color: #fff; font-weight: 600; }
        .ui-btn--danger:hover { background: #ef4444; }
        .ui-btn--primary { background: #4f46e5; color: #fff; font-weight: 600; }
        .ui-btn--primary:hover { background: #6366f1; }
    `;

    if (!document.getElementById('ui-styles')) {
        const style = document.createElement('style');
        style.id = 'ui-styles';
        style.textContent = CSS;
        document.head.append(style);
    }

    function svg(paths, size) {
        return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">${paths}</svg>`;
    }

    function toastContainer() {
        let box = document.getElementById('toast-container');
        if (!box) {
            box = document.createElement('div');
            box.id = 'toast-container';
            document.body.append(box);
        }
        return box;
    }

    function showToast(message, type = 'success') {
        const kind = STYLES[type] ? type : 'info';

        const toast = document.createElement('div');
        toast.className = `ui-toast ui-toast--${kind}`;
        toast.setAttribute('role', 'status');

        const icon = document.createElement('span');
        icon.className = 'ui-toast__icon';
        icon.innerHTML = svg(ICONS[kind], 18);

        const body = document.createElement('div');
        body.className = 'ui-toast__body';
        const label = document.createElement('p');
        label.className = 'ui-toast__label';
        label.textContent = STYLES[kind].name;
        const text = document.createElement('p');
        text.className = 'ui-toast__text';
        text.textContent = message;
        body.append(label, text);

        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'ui-toast__close';
        close.setAttribute('aria-label', 'Cerrar mensaje');
        close.innerHTML = svg('<path d="M18 6 6 18"/><path d="m6 6 12 12"/>', 14);

        let timer = 0;
        function dismiss() {
            clearTimeout(timer);
            toast.classList.add('is-hiding');
            setTimeout(() => toast.remove(), 250);
        }
        close.addEventListener('click', dismiss);

        toast.append(icon, body, close);
        toastContainer().append(toast);
        void toast.offsetWidth;  // fuerza el reflow antes de activar la transición
        toast.classList.add('is-visible');

        timer = setTimeout(dismiss, kind === 'error' || kind === 'warning' ? 6000 : 4000);
        return toast;
    }

    function confirmDialog({
        title = 'Confirmar',
        message = '',
        confirmLabel = 'Aceptar',
        cancelLabel = 'Cancelar',
        danger = true
    } = {}) {
        return new Promise((resolve) => {
            let closed = false;

            const overlay = document.createElement('div');
            overlay.className = 'ui-overlay';

            const dialog = document.createElement('div');
            dialog.className = 'ui-dialog';
            dialog.setAttribute('role', 'dialog');
            dialog.setAttribute('aria-modal', 'true');
            dialog.setAttribute('aria-labelledby', 'ui-dialog-title');
            dialog.setAttribute('aria-describedby', 'ui-dialog-text');

            const head = document.createElement('div');
            head.className = 'ui-dialog__head';
            const badge = document.createElement('span');
            badge.className = `ui-dialog__badge ${danger ? 'ui-dialog__badge--danger' : 'ui-dialog__badge--info'}`;
            badge.innerHTML = svg(ICONS.warning, 20);
            const heading = document.createElement('h2');
            heading.id = 'ui-dialog-title';
            heading.className = 'ui-dialog__title';
            heading.textContent = title;
            head.append(badge, heading);

            const text = document.createElement('p');
            text.id = 'ui-dialog-text';
            text.className = 'ui-dialog__text';
            text.textContent = message;

            const actions = document.createElement('div');
            actions.className = 'ui-dialog__actions';

            const cancel = document.createElement('button');
            cancel.type = 'button';
            cancel.className = 'ui-btn ui-btn--ghost';
            cancel.textContent = cancelLabel;

            const accept = document.createElement('button');
            accept.type = 'button';
            accept.className = `ui-btn ${danger ? 'ui-btn--danger' : 'ui-btn--primary'}`;
            accept.textContent = confirmLabel;

            function close(result) {
                if (closed) return;
                closed = true;
                document.removeEventListener('keydown', onKey);
                document.body.classList.remove('overflow-hidden');
                overlay.classList.add('is-closing');
                setTimeout(() => {
                    overlay.remove();
                    resolve(result);
                }, 150);
            }

            function onKey(event) {
                if (event.key === 'Escape') {
                    event.preventDefault();
                    close(false);
                }
            }

            cancel.addEventListener('click', () => close(false));
            accept.addEventListener('click', () => close(true));
            overlay.addEventListener('mousedown', (event) => {
                if (event.target === overlay) close(false);
            });
            document.addEventListener('keydown', onKey);

            actions.append(cancel, accept);
            dialog.append(head, text, actions);
            overlay.append(dialog);
            document.body.append(overlay);
            document.body.classList.add('overflow-hidden');
            accept.focus();
        });
    }

    window.showToast = showToast;
    window.confirmDialog = confirmDialog;
})();
