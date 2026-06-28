// FIX: порт выравнен с main.py
const API_BASE = 'http://127.0.0.1:8080';

const sectionTitles = {
    dashboard: 'Дашборд',
    upload:    'Загрузка архива',
    search:    'Поиск',
    unmatched: 'Очередь верификации',
    partners:  'Партнёры',
};

function showSection(name, el) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById(`sec-${name}`).classList.add('active');
    if (el) el.classList.add('active');
    document.getElementById('topbarTitle').textContent = sectionTitles[name] || '';

    if (name === 'dashboard') loadDashboard();
    if (name === 'unmatched') loadUnmatched();
    if (name === 'partners')  loadPartners();
}


let toastTimer;
function toast(msg, type = '') {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = `toast ${type}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.className = 'toast hidden', 3500);
}


async function loadDashboard() {
    try {
        const res = await fetch(`${API_BASE}/dashboard/stats`);
        if (!res.ok) throw new Error('API недоступен');
        const d = await res.json();

        animateCount('st-total-docs', d.total_docs);
        animateCount('st-done-docs',  d.done_docs);
        animateCount('st-review-docs', d.needs_review_docs);
        animateCount('st-error-docs', d.error_docs);
        animateCount('st-partners',   d.total_partners);
        animateCount('st-services',   d.total_services);
        animateCount('st-items',      d.total_items);

        const pct = d.normalization_pct;
        document.getElementById('normPct').textContent = pct + '%';
        const circ = 2 * Math.PI * 50; // 314
        const offset = circ - (circ * pct / 100);
        document.getElementById('normRing').style.strokeDashoffset = offset;

        const matched = d.total_items - d.unmatched_items;
        animateCount('matchedCount',   matched);
        animateCount('unmatchedCount', d.unmatched_items);
        animateCount('verifiedCount',  d.verified_items);

        const badge = document.getElementById('unmatchedBadge');
        if (d.unmatched_items > 0) {
            badge.textContent = d.unmatched_items;
            badge.style.display = 'inline-block';
        } else {
            badge.style.display = 'none';
        }

        const total = d.total_docs || 1;
        const setPct = (id, val) => {
            document.getElementById(id).style.width = (val / total * 100) + '%';
        };
        setPct('barDone',    d.done_docs);
        setPct('barReview',  d.needs_review_docs);
        setPct('barError',   d.error_docs);
        setPct('barPending', total - d.done_docs - d.needs_review_docs - d.error_docs);

    } catch (e) {
        console.warn('Dashboard:', e.message);
    }
}

function animateCount(id, target) {
    const el = document.getElementById(id);
    if (!el) return;
    const start = parseInt(el.textContent) || 0;
    const diff = target - start;
    const duration = 700;
    const steps = 30;
    let step = 0;
    const interval = setInterval(() => {
        step++;
        const progress = step / steps;
        const ease = 1 - Math.pow(1 - progress, 3);
        el.textContent = Math.round(start + diff * ease);
        if (step >= steps) { el.textContent = target; clearInterval(interval); }
    }, duration / steps);
}

let selectedFile = null;

function handleFileSelect(e) {
    setFile(e.target.files[0]);
}

function handleDragOver(e) {
    e.preventDefault();
    document.getElementById('dropZone').classList.add('drag-over');
}

function handleDragLeave() {
    document.getElementById('dropZone').classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    document.getElementById('dropZone').classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file && file.name.endsWith('.zip')) setFile(file);
    else toast('Принимаются только ZIP-архивы', 'error');
}

function setFile(file) {
    if (!file) return;
    selectedFile = file;
    document.getElementById('selectedFile').classList.remove('hidden');
    document.getElementById('selectedFileName').textContent = file.name;
    document.getElementById('uploadBtn').disabled = false;
}

function clearFile() {
    selectedFile = null;
    document.getElementById('fileInput').value = '';
    document.getElementById('selectedFile').classList.add('hidden');
    document.getElementById('uploadBtn').disabled = true;
}

async function uploadFile() {
    if (!selectedFile) return;

    const btn = document.getElementById('uploadBtn');
    btn.disabled = true;
    btn.textContent = 'Загрузка...';

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
        const res = await fetch(`${API_BASE}/upload-archive`, { method: 'POST', body: formData });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Ошибка сервера');
        }

        const data = await res.json();
        toast(`Архив принят! ID: ${data.doc_id}`, 'success');

        // Show processing card
        const card = document.getElementById('processingCard');
        card.classList.remove('hidden');
        setChip('pending');
        document.getElementById('procStatus').textContent = 'pending';
        document.getElementById('procItems').textContent = '0';
        document.getElementById('procBar').className = 'proc-progress-bar';
        document.getElementById('procLog').classList.add('hidden');

        // Poll
        const interval = setInterval(async () => {
            try {
                const sr = await fetch(`${API_BASE}/documents/${data.doc_id}/status`);
                if (!sr.ok) return;
                const sd = await sr.json();

                document.getElementById('procStatus').textContent = sd.status;
                animateCount('procItems', sd.items_extracted);
                setChip(sd.status);

                if (['done', 'error', 'needs_review'].includes(sd.status)) {
                    clearInterval(interval);
                    const bar = document.getElementById('procBar');
                    bar.classList.add(sd.status === 'done' ? 'done' : 'error');
                    if (sd.log) {
                        document.getElementById('procLog').classList.remove('hidden');
                        document.getElementById('procLogText').textContent = sd.log;
                    }
                    loadDashboard();
                }
            } catch {}
        }, 2000);

    } catch (e) {
        toast(`Ошибка: ${e.message}`, 'error');
    } finally {
        btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg> Загрузить и обработать`;
        btn.disabled = false;
    }
}

function setChip(status) {
    const chip = document.getElementById('procChip');
    chip.textContent = status;
    chip.className = `proc-status-chip ${status}`;
}

// ─── Search ───

async function doSearch() {
    const q = document.getElementById('searchInput').value.trim();
    if (!q) return;

    const container = document.getElementById('searchResults');
    container.innerHTML = `<div class="empty-state"><p>Поиск...</p></div>`;

    try {
        const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(q)}`);
        if (!res.ok) throw new Error('Ошибка сервера');
        const data = await res.json();

        let html = '';

        if (data.services.length) {
            html += `<div class="result-group-title">Услуги (${data.services.length})</div>`;
            data.services.forEach(s => {
                html += `<div class="result-item">
                    <div class="result-item-top">
                        <div>
                            <div class="result-name">${esc(s.service_name)}</div>
                            ${s.category ? `<div class="result-meta">${esc(s.category)}</div>` : ''}
                        </div>
                        <div style="display:flex;align-items:center;gap:8px">
                            <span class="result-tag blue">${s.icd_code || 'МКБ н/д'}</span>
                            <button class="btn-secondary btn-sm" onclick="loadPartnersForService('${s.service_id}', this)">
                                Партнёры →
                            </button>
                        </div>
                    </div>
                    <div class="partners-sub" id="ps-${s.service_id}" style="display:none"></div>
                </div>`;
            });
        }

        if (data.partners.length) {
            html += `<div class="result-group-title" style="margin-top:8px">Партнёры (${data.partners.length})</div>`;
            data.partners.forEach(p => {
                html += `<div class="result-item">
                    <div class="result-item-top">
                        <div>
                            <div class="result-name">${esc(p.name)}</div>
                            <div class="result-meta">${[p.city, p.address].filter(Boolean).map(esc).join(' · ')}</div>
                        </div>
                        <span class="result-tag green">${p.is_active ? 'Активен' : 'Неактивен'}</span>
                    </div>
                </div>`;
            });
        }

        if (data.price_items.length) {
            html += `<div class="result-group-title" style="margin-top:8px">Позиции прайсов (${data.price_items.length})</div>`;
            data.price_items.slice(0, 30).forEach(item => {
                const price = item.price_resident_kzt
                    ? `${Number(item.price_resident_kzt).toLocaleString('ru')} ₸`
                    : '—';
                const anomaly = item.price_anomaly
                    ? `<span class="anomaly-tag">⚠ Аномалия цены</span>` : '';
                html += `<div class="result-item">
                    <div class="result-item-top">
                        <div class="result-name">${esc(item.service_name_raw)}</div>
                        <div style="display:flex;align-items:center;gap:8px">
                            ${anomaly}
                            <span class="result-tag teal">${price}</span>
                        </div>
                    </div>
                    ${item.price_nonresident_kzt ? `<div class="result-meta">Нерезидент: ${Number(item.price_nonresident_kzt).toLocaleString('ru')} ₸</div>` : ''}
                </div>`;
            });
        }

        if (!html) {
            html = `<div class="empty-state"><p>Ничего не найдено по запросу «${esc(q)}»</p></div>`;
        }

        container.innerHTML = html;

    } catch (e) {
        container.innerHTML = `<div class="empty-state"><p style="color:var(--red)">${e.message}</p></div>`;
    }
}

async function loadPartnersForService(serviceId, btn) {
    const sub = document.getElementById(`ps-${serviceId}`);
    if (sub.style.display === 'block') { sub.style.display = 'none'; btn.textContent = 'Партнёры →'; return; }

    sub.style.display = 'block';
    sub.innerHTML = '<span style="font-size:12px;color:var(--text-faint)">Загрузка...</span>';
    btn.textContent = 'Скрыть';

    try {
        const [itemsRes, partnersRes] = await Promise.all([
            fetch(`${API_BASE}/services/${serviceId}/partners`),
            fetch(`${API_BASE}/partners?limit=500`),
        ]);
        const items = await itemsRes.json();
        const partners = await partnersRes.json();
        const partnerMap = {};
        partners.forEach(p => { partnerMap[p.partner_id] = p; });

        if (!items.length) { sub.innerHTML = '<span style="font-size:12px;color:var(--text-faint)">Нет предложений</span>'; return; }

        sub.innerHTML = items.map(item => {
            const partner = item.partner_id ? partnerMap[item.partner_id] : null;
            const partnerName = partner ? esc(partner.name) : '—';
            const partnerCity = partner && partner.city ? ` · ${esc(partner.city)}` : '';
            const r  = item.price_resident_kzt    ? `${Number(item.price_resident_kzt).toLocaleString('ru')} ₸` : '—';
            const nr = item.price_nonresident_kzt ? ` · Нерезидент: <strong>${Number(item.price_nonresident_kzt).toLocaleString('ru')} ₸</strong>` : '';
            const eff = item.effective_date ? `<span style="font-size:11px;color:var(--text-faint);margin-left:4px">${item.effective_date}</span>` : '';
            const anomaly = item.price_anomaly ? `<span class="anomaly-tag" style="margin-left:4px">⚠ Аномалия</span>` : '';
            return `<div class="partner-price-row">
                <div><span style="font-weight:500">${partnerName}</span><span style="color:var(--text-faint)">${partnerCity}</span>${eff}</div>
                <span>Резидент: <strong>${r}</strong>${nr}${anomaly}</span>
            </div>`;
        }).join('');

    } catch (e) {
        sub.innerHTML = `<span style="font-size:12px;color:var(--red)">${e.message}</span>`;
    }
}


async function loadUnmatched() {
    const container = document.getElementById('unmatchedList');
    container.innerHTML = `<div class="empty-state"><p>Загрузка...</p></div>`;

    try {
        const [itemsRes, servicesRes] = await Promise.all([
            fetch(`${API_BASE}/unmatched?limit=50`),
            fetch(`${API_BASE}/services?limit=200`),
        ]);

        const items    = await itemsRes.json();
        const services = await servicesRes.json();

        if (!items.length) {
            container.innerHTML = `<div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="40" height="40"><polyline points="20 6 9 17 4 12"/></svg>
                <p style="color:var(--green);font-weight:600">Все позиции сопоставлены!</p>
            </div>`;
            return;
        }

        const opts = services.map(s =>
            `<option value="${s.service_id}">${esc(s.service_name)}</option>`
        ).join('');

        container.innerHTML = items.map(item => {
            const price = item.price_resident_kzt
                ? `${Number(item.price_resident_kzt).toLocaleString('ru')} ₸`
                : (item.price_original ? `${item.price_original} ${item.currency_original || ''}` : '—');
            const anomaly = item.price_anomaly ? `<span class="anomaly-tag">⚠ Аномалия</span>` : '';
            const note = item.verification_note ? `<div class="unmatched-note">${esc(item.verification_note)}</div>` : '';
            return `<div class="unmatched-item${item.price_anomaly ? ' anomaly' : ''}" id="ui-${item.item_id}">
                <div class="unmatched-top">
                    <div>
                        <div class="unmatched-name">${esc(item.service_name_raw)}</div>
                        <div class="unmatched-price">Цена: ${price}</div>
                        ${note}
                    </div>
                    ${anomaly}
                </div>
                <div class="unmatched-controls">
                    <select id="sel-${item.item_id}" class="svc-select">
                        <option value="">— выберите услугу из справочника —</option>
                        ${opts}
                    </select>
                    <button class="btn-primary btn-sm" onclick="matchItem('${item.item_id}')">✓ Сопоставить</button>
                </div>
            </div>`;
        }).join('');

    } catch (e) {
        container.innerHTML = `<div class="empty-state"><p style="color:var(--red)">${e.message}</p></div>`;
    }
}

async function matchItem(itemId) {
    const sel = document.getElementById(`sel-${itemId}`);
    if (!sel.value) { toast('Выберите услугу из справочника', 'error'); return; }

    try {
        const res = await fetch(`${API_BASE}/match`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ item_id: itemId, service_id: sel.value }),
        });

        if (!res.ok) throw new Error('Ошибка сопоставления');

        const card = document.getElementById(`ui-${itemId}`);
        card.classList.add('done');
        card.querySelector('.unmatched-controls').innerHTML =
            `<div style="font-size:13px;color:var(--green);font-weight:600">✓ Сопоставлено</div>`;
        toast('Позиция успешно сопоставлена', 'success');

    } catch (e) {
        toast(e.message, 'error');
    }
}


async function loadPartners() {
    const container = document.getElementById('partnersList');
    container.innerHTML = `<div class="empty-state"><p>Загрузка...</p></div>`;

    try {
        const res = await fetch(`${API_BASE}/partners?limit=100`);
        if (!res.ok) throw new Error('Ошибка загрузки');
        const partners = await res.json();

        if (!partners.length) {
            container.innerHTML = `<div class="empty-state"><p>Партнёры не найдены</p></div>`;
            return;
        }

        container.innerHTML = partners.map(p => {
            const initials = p.name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();
            const meta = [p.city, p.contact_email, p.contact_phone].filter(Boolean).join(' · ');
            return `<div class="partner-card">
                <div class="partner-avatar">${initials}</div>
                <div class="partner-info">
                    <div class="partner-name">${esc(p.name)}</div>
                    <div class="partner-meta">${esc(meta) || '—'}</div>
                    <div class="partner-services-sub" id="psvc-${p.partner_id}" style="display:none"></div>
                </div>
                <div style="display:flex;align-items:center;gap:8px">
                    <button class="btn-secondary btn-sm" onclick="togglePartnerServices('${p.partner_id}', this)">Прайс →</button>
                    <span class="partner-badge ${p.is_active ? 'active' : 'inactive'}">
                        ${p.is_active ? 'Активен' : 'Неактивен'}
                    </span>
                </div>
            </div>`;
        }).join('');

    } catch (e) {
        container.innerHTML = `<div class="empty-state"><p style="color:var(--red)">${e.message}</p></div>`;
    }
}

async function togglePartnerServices(partnerId, btn) {
    const sub = document.getElementById(`psvc-${partnerId}`);
    if (sub.style.display === 'block') { sub.style.display = 'none'; btn.textContent = 'Прайс →'; return; }
    sub.style.display = 'block';
    sub.innerHTML = '<span style="font-size:12px;color:var(--text-faint)">Загрузка...</span>';
    btn.textContent = 'Скрыть';

    try {
        const res = await fetch(`${API_BASE}/partners/${partnerId}/services`);
        if (!res.ok) throw new Error('Ошибка загрузки');
        const items = await res.json();
        if (!items.length) { sub.innerHTML = '<span style="font-size:12px;color:var(--text-faint)">Нет позиций прайса</span>'; return; }
        sub.innerHTML = `<table style="width:100%;font-size:12px;margin-top:8px;border-collapse:collapse">
            <thead><tr style="color:var(--text-faint);text-align:left">
                <th style="padding:4px 8px">Услуга</th>
                <th style="padding:4px 8px">Резидент</th>
                <th style="padding:4px 8px">Нерезидент</th>
                <th style="padding:4px 8px">Дата</th>
            </tr></thead>
            <tbody>${items.map(it => {
                const r  = it.price_resident_kzt    ? `${Number(it.price_resident_kzt).toLocaleString('ru')} ₸` : '—';
                const nr = it.price_nonresident_kzt ? `${Number(it.price_nonresident_kzt).toLocaleString('ru')} ₸` : '—';
                const anomaly = it.price_anomaly ? ' ⚠' : '';
                return `<tr style="border-top:1px solid var(--border)">
                    <td style="padding:4px 8px">${esc(it.service_name_raw)}${anomaly}</td>
                    <td style="padding:4px 8px">${r}</td>
                    <td style="padding:4px 8px">${nr}</td>
                    <td style="padding:4px 8px;color:var(--text-faint)">${it.effective_date || '—'}</td>
                </tr>`;
            }).join('')}</tbody></table>`;
    } catch (e) {
        sub.innerHTML = `<span style="font-size:12px;color:var(--red)">${e.message}</span>`;
    }
}


function esc(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

document.addEventListener('DOMContentLoaded', () => {
    const inp = document.getElementById('searchInput');
    if (inp) inp.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

    loadDashboard();
});
