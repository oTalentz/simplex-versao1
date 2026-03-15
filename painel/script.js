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

    async function apiFetch(path, options = {}) {
        let response;
        try {
            const fetchOptions = {
                ...options,
                headers: {
                    ...(token ? { Authorization: `Bearer ${token}` } : {}),
                    ...(options.headers || {})
                }
            };
            response = await fetch(`${API_BASE_URL}${path}`, fetchOptions);
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

    function setupDashboardInteractions() {
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
                        if (target === 'coupons') {
                            fetchCoupons();
                        }
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
            // Remove existing listeners to avoid duplicates if called multiple times
            const newBtn = pairBtn.cloneNode(true);
            pairBtn.parentNode.replaceChild(newBtn, pairBtn);
            
            newBtn.addEventListener('click', async () => {
                const code = pairInput.value.trim().toUpperCase();
                if (!code) {
                    pairStatus.textContent = 'Digite o código de pareamento.';
                    pairStatus.className = 'status-text error';
                    return;
                }

                pairStatus.textContent = 'Conectando...';
                pairStatus.className = 'status-text warning';
                newBtn.disabled = true;

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
                        
                        // Poll for status update until online or timeout (max 10 attempts)
                        let attempts = 0;
                        const pollInterval = setInterval(async () => {
                            attempts++;
                            try {
                                const statusData = await apiFetch('/admin/status');
                                if (statusData.mc_status === 'online' || statusData.mc_status === 'warning') {
                                    clearInterval(pollInterval);
                                    fetchStatus(); // Final update to UI
                                }
                            } catch (e) { console.error('Polling error', e); }
                            
                            if (attempts >= 10) clearInterval(pollInterval);
                        }, 2000);
                        
                        await fetchStatus(); // Immediate check
                    } else {
                        throw new Error(data.error || 'Falha ao conectar servidor');
                    }
                } catch (error) {
                    pairStatus.textContent = error.message;
                    pairStatus.className = 'status-text error';
                } finally {
                    newBtn.disabled = false;
                }
            });
        }

        // Server Name Edit Logic
        const btnEditName = document.getElementById('btn-edit-server-name');
        const btnSaveName = document.getElementById('btn-save-server-name');
        const btnCancelName = document.getElementById('btn-cancel-server-name');
        const displayContainer = document.getElementById('server-name-display');
        const editContainer = document.getElementById('server-name-edit');
        const nameInput = document.getElementById('input-server-name');
        const nameDisplay = document.getElementById('info-server-name');

        if (btnEditName) {
            // Clone to remove old listeners if any
            const newEditBtn = btnEditName.cloneNode(true);
            btnEditName.parentNode.replaceChild(newEditBtn, btnEditName);

            newEditBtn.addEventListener('click', () => {
                nameInput.value = nameDisplay.textContent === '-' ? '' : nameDisplay.textContent;
                displayContainer.style.display = 'none';
                editContainer.style.display = 'flex';
                editContainer.classList.remove('hidden');
                nameInput.focus();
            });
        }

        if (btnCancelName) {
            const newCancelBtn = btnCancelName.cloneNode(true);
            btnCancelName.parentNode.replaceChild(newCancelBtn, btnCancelName);

            newCancelBtn.addEventListener('click', () => {
                editContainer.style.display = 'none';
                editContainer.classList.add('hidden');
                displayContainer.style.display = 'flex';
            });
        }

        if (btnSaveName) {
            const newSaveBtn = btnSaveName.cloneNode(true);
            btnSaveName.parentNode.replaceChild(newSaveBtn, btnSaveName);

            newSaveBtn.addEventListener('click', async () => {
                const newName = nameInput.value.trim();
                if (!newName) return;

                const originalIcon = newSaveBtn.innerHTML;
                newSaveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                newSaveBtn.disabled = true;

                try {
                    await apiFetch('/admin/settings', { // Use apiFetch wrapper to handle auth/errors automatically
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${token}`
                        },
                        body: JSON.stringify({ key: 'server_name', value: newName })
                    });
                    
                    nameDisplay.textContent = newName;
                    editContainer.style.display = 'none';
                    editContainer.classList.add('hidden');
                    displayContainer.style.display = 'flex';
                    await fetchStatus(); 
                } catch (error) {
                    alert('Erro ao salvar nome: ' + error.message);
                } finally {
                    newSaveBtn.innerHTML = originalIcon;
                    newSaveBtn.disabled = false;
                }
            });
        }

        // Server Disconnect Logic
        const btnDisconnect = document.getElementById('btn-disconnect-server');
        if (btnDisconnect) {
            const newDisconnectBtn = btnDisconnect.cloneNode(true);
            btnDisconnect.parentNode.replaceChild(newDisconnectBtn, btnDisconnect);

            newDisconnectBtn.addEventListener('click', async () => {
                if (!confirm('Tem certeza que deseja desconectar este servidor? O pareamento será removido.')) {
                    return;
                }

                const originalContent = newDisconnectBtn.innerHTML;
                newDisconnectBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                newDisconnectBtn.disabled = true;

                try {
                    await apiFetch('/admin/connector/disconnect', {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${token}`
                        }
                    });

                    await fetchStatus();
                } catch (error) {
                    alert('Erro ao desconectar: ' + error.message);
                    newDisconnectBtn.innerHTML = originalContent;
                    newDisconnectBtn.disabled = false;
                }
            });
        }
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

            const connInfo = document.getElementById('server-connection-info');
            const pairingSection = document.getElementById('server-pairing-section');
            
            if (data.mc_status === 'online' || data.mc_status === 'warning') {
                if(connInfo) {
                    connInfo.style.display = 'block';
                    document.getElementById('info-server-name').textContent = data.mc_server_name || 'Desconhecido';
                    document.getElementById('info-players').textContent = data.mc_players_online || 0;
                    document.getElementById('info-last-seen').textContent = formatDate(data.mc_last_seen);
                    
                    const badge = document.getElementById('connection-badge');
                    if(badge) {
                        badge.textContent = data.mc_status === 'online' ? 'Online' : 'Instável';
                        badge.className = `badge ${data.mc_status === 'online' ? 'badge-delivered' : 'badge-waiting'}`;
                    }
                }
                if(pairingSection) pairingSection.style.display = 'none';
            } else {
                if(connInfo) connInfo.style.display = 'none';
                if(pairingSection) pairingSection.style.display = 'block';
            }
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
                // Tenta ler como texto primeiro para debug
                const rawText = await response.text();
                try {
                    data = JSON.parse(rawText);
                    console.log('[DEBUG] JSON data:', data);
                } catch (parseErr) {
                    console.error('[DEBUG] Falha ao parsear JSON. Resposta bruta:', rawText);
                    // Se a resposta for HTML de erro, tentamos extrair algo útil ou apenas mostramos erro genérico
                    if (rawText.includes("Internal Server Error")) {
                        throw new Error("Erro Interno no Servidor (500). Verifique os logs do Vercel.");
                    }
                    throw new Error(`Resposta inválida do servidor: ${rawText.substring(0, 100)}...`);
                }
            } catch (jsonErr) {
                console.error('[DEBUG] Erro de processamento:', jsonErr);
                if (!response.ok) {
                    // Se já falhou o parse e o status não é ok, usa a mensagem do erro de parse ou genérica
                    throw new Error(jsonErr.message || 'Resposta inválida no login (não é JSON)');
                }
                throw jsonErr; // Se status ok mas JSON inválido, lança erro
            }

            if (!response.ok) {
                let msg = data.error || 'Falha de autenticação';
                if (data.details) {
                    msg += `: ${data.details}`;
                }
                throw new Error(msg);
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
    setupDashboardInteractions();
    setupCouponInteractions();
    setupHistoryInteractions();
    validateSession().then(async (ok) => {
        if (ok) {
            await fetchStatus();
            await fetchStats();
        }
    });
    // End of validateSession

    async function fetchCoupons() {
        try {
            const data = await apiFetch('/admin/coupons');
            const coupons = data.coupons || data || []; // Handle list or dict response
            // Sometimes apiFetch returns object, sometimes array depending on endpoint wrapper
            // If endpoint returns list directly:
            const list = Array.isArray(data) ? data : (data.coupons || []);
            
            window.allCoupons = list; // Cache for validation
            renderCouponsTable(list);
            
            // Also fetch stats to update the cards
            loadCouponStats();
        } catch (error) {
            console.error('Erro ao buscar cupons:', error);
            // alert('Erro ao buscar cupons: ' + error.message);
        }
    }

    async function loadCouponStats() {
        try {
            const data = await apiFetch('/admin/coupons/stats');
            
            // Update cards
            const elActive = document.getElementById('stats-active-coupons');
            const elUses = document.getElementById('stats-total-uses');
            const elDiscount = document.getElementById('stats-total-discount');
            
            if (elActive) elActive.textContent = data.active_coupons;
            if (elUses) elUses.textContent = data.total_uses;
            if (elDiscount) elDiscount.textContent = formatCurrency(data.total_discount_given / 100);
            
            // Update Top 5 Table in Modal
            const tbody = document.getElementById('top-coupons-body');
            if (tbody) {
                tbody.innerHTML = '';
                if (data.top_coupons && data.top_coupons.length > 0) {
                    data.top_coupons.forEach(c => {
                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td><span style="font-family: monospace; font-weight: bold; color: var(--accent-gold);">${c.code}</span></td>
                            <td>${c.used_count}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                } else {
                    tbody.innerHTML = '<tr><td colspan="2" class="text-center">Nenhum dado disponível.</td></tr>';
                }
            }
        } catch (error) {
            console.error('Erro ao carregar estatísticas:', error);
        }
    }

    function renderCouponsTable(coupons) {
        const tbody = document.getElementById('coupons-table-body');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (!coupons.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center">Nenhum cupom encontrado.</td></tr>';
            return;
        }

        coupons.forEach(coupon => {
            const tr = document.createElement('tr');
            const isExpired = coupon.expires_at && new Date(coupon.expires_at) < new Date();
            const statusClass = (coupon.status === 'ACTIVE' && !isExpired) ? 'badge-delivered' : 'badge-failed';
            const statusText = isExpired ? 'Expirado' : (coupon.status === 'ACTIVE' ? 'Ativo' : 'Inativo');
            
            tr.innerHTML = `
                <td><span style="font-family: monospace; font-weight: bold; color: var(--accent-gold);">${coupon.code}</span></td>
                <td>${coupon.discount_type === 'PERCENT' ? 'Porcentagem' : 'Fixo'}</td>
                <td>${coupon.discount_type === 'PERCENT' ? coupon.discount_value + '%' : formatCurrency(coupon.discount_value / 100)}</td>
                <td>${coupon.used_count} / ${coupon.max_uses === -1 ? '∞' : coupon.max_uses}</td>
                <td>${formatDate(coupon.expires_at) || 'Nunca'}</td>
                <td><span class="badge ${statusClass}">${statusText}</span></td>
                <td>
                    <button class="btn-icon-small" onclick="editCoupon('${coupon.code}')" title="Editar"><i class="fas fa-edit"></i></button>
                    <button class="btn-icon-small" onclick="viewCouponHistory('${coupon.code}')" title="Histórico"><i class="fas fa-history"></i></button>
                    <button class="btn-icon-small danger" onclick="deleteCoupon('${coupon.code}')" title="Excluir"><i class="fas fa-trash"></i></button>
                </td>
            `;
            tbody.appendChild(tr);
        });
        
        // Add global functions for inline onclick handlers
        window.editCoupon = (code) => {
            const coupon = coupons.find(c => c.code === code);
            if (coupon) openCouponModal(coupon);
        };
        
        window.deleteCoupon = async (code) => {
            if (!confirm(\`Tem certeza que deseja excluir o cupom "\${code}"?\`)) return;
            try {
                await apiFetch(\`/admin/coupons/\${code}\`, { method: 'DELETE' });
                fetchCoupons();
            } catch (error) {
                alert('Erro ao excluir: ' + error.message);
            }
        };
    }

    function updateCouponStats(coupons) {
        const total = coupons.length;
        const active = coupons.filter(c => c.status === 'ACTIVE' && (!c.expires_at || new Date(c.expires_at) > new Date())).length;
        
        const elTotal = document.getElementById('stats-total-coupons');
        const elActive = document.getElementById('stats-active-coupons');
        
        if (elTotal) elTotal.textContent = total;
        if (elActive) elActive.textContent = active;
    }

    function setupCouponInteractions() {
        const modal = document.getElementById('coupon-modal');
        const btnNew = document.getElementById('btn-new-coupon');
        const btnClose = document.getElementById('btn-close-coupon-modal');
        const btnGenCode = document.getElementById('btn-generate-code');
        const form = document.getElementById('coupon-form');
        const btnPrev = document.getElementById('btn-prev-step');
        const btnNext = document.getElementById('btn-next-step');
        const btnSave = document.getElementById('btn-save-coupon');
        const btnImport = document.getElementById('btn-import-coupons');
        const btnExport = document.getElementById('btn-export-coupons');
        const fileImport = document.getElementById('file-import-coupons');
        
        // --- Stats Modal Logic ---
        const btnStats = document.getElementById('btn-coupon-stats');
        const statsModal = document.getElementById('coupon-stats-modal');
        const btnCloseStats = document.getElementById('btn-close-stats-modal');

        if (btnStats) {
            btnStats.addEventListener('click', async () => {
                if (statsModal) {
                    statsModal.style.display = 'flex';
                    statsModal.classList.remove('hidden');
                    // Force fetch fresh stats
                    await loadCouponStats();
                }
            });
        }

        if (btnCloseStats) {
            btnCloseStats.addEventListener('click', () => {
                if (statsModal) {
                    statsModal.style.display = 'none';
                    statsModal.classList.add('hidden');
                }
            });
        }
        
        // --- Template & Validation Logic ---
        const templateSelect = document.getElementById('coupon-template');
        const feedbackEl = document.getElementById('coupon-code-feedback');
        
        function validateCode() {
            const codeInput = document.getElementById('coupon-code');
            if (!feedbackEl || !codeInput) return;
            
            // If creating new, check duplicates. If editing, code is readonly.
            if (codeInput.readOnly) {
                feedbackEl.textContent = '';
                return;
            }

            const code = codeInput.value.trim().toUpperCase();
            
            if (code.length === 0) {
                feedbackEl.textContent = '';
                return;
            }
            
            if (code.length < 3) {
                feedbackEl.textContent = 'Muito curto (min 3)';
                feedbackEl.style.color = '#ff4444'; // Red
                return;
            }
            
            if (/\s/.test(code)) {
                feedbackEl.textContent = 'Sem espaços!';
                feedbackEl.style.color = '#ff4444';
                return;
            }
            
            const exists = (window.allCoupons || []).some(c => c.code === code);
            if (exists) {
                feedbackEl.textContent = 'Código já existe!';
                feedbackEl.style.color = '#ff4444';
            } else {
                feedbackEl.textContent = 'Disponível ✓';
                feedbackEl.style.color = '#00C851'; // Green
            }
        }

        if (templateSelect) {
            templateSelect.addEventListener('change', () => {
                const val = templateSelect.value;
                if (!val) return;
                
                const codeInput = document.getElementById('coupon-code');
                const typeInput = document.getElementById('coupon-type');
                const valueInput = document.getElementById('coupon-value');
                const maxUsesInput = document.getElementById('coupon-max-uses');
                const statusInput = document.getElementById('coupon-status');
                const minCartInput = document.getElementById('coupon-min-cart');

                // Clear previous validation
                if (feedbackEl) feedbackEl.textContent = '';
                
                if (val === 'WELCOME') {
                    codeInput.value = 'BEMVINDO10';
                    typeInput.value = 'PERCENT';
                    valueInput.value = 10;
                    maxUsesInput.value = 1;
                    statusInput.value = 'ACTIVE';
                    minCartInput.value = 0;
                } else if (val === 'BLACKFRIDAY') {
                    codeInput.value = 'BLACKFRIDAY';
                    typeInput.value = 'PERCENT';
                    valueInput.value = 50;
                    maxUsesInput.value = -1;
                    statusInput.value = 'ACTIVE';
                    minCartInput.value = 0;
                } else if (val === 'FIXED10') {
                    codeInput.value = 'DESCONTO10';
                    typeInput.value = 'FIXED';
                    valueInput.value = 10;
                    maxUsesInput.value = -1;
                    statusInput.value = 'ACTIVE';
                    minCartInput.value = 50; // Example min cart
                } else if (val === 'FIXED50') {
                    codeInput.value = 'DESCONTO50';
                    typeInput.value = 'FIXED';
                    valueInput.value = 50;
                    maxUsesInput.value = -1;
                    statusInput.value = 'ACTIVE';
                    minCartInput.value = 100;
                }
                validateCode();
            });
        }
        
        const codeInputRef = document.getElementById('coupon-code');
        if (codeInputRef) {
            codeInputRef.addEventListener('input', validateCode);
            codeInputRef.addEventListener('blur', validateCode);
        }
        // --- End Template Logic ---

        
        let currentStep = 1;
        const totalSteps = 3;

        function updateWizardUI() {
            document.querySelectorAll('.wizard-step').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.wizard-pane').forEach(p => {
                p.classList.add('hidden');
                p.style.display = 'none';
            });
            
            const currentPane = document.querySelector(`.wizard-pane[data-step="\${currentStep}"]`);
            if (currentPane) {
                currentPane.classList.remove('hidden');
                currentPane.style.display = 'block';
            }
            
            const currentStepIndicator = document.querySelector(`.step[data-step="\${currentStep}"]`);
            if (currentStepIndicator) currentStepIndicator.classList.add('active'); // Add active class style logic if needed
            
            // Update buttons
            btnPrev.disabled = currentStep === 1;
            if (currentStep === totalSteps) {
                btnNext.style.display = 'none';
                btnSave.style.display = 'inline-block';
                btnSave.classList.remove('hidden');
            } else {
                btnNext.style.display = 'inline-block';
                btnSave.style.display = 'none';
                btnSave.classList.add('hidden');
            }
            
            // Update step indicators style
            document.querySelectorAll('.step').forEach(step => {
                const stepNum = parseInt(step.getAttribute('data-step'));
                if (stepNum === currentStep) {
                    step.style.color = 'var(--accent-gold)';
                    step.style.fontWeight = 'bold';
                } else {
                    step.style.color = 'var(--text-secondary)';
                    step.style.fontWeight = 'normal';
                }
            });
        }

        if (btnNew) {
            btnNew.addEventListener('click', () => {
                openCouponModal();
            });
        }

        if (btnClose) {
            btnClose.addEventListener('click', () => {
                modal.style.display = 'none';
                modal.classList.add('hidden');
            });
        }

        if (btnGenCode) {
            btnGenCode.addEventListener('click', () => {
                const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
                let result = '';
                for (let i = 0; i < 8; i++) {
                    result += chars.charAt(Math.floor(Math.random() * chars.length));
                }
                document.getElementById('coupon-code').value = result;
            });
        }

        if (btnPrev) {
            btnPrev.addEventListener('click', () => {
                if (currentStep > 1) {
                    currentStep--;
                    updateWizardUI();
                }
            });
        }

        if (btnNext) {
            btnNext.addEventListener('click', () => {
                if (currentStep < totalSteps) {
                    currentStep++;
                    updateWizardUI();
                }
            });
        }
        
        if (form) {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = new FormData(form);
                const payload = {
                    code: formData.get('code'),
                    discount_type: formData.get('discount_type'),
                    discount_value: parseInt(formData.get('discount_value')),
                    min_cart_value: parseFloat(formData.get('min_cart_value') || 0) * 100, // Convert to cents if needed, but backend expects cents? let's check backend
                    status: formData.get('status'),
                    expires_at: formData.get('expires_at') || null,
                    max_uses: parseInt(formData.get('max_uses') || -1)
                };
                
                // Backend expects discount_value as integer. If type is FIXED, it might be in cents or raw value.
                // Let's assume FIXED is in BRL and needs conversion to cents, or just raw value.
                // Looking at server.py: discount_value INTEGER DEFAULT 0, -- percent or fixed amount in cents
                // So if FIXED, we should multiply by 100 if the input is in BRL.
                if (payload.discount_type === 'FIXED') {
                     // The input is type="number", user likely types 10 for R$ 10.00
                     // We should convert to cents.
                     payload.discount_value = Math.round(payload.discount_value * 100);
                }
                
                // min_cart_value is also in cents in backend?
                // server.py: min_cart_value INTEGER DEFAULT 0
                // Yes, consistent with other monetary values.
                payload.min_cart_value = Math.round(parseFloat(formData.get('min_cart_value') || 0) * 100);

                const btnText = btnSave.textContent;
                btnSave.textContent = 'Salvando...';
                btnSave.disabled = true;

                try {
                    const isEdit = form.dataset.mode === 'edit';
                    const url = isEdit ? `/admin/coupons/${form.dataset.code}` : '/admin/coupons';
                    const method = isEdit ? 'PUT' : 'POST';

                    await apiFetch(url, {
                        method: method,
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                    
                    modal.style.display = 'none';
                    modal.classList.add('hidden');
                    fetchCoupons();
                    alert('Cupom salvo com sucesso!');
                } catch (error) {
                    alert('Erro ao salvar cupom: ' + error.message);
                } finally {
                    btnSave.textContent = btnText;
                    btnSave.disabled = false;
                }
            });
        }
        
        // Import/Export
        if (btnExport) {
            btnExport.addEventListener('click', () => {
                window.open(\`\${API_BASE_URL}/admin/coupons/export?token=\${token}\`, '_blank');
            });
        }
        
        if (btnImport && fileImport) {
            btnImport.addEventListener('click', () => fileImport.click());
            
            fileImport.addEventListener('change', async () => {
                if (!fileImport.files.length) return;
                
                const file = fileImport.files[0];
                const formData = new FormData();
                formData.append('file', file);
                
                const btnText = btnImport.innerHTML;
                btnImport.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Importando...';
                btnImport.disabled = true;
                
                try {
                    // Note: apiFetch wrapper handles JSON responses, but for file upload we need specific handling if not JSON
                    // But our apiFetch sets Content-Type to application/json automatically if not specified? 
                    // Wait, apiFetch implementation:
                    /*
                    const fetchOptions = {
                        ...options,
                        headers: {
                            ...(token ? { Authorization: `Bearer ${token}` } : {}),
                            ...(options.headers || {})
                        }
                    };
                    */
                    // It doesn't force Content-Type unless we pass it.
                    // But fetch with FormData automatically sets Content-Type to multipart/form-data with boundary.
                    // So we should NOT set Content-Type header manually.
                    
                    const response = await fetch(\`\${API_BASE_URL}/admin/coupons/import\`, {
                        method: 'POST',
                        headers: {
                            'Authorization': \`Bearer \${token}\`
                        },
                        body: formData
                    });
                    
                    if (!response.ok) {
                        const errData = await response.json();
                        throw new Error(errData.error || 'Erro na importação');
                    }
                    
                    const result = await response.json();
                    alert(\`Importação concluída! Sucesso: \${result.success_count}, Erros: \${result.error_count}\`);
                    fetchCoupons();
                    fileImport.value = ''; // Reset
                } catch (error) {
                    alert('Erro ao importar: ' + error.message);
                } finally {
                    btnImport.innerHTML = btnText;
                    btnImport.disabled = false;
                }
            });
        }
        
        window.openCouponModal = (coupon = null) => {
            currentStep = 1;
            updateWizardUI();
            
            const title = document.getElementById('coupon-modal-title');
            if (coupon) {
                form.dataset.mode = 'edit';
                form.dataset.code = coupon.code;
                title.textContent = 'Editar Cupom';
                document.getElementById('coupon-code').value = coupon.code;
                document.getElementById('coupon-code').readOnly = true; // Cannot change code on edit usually
                document.getElementById('coupon-type').value = coupon.discount_type;
                
                // Convert cents to unit for display
                const val = coupon.discount_type === 'PERCENT' ? coupon.discount_value : coupon.discount_value / 100;
                document.getElementById('coupon-value').value = val;
                
                document.getElementById('coupon-min-cart').value = coupon.min_cart_value / 100;
                document.getElementById('coupon-status').value = coupon.status;
                document.getElementById('coupon-expires').value = coupon.expires_at ? coupon.expires_at.slice(0, 16) : '';
                document.getElementById('coupon-max-uses').value = coupon.max_uses;
            } else {
                form.dataset.mode = 'create';
                delete form.dataset.code;
                title.textContent = 'Novo Cupom';
                form.reset();
                document.getElementById('coupon-code').readOnly = false;
                document.getElementById('coupon-max-uses').value = -1;
                document.getElementById('coupon-min-cart').value = 0;
            }
            
            modal.style.display = 'flex';
            modal.classList.remove('hidden');
        };
    }

    function setupHistoryInteractions() {
        const historyModal = document.getElementById('coupon-history-modal');
        const btnCloseHistory = document.getElementById('btn-close-history-modal');
        const historyTitle = document.getElementById('history-modal-title');
        const historyBody = document.getElementById('history-table-body');

        if (btnCloseHistory) {
            btnCloseHistory.addEventListener('click', () => {
                historyModal.style.display = 'none';
                historyModal.classList.add('hidden');
            });
        }

        window.viewCouponHistory = async (code) => {
            historyTitle.textContent = `Histórico: ${code}`;
            historyBody.innerHTML = '<tr><td colspan="4" class="text-center"><i class="fas fa-spinner fa-spin"></i> Carregando...</td></tr>';
            
            historyModal.style.display = 'flex';
            historyModal.classList.remove('hidden');

            try {
                const logs = await apiFetch(`/admin/coupons/${code}/logs`);
                renderHistoryTable(logs);
            } catch (error) {
                historyBody.innerHTML = `<tr><td colspan="4" class="text-center error">Erro: ${error.message}</td></tr>`;
            }
        };

        function renderHistoryTable(logs) {
            historyBody.innerHTML = '';
            
            if (!logs || !logs.length) {
                historyBody.innerHTML = '<tr><td colspan="4" class="text-center">Nenhum registro encontrado.</td></tr>';
                return;
            }

            logs.forEach(log => {
                const tr = document.createElement('tr');
                let details = log.details;
                let detailsHtml = '';

                try {
                    if (typeof details === 'string') {
                        details = JSON.parse(details);
                    }
                } catch (e) {
                    // details is raw string
                }

                if (log.action === 'CREATE') {
                    detailsHtml = '<span class="text-success">Criação do cupom</span>';
                } else if (log.action === 'IMPORT') {
                    detailsHtml = '<span class="text-info">Importado via CSV</span>';
                } else if (log.action === 'UPDATE' && typeof details === 'object') {
                    detailsHtml = '<ul style="list-style: none; padding: 0; margin: 0; font-size: 0.85em;">';
                    let hasChanges = false;
                    
                    const keyMap = {
                        'code': 'Código',
                        'discount_type': 'Tipo de Desconto',
                        'discount_value': 'Valor do Desconto',
                        'min_cart_value': 'Valor Mínimo do Carrinho',
                        'max_uses': 'Limite de Usos',
                        'expires_at': 'Expira em',
                        'status': 'Status'
                    };

                    for (const [key, val] of Object.entries(details)) {
                         if (key === 'updated_at' || key === 'created_at') continue;
                         
                         let displayKey = keyMap[key] || key;
                         let displayVal = val;

                         if (key === 'min_cart_value') {
                             displayVal = formatCurrency(val / 100);
                         } else if (key === 'expires_at') {
                             displayVal = val ? formatDate(val) : 'Nunca';
                         } else if (key === 'discount_type') {
                             displayVal = val === 'PERCENT' ? 'Porcentagem' : 'Fixo';
                         } else if (key === 'status') {
                             displayVal = val === 'ACTIVE' ? 'Ativo' : 'Inativo';
                         } else if (key === 'discount_value') {
                            // Try to infer context or just show raw
                            displayVal = val; 
                         } else if (key === 'max_uses') {
                            displayVal = val === -1 ? 'Infinito' : val;
                         }

                         detailsHtml += `<li><b>${displayKey}:</b> ${displayVal}</li>`;
                         hasChanges = true;
                    }
                    detailsHtml += '</ul>';
                    if (!hasChanges) detailsHtml = '<span class="text-muted">Atualização sem mudanças visíveis</span>';
                } else if (log.action === 'DELETE') {
                     detailsHtml = '<span class="text-danger">Cupom excluído</span>';
                } else {
                    detailsHtml = typeof details === 'object' ? JSON.stringify(details) : details;
                }

                tr.innerHTML = `
                    <td>${formatDate(log.timestamp)}</td>
                    <td>${log.admin_user || 'Sistema'}</td>
                    <td><span class="badge badge-info">${log.action}</span></td>
                    <td style="font-size: 0.9em;">${detailsHtml}</td>
                `;
                historyBody.appendChild(tr);
            });
        }
    }
});

