document.addEventListener('DOMContentLoaded', () => {
    const isLocalRuntime = window.location.protocol === 'file:' || !window.location.hostname || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    const API_BASE_URL = isLocalRuntime ? 'http://localhost:5000' : '/api';
    const refreshBtn = document.getElementById('btn-refresh');
    const timeFilter = document.getElementById('time-filter');
    const authGate = document.getElementById('auth-gate');
    const loginForm = document.getElementById('login-form');
    const loginError = document.getElementById('login-error');
    const sessionUser = document.getElementById('session-user');
    const logoutBtn = document.getElementById('btn-logout');
    let token = localStorage.getItem('simplex_admin_token') || '';
    let username = localStorage.getItem('simplex_admin_user') || '';

    function showAuthGate() {
        authGate.classList.remove('hidden');
    }

    function hideAuthGate() {
        authGate.classList.add('hidden');
    }

    function setSessionUserLabel() {
        sessionUser.textContent = username ? `Sessão: ${username}` : '';
    }

    async function apiFetch(path) {
        let response;
        try {
            response = await fetch(`${API_BASE_URL}${path}`, {
                headers: token ? { Authorization: `Bearer ${token}` } : {}
            });
        } catch {
            throw new Error('Não foi possível conectar ao backend em http://localhost:5000');
        }
        if (response.status === 401) {
            localStorage.removeItem('simplex_admin_token');
            localStorage.removeItem('simplex_admin_user');
            token = '';
            username = '';
            showAuthGate();
            throw new Error('Sessão expirada');
        }
        let data = {};
        try {
            data = await response.json();
        } catch {
            if (!response.ok) {
                throw new Error('Resposta inválida da API');
            }
        }
        if (!response.ok) {
            throw new Error(data.error || 'Falha na API');
        }
        return data;
    }

    async function validateSession() {
        if (!token) {
            showAuthGate();
            return false;
        }
        try {
            const data = await apiFetch('/auth/me');
            username = data.username || username;
            localStorage.setItem('simplex_admin_user', username);
            // Tab Switching Logic
    const tabs = document.querySelectorAll('.nav-item[data-tab]');
    const views = document.querySelectorAll('.view-section');

    tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            const target = tab.getAttribute('data-tab');

            // Update active tab
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // Update visible view
            views.forEach(view => {
                if (view.id === `view-${target}`) {
                    view.classList.remove('hidden');
                    view.style.display = 'block'; // Ensure visibility
                } else {
                    view.classList.add('hidden');
                    view.style.display = 'none'; // Ensure hidden
                }
            });
        });
    });

    // Pairing Logic
    const pairBtn = document.getElementById('btn-pair-server');
    const pairInput = document.getElementById('pairing-code');
    const pairStatus = document.getElementById('pairing-status');

    if (pairBtn) {
        pairBtn.addEventListener('click', async () => {
            const code = pairInput.value.trim().toUpperCase();
            if (!code) {
                pairStatus.textContent = 'Digite o código de pareamento.';
                pairStatus.className = 'status-text error';
                return;
            }

            pairStatus.textContent = 'Conectando...';
            pairStatus.className = 'status-text warning';
            pairBtn.disabled = true;

            try {
                const response = await fetch(`${API_BASE_URL}/admin/connector/claim`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({ code })
                });

                const data = await response.json();

                if (response.ok) {
                    pairStatus.textContent = `Servidor "${data.agent}" conectado com sucesso!`;
                    pairStatus.className = 'status-text ok';
                    pairInput.value = '';
                    await fetchStatus(); // Update status indicators
                } else {
                    throw new Error(data.error || 'Falha ao conectar servidor');
                }
            } catch (error) {
                pairStatus.textContent = error.message;
                pairStatus.className = 'status-text error';
            } finally {
                pairBtn.disabled = false;
            }
        });
    }

    setSessionUserLabel();
            hideAuthGate();
            return true;
        } catch {
            showAuthGate();
            return false;
        }
    }

    async function fetchStatus() {
        try {
            const data = await apiFetch('/admin/status');
            updateStatusUI('api', data.api_status);
            updateStatusUI('db', data.db_status);
            updateStatusUI('mc', data.mc_status);
            updateStatusUI('payment', data.payment_status);
        } catch {
            updateStatusUI('api', 'error');
            updateStatusUI('db', 'error');
        }
    }

    async function fetchStats() {
        const days = timeFilter.value;
        const data = await apiFetch(`/admin/stats?days=${days}`);
        document.getElementById('total-revenue').textContent = formatCurrency((data.total_revenue || 0) / 100);
        document.getElementById('net-profit').textContent = formatCurrency((data.net_profit || 0) / 100);
        document.getElementById('vips-paid').textContent = data.vips_paid || 0;
        document.getElementById('vips-pending').textContent = data.vips_pending_delivery || 0;
        renderTable(data.recent_orders || []);
    }

    function updateStatusUI(id, status) {
        const el = document.getElementById(`status-${id}`);
        if (!el) return;
        if (status === 'online' || status === 'ok' || status === true) {
            el.textContent = 'Online';
            el.className = 'status-text ok';
        } else if (status === 'maintenance' || status === 'warning') {
            el.textContent = 'Instável';
            el.className = 'status-text warning';
        } else {
            el.textContent = 'Offline';
            el.className = 'status-text error';
        }
    }

    function renderTable(orders) {
        const tbody = document.getElementById('orders-table-body');
        tbody.innerHTML = '';
        if (!orders.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center">Nenhum registro encontrado.</td></tr>';
            return;
        }
        orders.forEach(order => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>#${order.id}</td>
                <td>${formatDate(order.created_at)}</td>
                <td>${order.customer_name}</td>
                <td>${order.product}</td>
                <td>${formatCurrency((order.amount || 0) / 100)}</td>
                <td><span class="badge ${getStatusBadgeClass(order.status || 'PENDING')}">${translateStatus(order.status || 'PENDING')}</span></td>
                <td><span class="badge ${getDeliveryBadgeClass(order.delivery_status || 'PENDING')}">${translateDelivery(order.delivery_status || 'PENDING')}</span></td>
            `;
            tbody.appendChild(tr);
        });
    }

    function formatCurrency(value) {
        return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
    }

    function formatDate(dateString) {
        if (!dateString) return '-';
        const date = new Date(dateString);
        return date.toLocaleDateString('pt-BR') + ' ' + date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    }

    function getStatusBadgeClass(status) {
        switch (String(status).toUpperCase()) {
            case 'PAID': return 'badge-paid';
            case 'PENDING': return 'badge-pending';
            case 'FAILED': return 'badge-failed';
            default: return 'badge-waiting';
        }
    }

    function getDeliveryBadgeClass(status) {
        switch (String(status).toUpperCase()) {
            case 'DELIVERED': return 'badge-delivered';
            case 'PENDING': return 'badge-waiting';
            case 'ROLLBACK_PENDING': return 'badge-waiting';
            case 'FAILED': return 'badge-failed';
            default: return 'badge-waiting';
        }
    }

    function translateStatus(status) {
        const map = { PAID: 'Pago', PENDING: 'Pendente', FAILED: 'Falhou', CANCELED: 'Cancelado' };
        return map[String(status).toUpperCase()] || status;
    }

    function translateDelivery(status) {
        const map = { DELIVERED: 'Entregue', PENDING: 'Aguardando', ROLLBACK_PENDING: 'Reprocessar', FAILED: 'Erro', NONE: '-' };
        return map[String(status).toUpperCase()] || status;
    }

    loginForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        loginError.textContent = '';
        const btn = loginForm.querySelector('button[type="submit"]');
        const originalText = btn.textContent;
        btn.textContent = 'Processando...';
        btn.disabled = true;

        const loginUsername = document.getElementById('login-username').value.trim();
        const loginPassword = document.getElementById('login-password').value;

        console.log('[DEBUG] Tentando login com:', loginUsername);
        console.log('[DEBUG] API_BASE_URL:', API_BASE_URL);

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000); // 15s timeout

        try {
            let response;
            try {
                console.log('[DEBUG] Fetching /auth/login...');
                response = await fetch(`${API_BASE_URL}/auth/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: loginUsername, password: loginPassword }),
                    signal: controller.signal
                });
                clearTimeout(timeoutId);
                console.log('[DEBUG] Fetch response:', response.status);
            } catch (err) {
                if (err.name === 'AbortError') {
                    throw new Error('Tempo limite excedido. O servidor demorou muito para responder.');
                }
                console.error('[DEBUG] Fetch error:', err);
                throw new Error(`Backend offline ou inacessível em ${API_BASE_URL}. Verifique conexão.`);
            }
            
            let data = {};
            try {
                data = await response.json();
                console.log('[DEBUG] JSON data:', data);
            } catch (jsonErr) {
                console.error('[DEBUG] JSON parse error:', jsonErr);
                if (!response.ok) {
                    throw new Error('Resposta inválida no login (não é JSON)');
                }
            }

            if (!response.ok) {
                throw new Error(data.error || 'Falha de autenticação');
            }

            token = data.token;
            username = loginUsername;
            localStorage.setItem('simplex_admin_token', token);
            localStorage.setItem('simplex_admin_user', username);
            
            console.log('[DEBUG] Login sucesso! Token salvo.');
            
            setSessionUserLabel();
            hideAuthGate();
            await fetchStatus();
            await fetchStats();
        } catch (error) {
            console.error('[DEBUG] Erro final:', error);
            loginError.textContent = error.message;
        } finally {
            btn.textContent = originalText;
            btn.disabled = false;
        }
    });

    logoutBtn.addEventListener('click', () => {
        token = '';
        username = '';
        localStorage.removeItem('simplex_admin_token');
        localStorage.removeItem('simplex_admin_user');
        setSessionUserLabel();
        showAuthGate();
    });

    refreshBtn.addEventListener('click', async () => {
        await fetchStatus();
        await fetchStats();
    });

    timeFilter.addEventListener('change', async () => {
        await fetchStats();
    });

    setSessionUserLabel();
    validateSession().then(async (ok) => {
        if (ok) {
            await fetchStatus();
            await fetchStats();
        }
    });
});
