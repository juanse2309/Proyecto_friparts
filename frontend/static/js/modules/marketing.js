/**
 * marketing.js — Módulo de control para el panel de Campañas Push B2B
 * Conecta la interfaz marketing_push.html con el endpoint /api/pwa/broadcast
 */

(function () {
    'use strict';

    const form = document.getElementById('formBroadcast');
    const btn = document.getElementById('mkt-submit');
    const alertBox = document.getElementById('mktAlert');
    const alertIcon = document.getElementById('mktAlertIcon');
    const alertText = document.getElementById('mktAlertText');
    const imageInput = document.getElementById('mkt-image');
    const preview = document.getElementById('mkt-preview');
    const previewImg = document.getElementById('mkt-preview-img');

    // ─── Vista previa de imagen en tiempo real ──────────────────────
    imageInput.addEventListener('input', () => {
        const url = imageInput.value.trim();
        if (url) {
            previewImg.src = url;
            previewImg.onload = () => preview.classList.add('visible');
            previewImg.onerror = () => preview.classList.remove('visible');
        } else {
            preview.classList.remove('visible');
        }
    });

    // ─── Enviar formulario ──────────────────────────────────────────
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        ocultarAlerta();

        const titulo = document.getElementById('mkt-titulo').value.trim();
        const cuerpo = document.getElementById('mkt-cuerpo').value.trim();
        const url_destino = document.getElementById('mkt-url').value.trim() || '/';
        const image_url = imageInput.value.trim() || null;
        const destino = document.getElementById('mkt-destino').value;

        if (!cuerpo) {
            mostrarAlerta('error', 'fa-circle-exclamation', 'El campo Mensaje es obligatorio.');
            return;
        }

        setLoading(true);

        try {
            const response = await fetch('/api/pwa/broadcast', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ titulo, cuerpo, url_destino, image_url, destino })
            });

            const data = await response.json();

            if (response.status === 202) {
                mostrarAlerta('success', 'fa-circle-check', '¡Campaña encolada! Las notificaciones se están enviando en segundo plano.');
                form.reset();
                preview.classList.remove('visible');
            } else if (response.status === 403) {
                mostrarAlerta('error', 'fa-lock', 'Acceso denegado. Tu rol no tiene permisos de Marketing.');
            } else {
                mostrarAlerta('error', 'fa-circle-exclamation', data.message || 'Error desconocido.');
            }
        } catch (err) {
            mostrarAlerta('error', 'fa-wifi', 'Error de red: ' + err.message);
        } finally {
            setLoading(false);
        }
    });

    // ─── Cargar métricas de debug ───────────────────────────────────
    async function cargarMetricas() {
        try {
            const res = await fetch('/api/pwa/debug/info');
            if (!res.ok) return;
            const data = await res.json();
            if (data.success && data.metrics) {
                document.getElementById('stat-subs').textContent = data.metrics.total_suscripciones || 0;
                const vapidOk = data.metrics.keys_status.public_key_loaded && data.metrics.keys_status.private_key_loaded;
                const statVapid = document.getElementById('stat-vapid');
                statVapid.textContent = vapidOk ? '✓ OK' : '✗ Error';
                statVapid.style.color = vapidOk ? 'var(--mkt-success)' : 'var(--mkt-danger)';
            }
        } catch (_) {
            // Silenciar errores de métricas (no críticas)
        }
    }

    // ─── Helpers ────────────────────────────────────────────────────
    function setLoading(state) {
        btn.disabled = state;
        if (state) {
            btn.classList.add('loading');
        } else {
            btn.classList.remove('loading');
        }
    }

    function mostrarAlerta(tipo, iconClass, mensaje) {
        alertBox.className = 'mkt-alert visible ' + tipo;
        alertIcon.className = 'fas ' + iconClass;
        alertText.textContent = mensaje;
    }

    function ocultarAlerta() {
        alertBox.className = 'mkt-alert';
    }

    // Inicializar
    cargarMetricas();
})();
