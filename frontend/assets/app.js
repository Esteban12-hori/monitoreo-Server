const { useEffect, useState, useRef } = React;

console.log("ServPulse Dashboard v3.1 Loaded");

// --- UTILS ---

function getDashboardToken() {
  return localStorage.getItem('dashboard_token') || '';
}

function getUserInfo() {
  try {
    const u = localStorage.getItem('user_info');
    return u ? JSON.parse(u) : null;
  } catch { return null; }
}

function useQuery() {
  return { demo: false };
}

function getApiBase() {
  const params = new URLSearchParams(window.location.search);
  const override = params.get('api');
  const stored = localStorage.getItem('api_base');
  let base = override || stored || window.location.origin;
  if (base === 'null' || base.startsWith('file:')) {
      base = 'http://localhost:8000';
  }
  return base.endsWith('/') ? base.slice(0, -1) : base;
}

function fetchJSON(url, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  const token = getDashboardToken();
  if (token) headers['X-Dashboard-Token'] = token;
  const apiBase = getApiBase();
  const fullUrl = url.startsWith('http') ? url : `${apiBase}${url}`;
  return fetch(fullUrl, { ...opts, headers }).then(async (r) => {
    const ct = r.headers.get('content-type') || '';
    if (!r.ok) {
        if (r.status === 401) throw new Error('HTTP 401');
        const txt = await r.text();
        let json;
        try { json = JSON.parse(txt); } catch (e) { throw new Error(txt || `HTTP ${r.status}`); }
        if (json.detail) {
             const d = json.detail;
             if (typeof d === 'string') throw new Error(d);
             if (Array.isArray(d)) throw new Error(d.map(x => x.msg || JSON.stringify(x)).join('; '));
             throw new Error(JSON.stringify(d));
        }
        throw new Error(txt || `HTTP ${r.status}`);
    }
    if (!ct.includes('application/json')) throw new Error('Respuesta no JSON');
    return await r.json();
  });
}

// --- SHARED COMPONENTS ---

function MetricCard({ title, value, subtitle }) {
  return (
    React.createElement('div', { className: 'card' },
      React.createElement('div', { className: 'card-title', style: { marginBottom: '0.5rem', color: 'var(--text-muted)', fontSize: '0.875rem' } }, title),
      React.createElement('div', { style: { fontSize: '2rem', fontWeight: 700, color: 'var(--primary)', marginBottom: '0.25rem' } }, value),
      React.createElement('div', { style: { color: 'var(--text-muted)', fontSize: '0.875rem' } }, subtitle)
    )
  );
}

function LineChart({ labels, data, label, color='var(--primary)' }) {
  const ref = useRef(null);
  const chartColor = color.startsWith('var') ? '#38bdf8' : color;

  useEffect(() => {
    const ctx = ref.current.getContext('2d');
    const chart = new window.Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label,
          data,
          borderColor: chartColor,
          backgroundColor: chartColor,
          tension: 0.3,
          pointRadius: 0,
          borderWidth: 2
        }]
      },
      options: { 
        responsive: true, 
        plugins: { legend: { display: false } },
        scales: {
            x: { grid: { display: false }, ticks: { display: false } },
            y: { grid: { color: '#334155' }, ticks: { color: '#94a3b8' }, beginAtZero: true, max: 100 }
        },
        maintainAspectRatio: false
      }
    });
    return () => chart.destroy();
  }, [labels.join(','), data.join(',')]);
  return React.createElement('div', { style: { height: 150 } }, React.createElement('canvas', { ref }));
}

function BarChart({ labels, data, label, color='#38bdf8' }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current) return;
    const ctx = ref.current.getContext('2d');
    const chart = new window.Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label,
          data,
          backgroundColor: color,
          borderRadius: 4
        }]
      },
      options: { 
        responsive: true, 
        plugins: { legend: { display: false } },
        scales: {
            y: { beginAtZero: true, grid: { color: '#334155' }, ticks: { color: '#94a3b8' } },
            x: { grid: { display: false }, ticks: { color: '#94a3b8' } }
        },
        maintainAspectRatio: false
      }
    });
    return () => chart.destroy();
  }, [JSON.stringify(labels), JSON.stringify(data)]);
  return React.createElement('div', { style: { height: 200 } }, React.createElement('canvas', { ref }));
}

function ThresholdModal({ serverId, onClose }) {
  const [config, setConfig] = useState({ cpu: 80, ram: 80, disk: 80 });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchJSON(`/api/umbrales/${serverId}`).then(setConfig).catch(console.error);
  }, [serverId]);

  const handleSave = async () => {
    try {
      setLoading(true);
      await fetchJSON(`/api/umbrales/${serverId}`, { 
        method: 'POST', 
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify(config)
      });
      onClose();
    } catch (e) { alert(e.message); }
    finally { setLoading(false); }
  };

  return React.createElement('div', { className: 'modal-overlay' },
    React.createElement('div', { className: 'card', style: { width: 400, maxHeight: '90vh', overflowY: 'auto' } },
      React.createElement('div', { className: 'card-title', style: { marginBottom: 20 } }, `Umbrales: ${serverId}`),
      React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 15 } },
        ['cpu', 'ram', 'disk'].map(k => 
          React.createElement('div', { key: k },
            React.createElement('label', { style: { display: 'block', marginBottom: 5, color: 'var(--text-muted)' } }, `${k.toUpperCase()} (%)`),
            React.createElement('input', { type: 'number', value: config[k], onChange: e => setConfig({...config, [k]: parseInt(e.target.value)||0}) })
          )
        )
      ),
      React.createElement('div', { style: { display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 20 } },
        React.createElement('button', { className: 'secondary', onClick: onClose }, 'Cancelar'),
        React.createElement('button', { onClick: handleSave, disabled: loading }, loading ? 'Guardando...' : 'Guardar')
      )
    )
  );
}

function ContainerMonitor({ containers }) {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  
  const filtered = (containers || []).filter(c => {
      const matchSearch = c.name.toLowerCase().includes(search.toLowerCase()) || c.image.toLowerCase().includes(search.toLowerCase());
      const matchStatus = statusFilter === 'all' || c.status.toLowerCase().includes(statusFilter);
      return matchSearch && matchStatus;
  });
  
  return React.createElement('div', { className: 'card' },
    React.createElement('div', { className: 'card-title' }, '🐳 Monitor de Contenedores'),
    React.createElement('div', { style: { display: 'flex', gap: 10, marginBottom: 15 } },
        React.createElement('input', { 
            placeholder: 'Buscar container...', 
            value: search, 
            onChange: e => setSearch(e.target.value), 
            style: { flex: 1, padding: 8, border: '1px solid var(--border)', borderRadius: 4, background: 'var(--bg-body)', color: 'var(--text)' } 
        }),
        React.createElement('select', { 
            value: statusFilter, 
            onChange: e => setStatusFilter(e.target.value),
            style: { padding: 8, border: '1px solid var(--border)', borderRadius: 4, background: 'var(--bg-body)', color: 'var(--text)' }
        },
            React.createElement('option', { value: 'all' }, 'Todos'),
            React.createElement('option', { value: 'up' }, 'Activos'),
            React.createElement('option', { value: 'exited' }, 'Detenidos')
        )
    ),
    React.createElement('div', { style: { overflowX: 'auto' } },
        React.createElement('table', { style: { width: '100%', borderCollapse: 'collapse' } },
            React.createElement('thead', null,
                React.createElement('tr', { style: { borderBottom: '1px solid var(--border)', textAlign: 'left' } },
                    React.createElement('th', { style: { padding: 10 } }, 'Nombre'),
                    React.createElement('th', { style: { padding: 10 } }, 'Imagen'),
                    React.createElement('th', { style: { padding: 10 } }, 'Estado'),
                    React.createElement('th', { style: { padding: 10 } }, 'CPU %'),
                    React.createElement('th', { style: { padding: 10 } }, 'Mem %')
                )
            ),
            React.createElement('tbody', null,
                filtered.length === 0 
                ? React.createElement('tr', null, React.createElement('td', { colSpan: 5, style: { padding: 20, textAlign: 'center' } }, 'No hay contenedores'))
                : filtered.map(c => 
                    React.createElement('tr', { key: c.id || c.name, style: { borderBottom: '1px solid var(--border)' } },
                        React.createElement('td', { style: { padding: 10, fontWeight: 500 } }, c.name),
                        React.createElement('td', { style: { padding: 10, fontSize: '0.85rem', color: 'var(--text-muted)' } }, c.image || '-'),
                        React.createElement('td', { style: { padding: 10 } }, 
                             React.createElement('span', { className: 'badge', style: { 
                                 background: c.status.toLowerCase().includes('up') ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                                 color: c.status.toLowerCase().includes('up') ? '#10b981' : '#ef4444'
                             } }, c.status)
                        ),
                        React.createElement('td', { style: { padding: 10 } }, c.cpu || 0),
                        React.createElement('td', { style: { padding: 10 } }, c.mem || 0)
                    )
                )
            )
        )
    )
  );
}

function ServiceManager({ services, serverId }) {
    const [search, setSearch] = useState('');
    const [processing, setProcessing] = useState(null); // service_name being processed
    const [selectedServices, setSelectedServices] = useState({});

    const filtered = (services || []).filter(s => s.name.toLowerCase().includes(search.toLowerCase()) || (s.display_name && s.display_name.toLowerCase().includes(search.toLowerCase())));

    const handleAction = async (serviceName, action) => {
        if (!confirm(`¿Estás seguro de que quieres ${action} el servicio ${serviceName}?`)) return;
        setProcessing(serviceName);
        try {
            await fetchJSON(`/api/servers/${serverId}/services/action`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ service: serviceName, action })
            });
            alert(`Comando ${action} enviado correctamente. El agente lo ejecutará en breve.`);
        } catch (e) {
            alert(`Error: ${e.message}`);
        } finally {
            setProcessing(null);
        }
    };

    const handleGroupAction = async (action) => {
        const targets = Object.keys(selectedServices).filter(k => selectedServices[k]);
        if (targets.length === 0) return alert("Selecciona al menos un servicio");
        if (!confirm(`¿${action} ${targets.length} servicios seleccionados?`)) return;
        
        setProcessing('GROUP');
        try {
            await fetchJSON(`/api/servers/${serverId}/services/bulk-action`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ services: targets, action })
            });
            alert("Acciones enviadas correctamente. El agente las ejecutará en breve.");
            setSelectedServices({});
        } catch (e) {
            alert(`Error al enviar acciones masivas: ${e.message}`);
        } finally {
            setProcessing(null);
        }
    };

    const toggleSelect = (name) => setSelectedServices(p => ({...p, [name]: !p[name]}));
    const toggleAll = () => {
        if (Object.keys(selectedServices).length === filtered.length) setSelectedServices({});
        else {
            const all = {};
            filtered.forEach(s => all[s.name] = true);
            setSelectedServices(all);
        }
    };

    return React.createElement('div', { className: 'card' },
        React.createElement('div', { className: 'card-title' }, '⚙️ Gestión de Servicios'),
        React.createElement('div', { style: { display: 'flex', gap: 10, marginBottom: 15, flexWrap: 'wrap' } },
             React.createElement('input', { 
                placeholder: 'Buscar servicio...', 
                value: search, 
                onChange: e => setSearch(e.target.value), 
                style: { padding: 8, flex: 1, minWidth: 200, border: '1px solid var(--border)', borderRadius: 4, background: 'var(--bg-body)', color: 'var(--text)' } 
            }),
            React.createElement('button', { className: 'secondary', onClick: () => handleGroupAction('start'), disabled: processing }, 'Iniciar'),
            React.createElement('button', { className: 'secondary', onClick: () => handleGroupAction('stop'), disabled: processing }, 'Detener'),
            React.createElement('button', { className: 'secondary', onClick: () => handleGroupAction('restart'), disabled: processing }, 'Reiniciar'),
            React.createElement('button', { className: 'secondary', onClick: () => handleGroupAction('update'), disabled: processing }, 'Actualizar')
        ),
        React.createElement('div', { style: { overflowX: 'auto', maxHeight: 400, overflowY: 'auto' } },
            React.createElement('table', { style: { width: '100%', borderCollapse: 'collapse' } },
                React.createElement('thead', null,
                    React.createElement('tr', { style: { borderBottom: '1px solid var(--border)', textAlign: 'left' } },
                        React.createElement('th', { style: { padding: 10, width: 30 } }, 
                            React.createElement('input', { type: 'checkbox', checked: filtered.length > 0 && Object.keys(selectedServices).length === filtered.length, onChange: toggleAll })
                        ),
                        React.createElement('th', { style: { padding: 10 } }, 'Nombre'),
                        React.createElement('th', { style: { padding: 10 } }, 'Display Name'),
                        React.createElement('th', { style: { padding: 10 } }, 'Versión'),
                        React.createElement('th', { style: { padding: 10 } }, 'Dependencias'),
                        React.createElement('th', { style: { padding: 10 } }, 'Estado'),
                        React.createElement('th', { style: { padding: 10 } }, 'Acciones')
                    )
                ),
                React.createElement('tbody', null,
                    filtered.length === 0 
                    ? React.createElement('tr', null, React.createElement('td', { colSpan: 6, style: { padding: 20, textAlign: 'center' } }, 'No hay servicios'))
                    : filtered.map(s => 
                        React.createElement('tr', { key: s.name, style: { borderBottom: '1px solid var(--border)', background: selectedServices[s.name] ? 'rgba(var(--primary-rgb), 0.1)' : 'transparent' } },
                            React.createElement('td', { style: { padding: 10 } }, 
                                React.createElement('input', { type: 'checkbox', checked: !!selectedServices[s.name], onChange: () => toggleSelect(s.name) })
                            ),
                            React.createElement('td', { style: { padding: 10 } }, s.name),
                            React.createElement('td', { style: { padding: 10 } }, s.display_name),
                            React.createElement('td', { style: { padding: 10, fontSize: '0.8rem', color: 'var(--text-muted)' } }, s.version || '-'),
                            React.createElement('td', { style: { padding: 10, fontSize: '0.8rem', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, 
                                (s.dependencies || []).join(', ') || '-'
                            ),
                            React.createElement('td', { style: { padding: 10 } }, 
                                React.createElement('span', { className: 'badge', style: { background: s.status === 'running' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)', color: s.status === 'running' ? '#10b981' : '#ef4444' } }, s.status)
                            ),
                            React.createElement('td', { style: { padding: 10, display: 'flex', gap: 5 } },
                                processing === s.name 
                                ? React.createElement('span', { style: { fontSize: '0.8rem' } }, 'Procesando...')
                                : React.createElement(React.Fragment, null,
                                    s.status !== 'running' && React.createElement('button', { className: 'secondary', style: { fontSize: '0.7rem', padding: '2px 6px' }, onClick: () => handleAction(s.name, 'start') }, 'Iniciar'),
                                    s.status === 'running' && React.createElement('button', { className: 'secondary', style: { fontSize: '0.7rem', padding: '2px 6px' }, onClick: () => handleAction(s.name, 'stop') }, 'Detener'),
                                    React.createElement('button', { className: 'secondary', style: { fontSize: '0.7rem', padding: '2px 6px' }, onClick: () => handleAction(s.name, 'restart') }, 'Reiniciar'),
                                    React.createElement('button', { className: 'secondary', style: { fontSize: '0.7rem', padding: '2px 6px' }, onClick: () => handleAction(s.name, 'update') }, 'Actualizar')
                                )
                            )
                        )
                    )
                )
            )
        )
    );
}

function SidebarSettingsModal({ config, setConfig, onClose }) {
    const [activeTab, setActiveTab] = useState('sections');
    const [sectionsExpanded, setSectionsExpanded] = useState(true);
    const [saveState, setSaveState] = useState('idle');
    const [error, setError] = useState('');
    const overlayRef = useRef(null);

    useEffect(() => {
        const handler = (e) => {
            if (e.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, [onClose]);

    useEffect(() => {
        if (saveState === 'saved') {
            const t = setTimeout(() => setSaveState('idle'), 1500);
            return () => clearTimeout(t);
        }
    }, [saveState]);

    const update = (newSections) => {
        const newConfig = { ...config, sections: newSections };
        setConfig(newConfig);
        setSaveState('saving');
        setTimeout(() => setSaveState('saved'), 400);
    };

    const toggle = (index) => {
        const newSections = [...config.sections];
        newSections[index].visible = !newSections[index].visible;
        const visibleCount = newSections.filter(s => s.visible).length;
        if (visibleCount === 0) {
            setError('Debe haber al menos una sección visible');
            return;
        }
        setError('');
        update(newSections);
    };

    const move = (index, direction) => {
        const newSections = [...config.sections];
        if (direction === -1 && index > 0) {
            [newSections[index], newSections[index - 1]] = [newSections[index - 1], newSections[index]];
        } else if (direction === 1 && index < newSections.length - 1) {
            [newSections[index], newSections[index + 1]] = [newSections[index + 1], newSections[index]];
        }
        update(newSections);
    };

    const handleOverlayClick = (e) => {
        if (e.target === overlayRef.current) onClose();
    };

    const visibleCount = (config.sections || []).filter(s => s.visible).length;
    const totalSections = (config.sections || []).length || 1;
    const usagePercent = Math.round((visibleCount / totalSections) * 100);

    const handleReset = () => {
        const resetSections = (config.sections || []).map(s => ({ ...s, visible: true }));
        setError('');
        update(resetSections);
    };

    const general = config.general || {};

    const updateGeneral = (patch) => {
        const newConfig = { ...config, general: { ...general, ...patch } };
        setConfig(newConfig);
        setSaveState('saving');
        setTimeout(() => setSaveState('saved'), 400);
    };

    return React.createElement('div', { className: 'modal-overlay', ref: overlayRef, onClick: handleOverlayClick },
        React.createElement('div', { className: 'card', style: { width: 520, maxWidth: '80vw', maxHeight: '90vh', overflowY: 'auto', position: 'relative', fontSize: '14px' } },
            React.createElement('button', { 
                className: 'secondary', 
                onClick: onClose, 
                style: { position: 'absolute', top: 10, right: 10, padding: '2px 8px', fontSize: '0.75rem' } 
            }, '✕'),
            React.createElement('div', { style: { marginBottom: 16 } },
                React.createElement('div', { className: 'card-title', style: { marginBottom: 4 } }, '🛠️ Configuración de Panel'),
                React.createElement('div', { style: { fontSize: '0.85rem', color: 'var(--text-muted)' } }, 'Elige qué secciones se muestran y el orden en el dashboard.')
            ),
            React.createElement('div', { style: { display: 'flex', gap: 8, marginBottom: 12 } },
                React.createElement('button', { 
                    className: 'secondary', 
                    onClick: () => setActiveTab('sections'),
                    style: { padding: '4px 10px', fontSize: '0.8rem', borderColor: activeTab === 'sections' ? 'var(--primary)' : 'var(--border)', color: activeTab === 'sections' ? 'var(--primary)' : 'var(--text-main)' }
                }, '🧩 Secciones'),
                React.createElement('button', { 
                    className: 'secondary', 
                    onClick: () => setActiveTab('general'),
                    style: { padding: '4px 10px', fontSize: '0.8rem', borderColor: activeTab === 'general' ? 'var(--primary)' : 'var(--border)', color: activeTab === 'general' ? 'var(--primary)' : 'var(--text-main)' }
                }, '⚙️ General')
            ),
            React.createElement('div', { style: { marginBottom: 12 } },
                React.createElement('div', { style: { display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 4 } },
                    React.createElement('span', null, 'Uso del panel'),
                    React.createElement('span', null, visibleCount + '/' + totalSections + ' secciones')
                ),
                React.createElement('div', { style: { height: 6, borderRadius: 999, background: 'var(--bg-body)', overflow: 'hidden' } },
                    React.createElement('div', { style: { width: usagePercent + '%', height: '100%', background: 'var(--primary)' } })
                )
            ),
            activeTab === 'sections' && React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 8 } },
                React.createElement('div', { 
                    style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 8, borderRadius: 6, border: '1px solid var(--border)', cursor: 'pointer', marginBottom: 4 }, 
                    onClick: () => setSectionsExpanded(!sectionsExpanded)
                },
                    React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8 } },
                        React.createElement('span', null, '📋'),
                        React.createElement('span', { style: { fontSize: '0.9rem', fontWeight: 500 } }, 'Secciones del dashboard')
                    ),
                    React.createElement('span', { style: { fontSize: '0.8rem', color: 'var(--text-muted)' } }, sectionsExpanded ? 'Contraer' : 'Expandir')
                ),
                sectionsExpanded && React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 8 } },
            React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 10 } },
                config.sections.map((s, i) => 
                    React.createElement('div', { 
                        key: s.id, 
                        style: { 
                            display: 'flex', 
                            alignItems: 'center', 
                            justifyContent: 'space-between', 
                            padding: 10, 
                            border: '1px solid var(--border)', 
                            borderRadius: 8,
                            background: s.visible ? 'rgba(56, 189, 248, 0.05)' : 'transparent'
                        } 
                    },
                        React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 10 } },
                            React.createElement('input', { type: 'checkbox', checked: s.visible, onChange: () => toggle(i), style: { width: 'auto' } }),
                            React.createElement('div', null,
                                React.createElement('div', { style: { fontSize: '0.9rem', fontWeight: 500 } }, s.label),
                                React.createElement('div', { style: { fontSize: '0.75rem', color: 'var(--text-muted)' } }, i === 0 ? 'Sección principal' : `Posición ${i + 1}`)
                            )
                        ),
                        React.createElement('div', { style: { display: 'flex', gap: 5 } },
                            React.createElement('button', { className: 'secondary', disabled: i === 0, onClick: () => move(i, -1), style: { padding: '4px 8px', fontSize: '0.8rem' } }, '⬆ Arriba'),
                            React.createElement('button', { className: 'secondary', disabled: i === config.sections.length - 1, onClick: () => move(i, 1), style: { padding: '4px 8px', fontSize: '0.8rem' } }, '⬇ Abajo')
                        )
                    )
                )
            ),
                )
            ),
            activeTab === 'general' && React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 12, paddingTop: 4 } },
                React.createElement('div', { style: { padding: 10, borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-element)', display: 'flex', flexDirection: 'column', gap: 4 } },
                    React.createElement('div', { style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between' } },
                        React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8 } },
                            React.createElement('span', null, '📌'),
                            React.createElement('span', { style: { fontWeight: 500, fontSize: '0.9rem' } }, 'Resumen del panel')
                        ),
                        React.createElement('span', { style: { fontSize: '0.75rem', color: 'var(--text-muted)' } }, visibleCount + '/' + totalSections + ' secciones activas')
                    ),
                    React.createElement('div', { style: { fontSize: '0.8rem', color: 'var(--text-muted)' } }, 'Ajusta estos parámetros para adaptar el dashboard a tu forma de trabajar.')
                ),
                React.createElement('div', { style: { padding: 10, borderRadius: 8, border: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 } },
                    React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 3 } },
                        React.createElement('div', { style: { fontSize: '0.9rem', fontWeight: 500 } }, 'Retracción automática del panel lateral'),
                        React.createElement('div', { style: { fontSize: '0.8rem', color: 'var(--text-muted)' } }, 'Oculta el panel cuando no hay actividad para ganar espacio.')
                    ),
                    React.createElement('label', { style: { display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', cursor: 'pointer' } },
                        React.createElement('input', {
                            type: 'checkbox',
                            checked: general.autoCollapseSidebar !== false,
                            onChange: (e) => updateGeneral({ autoCollapseSidebar: e.target.checked }),
                            style: { width: 'auto' }
                        }),
                        React.createElement('span', null, general.autoCollapseSidebar !== false ? 'Activado' : 'Desactivado')
                    )
                )
            ),
            error && React.createElement('div', { style: { marginTop: 10, fontSize: '0.8rem', color: 'var(--danger)' } }, error),
            React.createElement('div', { style: { marginTop: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between' } },
                React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8 } },
                    React.createElement('button', { className: 'secondary', style: { padding: '4px 8px', fontSize: '0.8rem' }, onClick: handleReset }, '⟳ Restablecer'),
                    saveState === 'saving' && React.createElement('span', { style: { fontSize: '0.8rem', color: 'var(--text-muted)' } }, 'Guardando...'),
                    saveState === 'saved' && React.createElement('span', { style: { fontSize: '0.8rem', color: 'var(--success)' } }, 'Guardado')
                ),
                React.createElement('button', { className: 'secondary', onClick: onClose }, 'Cerrar')
            )
        )
    );
}

// --- ADMIN COMPONENTS ---

function ServerAssignmentModal({ user, onClose }) {
    const [allServers, setAllServers] = useState([]);
    const [assignments, setAssignments] = useState({});
    const [loading, setLoading] = useState(true);
    const [groups, setGroups] = useState([]);
    const [selectedGroup, setSelectedGroup] = useState('');

    useEffect(() => {
        const load = async () => {
            try {
                const [serversData, assignedData, groupsData] = await Promise.all([
                    fetchJSON('/api/servers'),
                    fetchJSON(`/api/admin/users/${user.id}/servers`),
                    fetchJSON('/api/admin/groups')
                ]);
                setAllServers(serversData);
                setGroups(groupsData);
                const map = {};
                serversData.forEach(s => { map[s.server_id] = { assigned: false, alerts: true, postman: 'none' }; });
                assignedData.forEach(a => {
                    if (map[a.server_id]) {
                        map[a.server_id].assigned = true;
                        map[a.server_id].alerts = a.receive_alerts;
                        map[a.server_id].postman = a.postman_access_level || 'none';
                    }
                });
                setAssignments(map);
            } catch (e) { alert(e.message); onClose(); } 
            finally { setLoading(false); }
        };
        load();
    }, [user.id]);

    const toggleAssigned = (sid) => setAssignments(p => ({...p, [sid]: {...p[sid], assigned: !p[sid].assigned}}));
    const toggleAlerts = (sid) => setAssignments(p => ({...p, [sid]: {...p[sid], alerts: !p[sid].alerts}}));
    const setPostman = (sid, val) => setAssignments(p => ({...p, [sid]: {...p[sid], postman: val}}));

    const bulkAssignGroupAdmin = () => {
        if (!selectedGroup) return;
        setAssignments(prev => {
            const next = { ...prev };
            allServers.forEach(s => {
                if (s.group_name === selectedGroup) {
                    const st = next[s.server_id] || { assigned: false, alerts: true, postman: 'none' };
                    next[s.server_id] = { ...st, assigned: true, alerts: true, postman: 'admin' };
                }
            });
            return next;
        });
    };

    const bulkUnassignGroup = () => {
        if (!selectedGroup) return;
        setAssignments(prev => {
            const next = { ...prev };
            allServers.forEach(s => {
                if (s.group_name === selectedGroup) {
                    const st = next[s.server_id] || { assigned: false, alerts: true, postman: 'none' };
                    next[s.server_id] = { ...st, assigned: false };
                }
            });
            return next;
        });
    };
    
    const handleSave = async () => {
        try {
            const payload = Object.entries(assignments).filter(([_, v]) => v.assigned).map(([sid, v]) => ({ 
                server_id: sid, 
                receive_alerts: v.alerts,
                postman_access_level: v.postman 
            }));
            await fetchJSON(`/api/admin/users/${user.id}/servers`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ assignments: payload }) });
            onClose();
        } catch (e) { alert(e.message); }
    };

    return React.createElement('div', { className: 'modal-overlay' },
        React.createElement('div', { className: 'card', style: { width: 640, maxHeight: '80vh', overflowY: 'auto' } },
            React.createElement('div', { className: 'card-title', style: { marginBottom: 10 } }, `Asignar a ${user.name || user.email}`),
            !loading && groups.length > 0 && React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, fontSize: '0.85rem' } },
                React.createElement('span', { style: { color: 'var(--text-muted)' } }, 'Admin de grupo:'),
                React.createElement('select', { 
                    value: selectedGroup, 
                    onChange: e => setSelectedGroup(e.target.value),
                    style: { fontSize: '0.8rem' }
                },
                    React.createElement('option', { value: '' }, 'Selecciona un grupo'),
                    groups.map(g => React.createElement('option', { key: g.id, value: g.name }, g.name))
                ),
                React.createElement('button', { 
                    className: 'secondary', 
                    onClick: bulkAssignGroupAdmin, 
                    disabled: !selectedGroup 
                }, 'Asignar todos como Admin'),
                React.createElement('button', { 
                    className: 'secondary', 
                    onClick: bulkUnassignGroup, 
                    disabled: !selectedGroup 
                }, 'Quitar del grupo')
            ),
            loading ? 'Cargando...' : React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 8 } },
                allServers.map(s => {
                    const st = assignments[s.server_id] || { assigned: false, alerts: true, postman: 'none' };
                    const label = s.group_name ? `${s.server_id} (${s.group_name})` : s.server_id;
                    return React.createElement('div', { key: s.server_id, style: { display: 'flex', alignItems: 'center', gap: 10, padding: 10, border: '1px solid var(--border)', borderRadius: 6, background: st.assigned ? 'var(--bg-element)' : 'transparent' } },
                        React.createElement('input', { type: 'checkbox', checked: st.assigned, onChange: () => toggleAssigned(s.server_id), style: { width: 'auto' } }),
                        React.createElement('span', { style: { flex: 1, fontWeight: 500 } }, label),
                        st.assigned && React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 10 } },
                            React.createElement('label', { style: { display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem' } },
                                React.createElement('input', { type: 'checkbox', checked: st.alerts, onChange: () => toggleAlerts(s.server_id), style: { width: 'auto' } }), 'Alertas'
                            ),
                            React.createElement('select', { 
                                value: st.postman, 
                                onChange: e => setPostman(s.server_id, e.target.value),
                                style: { fontSize: '0.8rem', padding: '2px 4px' } 
                            },
                                React.createElement('option', { value: 'none' }, 'Sin Acceso Postman'),
                                React.createElement('option', { value: 'view' }, 'Ver'),
                                React.createElement('option', { value: 'edit' }, 'Editar'),
                                React.createElement('option', { value: 'admin' }, 'Admin')
                            )
                        )
                    );
                })
            ),
            React.createElement('div', { style: { display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 20 } },
                React.createElement('button', { className: 'secondary', onClick: onClose }, 'Cancelar'),
                React.createElement('button', { onClick: handleSave }, 'Guardar')
            )
        )
    );
}

function UserEditModal({ user, onClose, onSave }) {
  const [formData, setFormData] = useState(user || { name: '', email: '', role: 'user', password: '' });

  const handleSubmit = async () => {
    try {
      if (user) {
        await fetchJSON(`/api/admin/users/${user.id}`, { method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify(formData) });
      } else {
        await fetchJSON('/api/register', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(formData) });
      }
      onSave();
    } catch (e) { alert(e.message); }
  };

  return React.createElement('div', { className: 'modal-overlay' },
    React.createElement('div', { className: 'card', style: { width: 400 } },
      React.createElement('div', { className: 'card-title', style: { marginBottom: 20 } }, user ? 'Editar Usuario' : 'Nuevo Usuario'),
      React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 15 } },
        React.createElement('input', { placeholder: 'Nombre', value: formData.name, onChange: e => setFormData({...formData, name: e.target.value}) }),
        React.createElement('input', { placeholder: 'Email', value: formData.email, onChange: e => setFormData({...formData, email: e.target.value}) }),
        React.createElement('select', { value: formData.role, onChange: e => setFormData({...formData, role: e.target.value}) },
          React.createElement('option', { value: 'user' }, 'Usuario'),
          React.createElement('option', { value: 'admin' }, 'Administrador')
        ),
        React.createElement('input', { type: 'password', placeholder: user ? 'Nueva Contraseña (opcional)' : 'Contraseña', value: formData.password || '', onChange: e => setFormData({...formData, password: e.target.value}) })
      ),
      React.createElement('div', { style: { display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 20 } },
        React.createElement('button', { className: 'secondary', onClick: onClose }, 'Cancelar'),
        React.createElement('button', { onClick: handleSubmit }, 'Guardar')
      )
    )
  );
}

function ServerGroupManager() {
  const [groups, setGroups] = useState([]);
  const [servers, setServers] = useState([]);
  const [newGroup, setNewGroup] = useState('');
  const [savingServer, setSavingServer] = useState('');

  const load = () => {
    fetchJSON('/api/admin/groups').then(setGroups).catch(console.error);
    fetchJSON('/api/servers').then(setServers).catch(console.error);
  };

  useEffect(() => { load(); }, []);

  const createGroup = async () => {
    const name = newGroup.trim();
    if (!name) return;
    try {
      await fetchJSON('/api/admin/groups', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ name }) });
      setNewGroup('');
      load();
    } catch (e) { alert(e.message); }
  };

  const deleteGroup = async (id) => {
    if (!confirm('¿Eliminar grupo?')) return;
    try {
      await fetchJSON(`/api/admin/groups/${id}`, { method: 'DELETE' });
      load();
    } catch (e) { alert(e.message); }
  };

  const updateServerGroup = async (serverId, groupName) => {
    try {
      setSavingServer(serverId);
      await fetchJSON(`/api/admin/servers/${encodeURIComponent(serverId)}/group`, {
        method: 'PUT',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ group_name: groupName || null })
      });
      setServers(prev => prev.map(s => s.server_id === serverId ? { ...s, group_name: groupName || null } : s));
    } catch (e) { alert(e.message); }
    finally {
      setSavingServer('');
    }
  };

  const groupCounts = {};
  servers.forEach(s => {
    const g = s.group_name || '';
    groupCounts[g] = (groupCounts[g] || 0) + 1;
  });
  const ungroupedCount = groupCounts[''] || 0;

  return React.createElement('div', { className: 'card' },
    React.createElement('div', { className: 'card-header' },
      React.createElement('div', { className: 'card-title' }, 'Grupos de Servidores'),
      React.createElement('span', { style: { fontSize: '0.8rem', color: 'var(--text-muted)' } }, servers.length + ' servidores')
    ),
    React.createElement('div', { style: { display: 'grid', gridTemplateColumns: 'minmax(0, 260px) minmax(0, 1fr)', gap: 20, alignItems: 'flex-start' } },
      React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 12 } },
        React.createElement('div', { style: { display: 'flex', gap: 8 } },
          React.createElement('input', { placeholder: 'Nombre del grupo', value: newGroup, onChange: e => setNewGroup(e.target.value) }),
          React.createElement('button', { onClick: createGroup }, 'Crear')
        ),
        React.createElement('div', { style: { fontSize: '0.8rem', color: 'var(--text-muted)' } }, 'Organiza los servidores en grupos lógicos (por cliente, entorno, sucursal, etc.).'),
        React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 260, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 8, padding: 8 } },
          React.createElement('div', { style: { display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 4 } },
            React.createElement('span', null, 'Grupos'),
            React.createElement('span', null, 'Servidores')
          ),
          groups.length === 0 && React.createElement('div', { style: { fontSize: '0.8rem', color: 'var(--text-muted)' } }, 'Sin grupos creados'),
          groups.map(g => 
            React.createElement('div', { key: g.id, style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 8, borderRadius: 6, background: 'var(--bg-element)' } },
              React.createElement('div', { style: { display: 'flex', flexDirection: 'column' } },
                React.createElement('span', { style: { fontSize: '0.9rem', fontWeight: 500 } }, g.name),
                React.createElement('span', { style: { fontSize: '0.75rem', color: 'var(--text-muted)' } }, (groupCounts[g.name] || 0) + ' servidores')
              ),
              React.createElement('button', { 
                className: 'secondary', 
                style: { padding: '2px 8px', fontSize: '0.8rem', color: 'var(--danger)', borderColor: 'var(--danger)' }, 
                onClick: () => deleteGroup(g.id),
                disabled: (groupCounts[g.name] || 0) > 0
              }, (groupCounts[g.name] || 0) > 0 ? 'En uso' : 'Eliminar')
            )
          ),
          React.createElement('div', { style: { fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 4 } }, 'Sin grupo: ' + ungroupedCount)
        )
      ),
      React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 10 } },
        React.createElement('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' } },
          React.createElement('div', { style: { fontSize: '0.9rem', fontWeight: 500 } }, 'Asignación de servidores a grupos'),
          React.createElement('div', { style: { fontSize: '0.8rem', color: 'var(--text-muted)' } }, 'Haz clic en el grupo para cambiarlo')
        ),
        React.createElement('div', { style: { overflowX: 'auto' } },
          React.createElement('table', { style: { width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' } },
            React.createElement('thead', null,
              React.createElement('tr', { style: { textAlign: 'left', borderBottom: '1px solid var(--border)' } },
                React.createElement('th', { style: { padding: 8 } }, 'Servidor'),
                React.createElement('th', { style: { padding: 8 } }, 'Grupo'),
                React.createElement('th', { style: { padding: 8 } }, 'Estado')
              )
            ),
            React.createElement('tbody', null,
              servers.length === 0
                ? React.createElement('tr', null, React.createElement('td', { colSpan: 3, style: { padding: 16, textAlign: 'center', color: 'var(--text-muted)' } }, 'Sin servidores registrados'))
                : servers.map(s =>
                    React.createElement('tr', { key: s.server_id, style: { borderBottom: '1px solid var(--border)' } },
                      React.createElement('td', { style: { padding: 8 } }, s.server_id),
                      React.createElement('td', { style: { padding: 8 } },
                        React.createElement('select', {
                          value: s.group_name || '',
                          onChange: e => updateServerGroup(s.server_id, e.target.value),
                          style: { fontSize: '0.8rem' }
                        },
                          React.createElement('option', { value: '' }, 'Sin grupo'),
                          groups.map(g => React.createElement('option', { key: g.id, value: g.name }, g.name))
                        )
                      ),
                      React.createElement('td', { style: { padding: 8, fontSize: '0.8rem', color: 'var(--text-muted)' } },
                        savingServer === s.server_id ? 'Guardando...' : 'Listo'
                      )
                    )
                  )
            )
          )
        )
      )
    )
  );
}

function AlertRulesManager() {
  const [rules, setRules] = useState([]);
  const [newRule, setNewRule] = useState({ alert_type: 'cpu', server_scope: 'global', target_id: '', email: '', extra_emails: '' });
  const [loading, setLoading] = useState(false);

  const load = () => fetchJSON('/api/admin/alert-rules').then(setRules).catch(console.error);
  useEffect(() => { load(); }, []);

  const createRule = async () => {
    try {
      if (newRule.server_scope !== 'global' && !newRule.target_id) {
        alert('Debe especificar el ID del Servidor o Grupo');
        return;
      }
      if (!newRule.email) {
        alert('Debe especificar un email');
        return;
      }
      setLoading(true);
      const payload = {
        alert_type: newRule.alert_type,
        server_scope: newRule.server_scope,
        target_id: newRule.server_scope === 'global' ? null : newRule.target_id,
        emails: [newRule.email],
        extra_emails: newRule.extra_emails ? JSON.stringify(newRule.extra_emails.split(',').map(e => e.trim()).filter(e => e)) : null
      };

      await fetchJSON('/api/admin/alert-rules', { 
        method: 'POST', 
        headers: {'Content-Type':'application/json'}, 
        body: JSON.stringify(payload) 
      });
      setNewRule({ alert_type: 'cpu', server_scope: 'global', target_id: '', email: '', extra_emails: '' });
      load();
    } catch (e) { alert(e.message); }
    finally { setLoading(false); }
  };

  const deleteRule = async (id) => {
    if(!confirm("¿Eliminar regla?")) return;
    try {
      await fetchJSON(`/api/admin/alert-rules/${id}`, { method: 'DELETE' });
      load();
    } catch (e) { alert(e.message); }
  };

  return React.createElement('div', { className: 'card' },
    React.createElement('div', { className: 'card-title' }, 'Reglas de Ruteo de Alertas'),
    React.createElement('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 10, marginBottom: 20 } },
      React.createElement('select', { value: newRule.alert_type, onChange: e => setNewRule({...newRule, alert_type: e.target.value}) },
        ['cpu', 'memory', 'disk', 'offline', 'service_status'].map(m => React.createElement('option', { key: m, value: m }, m.toUpperCase()))
      ),
      React.createElement('select', { value: newRule.server_scope, onChange: e => setNewRule({...newRule, server_scope: e.target.value}) },
        React.createElement('option', { value: 'global' }, 'Global'),
        React.createElement('option', { value: 'server' }, 'Servidor'),
        React.createElement('option', { value: 'group' }, 'Grupo')
      ),
      newRule.server_scope !== 'global' && React.createElement('input', { 
        placeholder: newRule.server_scope === 'server' ? 'Server ID' : 'Nombre Grupo', 
        value: newRule.target_id, 
        onChange: e => setNewRule({...newRule, target_id: e.target.value}) 
      }),
      React.createElement('input', { placeholder: 'Email destino', value: newRule.email, onChange: e => setNewRule({...newRule, email: e.target.value}) }),
      React.createElement('input', { placeholder: 'CC (separar por comas)', value: newRule.extra_emails, onChange: e => setNewRule({...newRule, extra_emails: e.target.value}) }),
      React.createElement('button', { onClick: createRule, disabled: loading }, loading ? '...' : 'Añadir')
    ),
    React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 10 } },
      rules.map(r => 
        React.createElement('div', { key: r.id, style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 10, border: '1px solid var(--border)', borderRadius: 6 } },
          React.createElement('div', null, 
            React.createElement('div', { style: { fontWeight: 'bold' } }, r.alert_type.toUpperCase()),
            React.createElement('div', { style: { fontSize: '0.85rem', color: 'var(--text-muted)' } }, 
              `${r.server_scope.toUpperCase()} ${r.target_id ? `(${r.target_id})` : ''} -> ${r.emails && r.emails.join(', ')}${r.extra_emails ? ' + CC: ' + JSON.parse(r.extra_emails).join(', ') : ''}`
            )
          ),
          React.createElement('button', { className: 'secondary', style: { padding: '2px 8px', fontSize: '0.8rem', color: 'var(--danger)', borderColor: 'var(--danger)' }, onClick: () => deleteRule(r.id) }, 'Eliminar')
        )
      )
    )
  );
}

function AdminPanel() {
  const [tab, setTab] = useState('users');
  const [users, setUsers] = useState([]);
  const [editingUser, setEditingUser] = useState(null);
  const [assigningUser, setAssigningUser] = useState(null);

  const loadUsers = () => fetchJSON('/api/admin/users').then(setUsers).catch(console.error);

  useEffect(() => { if (tab === 'users') loadUsers(); }, [tab]);

  const deleteUser = async (id) => {
    if (!confirm('¿Eliminar usuario?')) return;
    try { await fetchJSON(`/api/admin/users/${id}`, { method: 'DELETE' }); loadUsers(); } catch (e) { alert(e.message); }
  };

  return React.createElement('div', { className: 'fade-in' },
    React.createElement('div', { style: { display: 'flex', gap: 10, marginBottom: 20, overflowX: 'auto', paddingBottom: 5 } },
      ['users', 'groups', 'alerts'].map(t => 
        React.createElement('button', { 
          key: t, 
          className: tab === t ? '' : 'secondary',
          onClick: () => setTab(t)
        }, t === 'users' ? 'Usuarios' : t === 'groups' ? 'Grupos' : 'Alertas')
      )
    ),
    
    tab === 'users' && React.createElement('div', { className: 'card' },
      React.createElement('div', { className: 'card-header' },
        React.createElement('div', { className: 'card-title' }, 'Gestión de Usuarios'),
        React.createElement('button', { onClick: () => setEditingUser({}) }, 'Nuevo Usuario')
      ),
      React.createElement('table', { style: { width: '100%', borderCollapse: 'collapse', marginTop: 15 } },
        React.createElement('thead', null,
          React.createElement('tr', { style: { textAlign: 'left', borderBottom: '1px solid var(--border)' } },
            React.createElement('th', { style: { padding: 10 } }, 'Nombre'),
            React.createElement('th', { style: { padding: 10 } }, 'Email'),
            React.createElement('th', { style: { padding: 10 } }, 'Rol'),
            React.createElement('th', { style: { padding: 10 } }, 'Acciones')
          )
        ),
        React.createElement('tbody', null,
          users.map(u => 
            React.createElement('tr', { key: u.id, style: { borderBottom: '1px solid var(--border)' } },
              React.createElement('td', { style: { padding: 10 } }, u.name),
              React.createElement('td', { style: { padding: 10 } }, u.email),
              React.createElement('td', { style: { padding: 10 } }, u.role),
              React.createElement('td', { style: { padding: 10, display: 'flex', gap: 5 } },
                React.createElement('button', { className: 'secondary', style: { padding: '4px 8px', fontSize: '0.8rem' }, onClick: () => setEditingUser(u) }, 'Editar'),
                React.createElement('button', { className: 'secondary', style: { padding: '4px 8px', fontSize: '0.8rem' }, onClick: () => setAssigningUser(u) }, 'Servidores'),
                React.createElement('button', { className: 'secondary', style: { padding: '4px 8px', fontSize: '0.8rem', color: 'var(--danger)', borderColor: 'var(--danger)' }, onClick: () => deleteUser(u.id) }, 'Eliminar')
              )
            )
          )
        )
      )
    ),

    tab === 'groups' && React.createElement(ServerGroupManager),
    tab === 'alerts' && React.createElement(AlertRulesManager),

    editingUser && React.createElement(UserEditModal, { user: editingUser.id ? editingUser : null, onClose: () => setEditingUser(null), onSave: () => { setEditingUser(null); loadUsers(); } }),
    assigningUser && React.createElement(ServerAssignmentModal, { user: assigningUser, onClose: () => setAssigningUser(null) })
  );
}

function DataMonitoringDashboard({ currentServer, userInfo }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      if (!currentServer) {
        setData([]);
        setError(null);
        setLoading(false);
        return;
      }
      const url = '/api/data-monitoring?limit=50&entity_id=' + encodeURIComponent(currentServer.server_id);
      const res = await fetchJSON(url);
      setData(res);
      setError(null);
    } catch (err) { setError(err.message); } 
    finally { setLoading(false); }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [currentServer && currentServer.server_id]);

  const flowCounts = {};
  data.forEach(d => { const f = d.flow || 'Unknown'; flowCounts[f] = (flowCounts[f] || 0) + 1; });
  const chartLabels = Object.keys(flowCounts);
  const chartData = Object.values(flowCounts);

  if (!userInfo) return null;

  const isAdmin = !!userInfo.is_admin;
  const hasGlobalDM = !!userInfo.can_view_data_monitoring;

  if (!currentServer || !currentServer.data_monitoring_enabled) {
    if (isAdmin || hasGlobalDM) {
      return React.createElement('div', { className: 'card' }, 'Este servidor no tiene el dashboard de Postman habilitado');
    }
    return null;
  }

  const accessLevel = currentServer.postman_access_level || 'none';
  if (!isAdmin && !hasGlobalDM && accessLevel === 'none') {
    return React.createElement('div', { className: 'card' }, '⛔ Acceso denegado al panel Postman');
  }

  const canEdit = accessLevel === 'edit' || accessLevel === 'admin' || isAdmin;

  return React.createElement('div', { className: 'card' },
    React.createElement('div', { className: 'card-header' },
      React.createElement('div', { className: 'card-title' }, '📊 Dashboard Postman'),
      React.createElement('div', { style: { display: 'flex', gap: 8 } },
        canEdit && React.createElement('button', { className: 'secondary', onClick: () => alert('Funcionalidad de edición en desarrollo') }, '✏️ Editar'),
        React.createElement('button', { className: 'secondary', onClick: fetchData }, 'Refrescar')
      )
    ),
    error && React.createElement('div', { style: { color: 'var(--danger)', marginBottom: 15 } }, error),
    
    chartLabels.length > 0 && React.createElement('div', { style: { marginBottom: 24 } },
        React.createElement(BarChart, { labels: chartLabels, data: chartData, label: 'Eventos' })
    ),

    React.createElement('div', { style: { overflowX: 'auto' } },
      React.createElement('table', { style: { width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' } },
        React.createElement('thead', null,
          React.createElement('tr', { style: { textAlign: 'left', borderBottom: '1px solid var(--border)' } },
            ['ID', 'App', 'Caja', 'User', 'Flujo', 'Patente', 'Tipo', 'Prod', 'Fecha', 'Env'].map(h => 
                React.createElement('th', { key: h, style: { padding: '10px', color: 'var(--text-muted)' } }, h)
            )
          )
        ),
        React.createElement('tbody', null,
          data.length === 0 
            ? React.createElement('tr', null, React.createElement('td', { colSpan: 10, style: { padding: 20, textAlign: 'center', color: 'var(--text-muted)' } }, 'Sin datos'))
            : data.map(row => 
                React.createElement('tr', { key: row.id, style: { borderBottom: '1px solid var(--border)' } },
                  React.createElement('td', { style: { padding: '10px' } }, row.id),
                  React.createElement('td', { style: { padding: '10px' } }, row.app),
                  React.createElement('td', { style: { padding: '10px' } }, row.cashRegisterNumber),
                  React.createElement('td', { style: { padding: '10px' } }, row.userName),
                  React.createElement('td', { style: { padding: '10px' } }, row.flow),
                  React.createElement('td', { style: { padding: '10px' } }, row.patent || '-'),
                  React.createElement('td', { style: { padding: '10px' } }, row.vehicleType || '-'),
                  React.createElement('td', { style: { padding: '10px' } }, row.product || '-'),
                  React.createElement('td', { style: { padding: '10px' } }, new Date(row.received_at).toLocaleString()),
                  React.createElement('td', { style: { padding: '10px' } }, row.environment || '-')
                )
            )
        )
      )
    )
  );
}

// --- MAIN APP ---

function App() {
  const { demo } = useQuery();
  const [authed, setAuthed] = useState(!!getDashboardToken());
  const [userInfo, setUserInfo] = useState(getUserInfo());
  const [currentView, setCurrentView] = useState('dashboard');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const inactivityTimerRef = useRef(null);
  
  // Sidebar Config
  const [sidebarConfig, setSidebarConfig] = useState(() => {
      // 1. Try from userInfo (backend persistence)
      const u = getUserInfo();
      if (u && u.sidebar_config) return u.sidebar_config;

      // 2. Try from localStorage (legacy/fallback)
      try {
          const s = localStorage.getItem('sidebar_config');
          if (s) {
              const parsed = JSON.parse(s);
              if (!parsed.sections) {
                  return {
                      sections: [
                          { id: 'containers', label: '🐳 Monitor Contenedores', visible: parsed.showContainers !== false },
                          { id: 'services', label: '⚙️ Gestión Servicios', visible: parsed.showServices !== false },
                          { id: 'postman', label: '📊 Postman Dashboard', visible: parsed.showPostman !== false }
                      ],
                      general: { autoCollapseSidebar: true }
                  };
              }
              if (!parsed.general) {
                  parsed.general = { autoCollapseSidebar: true };
              }
              return parsed;
          }
      } catch {}
      
      // 3. Default
      return {
          sections: [
              { id: 'containers', label: '🐳 Monitor Contenedores', visible: true },
              { id: 'services', label: '⚙️ Gestión Servicios', visible: true },
              { id: 'postman', label: '📊 Postman Dashboard', visible: true }
          ],
          general: { autoCollapseSidebar: true }
      };
  });
  
  // Auto-save Sidebar Config
  useEffect(() => {
      if (!authed) return;
      
      // Save to local storage for offline/fast load
      localStorage.setItem('sidebar_config', JSON.stringify(sidebarConfig));
      
      // Debounce save to backend
      const timer = setTimeout(() => {
          fetchJSON('/api/user/sidebar-config', {
              method: 'PUT',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({ config: sidebarConfig })
          }).catch(err => console.error("Error saving sidebar config:", err));
      }, 2000);
      
      return () => clearTimeout(timer);
  }, [sidebarConfig, authed]);

  useEffect(() => {
      if (!authed) return;
      const autoCollapse = !sidebarConfig.general || sidebarConfig.general.autoCollapseSidebar !== false;
      if (!autoCollapse) return;
      const handleActivity = () => {
          if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
          inactivityTimerRef.current = setTimeout(() => {
              setSidebarCollapsed(true);
          }, 3000);
      };
      window.addEventListener('mousemove', handleActivity);
      window.addEventListener('keydown', handleActivity);
      handleActivity();
      return () => {
          window.removeEventListener('mousemove', handleActivity);
          window.removeEventListener('keydown', handleActivity);
          if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
      };
  }, [authed, sidebarConfig.general && sidebarConfig.general.autoCollapseSidebar]);

  const [showSidebarSettings, setShowSidebarSettings] = useState(false);

  // Login State
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');

  // Dashboard State
  const [servers, setServers] = useState([]);
  const [selected, setSelected] = useState('');
  const [history, setHistory] = useState([]);
  const [status, setStatus] = useState({ ok: true, message: '' });
  const [editingThresholds, setEditingThresholds] = useState(null);

  // LOAD DATA
  const load = async () => {
    if (!getDashboardToken() && !demo) return;
    try {
      const [health, ss] = await Promise.all([fetchJSON('/api/health'), fetchJSON('/api/servers')]);
      if (!health.ok) throw new Error(health.error || 'Backend Error');
      setServers(ss);
      setStatus({ ok: true, message: '' });
    } catch (e) {
      if (e.message.includes('HTTP 401')) handleLogout();
      else setStatus({ ok: false, message: e.message });
    }
  };

  useEffect(() => {
    if (authed) {
        load();
        const i = setInterval(load, 30000);
        return () => clearInterval(i);
    }
  }, [authed]);

  // HISTORY POLLING
  useEffect(() => {
    if (authed && selected) {
        const fetchHistory = async () => {
            try {
                const h = await fetchJSON(`/api/metrics/history?server_id=${encodeURIComponent(selected)}&limit=100`);
                setHistory(h);
            } catch {}
        };
        fetchHistory();
        const i = setInterval(fetchHistory, 30000);
        return () => clearInterval(i);
    }
  }, [selected, authed]);

  const handleLogin = async () => {
    try {
      const res = await fetchJSON('/api/login', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ email, password }) });
      if (res.token) {
        localStorage.setItem('dashboard_token', res.token);
        localStorage.setItem('user_info', JSON.stringify(res));
        setUserInfo(res);
        if (res.sidebar_config) setSidebarConfig(res.sidebar_config);
        setAuthed(true);
      }
    } catch (e) { setLoginError(e.message); }
  };

  const handleLogout = () => {
    localStorage.removeItem('dashboard_token');
    localStorage.removeItem('user_info');
    setAuthed(false);
    setUserInfo(null);
  };

  if (!authed) {
    return React.createElement('div', { style: { display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', background: 'var(--bg-body)' } },
        React.createElement('div', { className: 'card', style: { width: 400, margin: 0 } },
            React.createElement('div', { className: 'card-title', style: { textAlign: 'center', marginBottom: 20 } }, '🔐 Acceso ServPulse'),
            React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 15 } },
                React.createElement('input', { placeholder: 'Email', value: email, onChange: e => setEmail(e.target.value) }),
                React.createElement('input', { type: 'password', placeholder: 'Contraseña', value: password, onChange: e => setPassword(e.target.value) }),
                loginError && React.createElement('div', { style: { color: 'var(--danger)' } }, loginError),
                React.createElement('button', { onClick: handleLogin }, 'Iniciar Sesión')
            )
        )
    );
  }

  const Sidebar = () => React.createElement('div', { className: sidebarCollapsed ? 'sidebar sidebar-collapsed' : 'sidebar', onMouseEnter: () => { if (sidebarCollapsed) setSidebarCollapsed(false); } },
    React.createElement('div', { className: 'sidebar-header' }, 
        React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8, flex: 1 } },
            React.createElement('span', null, '⚡'),
            !sidebarCollapsed && React.createElement('span', null, 'ServPulse')
        ),
        React.createElement('button', { 
            className: 'secondary', 
            onClick: () => setSidebarCollapsed(!sidebarCollapsed),
            style: { padding: '4px 8px', fontSize: '0.75rem' } 
        }, sidebarCollapsed ? '⮞' : '⮜')
    ),
    React.createElement('div', { className: 'sidebar-nav' },
        React.createElement('div', { className: `nav-item ${currentView === 'dashboard' ? 'active' : ''}`, onClick: () => setCurrentView('dashboard') }, sidebarCollapsed ? '📊' : '📊 Dashboard'),
        userInfo?.is_admin && React.createElement('div', { className: `nav-item ${currentView === 'admin' ? 'active' : ''}`, onClick: () => setCurrentView('admin') }, sidebarCollapsed ? '⚙️' : '⚙️ Administración')
    ),
    React.createElement('div', { className: 'sidebar-footer' },
        React.createElement('button', { 
            className: 'secondary', 
            style: { width: '100%', marginBottom: 10, fontSize: '0.85rem' }, 
            onClick: () => setShowSidebarSettings(true) 
        }, sidebarCollapsed ? '🛠️' : '🛠️ Configuración Panel'),
        !sidebarCollapsed && React.createElement('div', { style: { fontSize: '0.9rem', marginBottom: 10, color: 'var(--text-muted)' } }, userInfo?.name),
        React.createElement('button', { 
            className: 'secondary', 
            style: { width: '100%' }, 
            onClick: handleLogout 
        }, sidebarCollapsed ? '⏻' : 'Salir')
    )
  );

  const DashboardView = () => {
    if (!selected) {
        return React.createElement('div', { className: 'fade-in' },
            React.createElement('h2', { style: { marginBottom: 20 } }, 'Mis Servidores'),
            servers.length === 0 
                ? React.createElement('div', { className: 'card' }, 'No tienes servidores asignados.')
                : React.createElement('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 20 } },
                    servers.map(s => 
                        React.createElement('div', { 
                            key: s.server_id, 
                            className: 'card',
                            style: { cursor: 'pointer', transition: 'all 0.2s', border: '1px solid var(--border)' },
                            onMouseEnter: (e) => e.currentTarget.style.borderColor = 'var(--primary)',
                            onMouseLeave: (e) => e.currentTarget.style.borderColor = 'var(--border)',
                            onClick: () => setSelected(s.server_id)
                        },
                            React.createElement('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 } },
                                React.createElement('div', { style: { fontWeight: 'bold', fontSize: '1.1rem' } }, s.server_id),
                                React.createElement('span', { style: { fontSize: '1.5rem' } }, '🖥️')
                            ),
                            React.createElement('div', { style: { color: 'var(--text-muted)', fontSize: '0.9rem' } }, s.group_name ? `Grupo: ${s.group_name}` : 'Sin Grupo'),
                            React.createElement('div', { style: { marginTop: 15, fontSize: '0.85rem', color: 'var(--primary)' } }, 'Ver Métricas →')
                        )
                    )
                )
        );
    }

    const latest = history[history.length - 1] || { cpu:{total:0}, memory:{used:0,total:0}, disk:{percent:0,used:0,total:0}, docker:{running_containers:0} };
    const cpuData = history.map(h => h.cpu.total);
    const memData = history.map(h => Math.round((h.memory.used / h.memory.total) * 100));
    
    return React.createElement('div', { className: 'fade-in' },
        !status.ok && React.createElement('div', { style: { padding: 15, background: 'rgba(239,68,68,0.1)', border: '1px solid var(--danger)', color: 'var(--danger)', borderRadius: 8, marginBottom: 20 } }, status.message),
        
        React.createElement('div', { className: 'card', style: { display: 'flex', gap: 15, alignItems: 'center', flexWrap: 'wrap' } },
            React.createElement('button', { className: 'secondary', onClick: () => setSelected('') }, '⬅ Volver'),
            React.createElement('div', { style: { display: 'flex', flexDirection: 'column' } },
                React.createElement('span', { style: { fontWeight: 'bold', fontSize: '1.1rem' } }, selected),
                React.createElement('span', { style: { fontSize: '0.8rem', color: 'var(--text-muted)' } }, servers.find(s=>s.server_id===selected)?.group_name || '')
            ),
            React.createElement('span', { className: 'badge', style: { background: 'var(--bg-element)', padding: '4px 8px', borderRadius: 4, fontSize: '0.8rem', marginLeft: 10 } }, 'Conectado'),
            React.createElement('div', { style: { marginLeft: 'auto' } },
                React.createElement('button', { className: 'secondary', onClick: () => setEditingThresholds(selected) }, 'Configurar Umbrales')
            )
        ),

        React.createElement('div', { className: 'grid-3' },
            React.createElement(MetricCard, { title: 'CPU Total', value: `${latest.cpu.total || 0}%`, subtitle: 'Carga del sistema' }),
            React.createElement(MetricCard, { title: 'Memoria', value: `${Math.round((latest.memory.used / latest.memory.total) * 100) || 0}%`, subtitle: `${(latest.memory.used/1024).toFixed(1)} / ${(latest.memory.total/1024).toFixed(1)} GB` }),
            React.createElement(MetricCard, { title: 'Disco', value: `${Math.round(latest.disk.percent) || 0}%`, subtitle: `${latest.disk.used} / ${latest.disk.total} GB` })
        ),

        React.createElement('div', { className: 'grid-2' },
            React.createElement('div', { className: 'card' },
                React.createElement('div', { className: 'card-title' }, 'Historial CPU'),
                React.createElement(LineChart, { labels: history.map(h => new Date(h.ts).toLocaleTimeString()), data: cpuData, label: 'CPU %' })
            ),
            React.createElement('div', { className: 'card' },
                React.createElement('div', { className: 'card-title' }, 'Historial Memoria'),
                React.createElement(LineChart, { labels: history.map(h => new Date(h.ts).toLocaleTimeString()), data: memData, label: 'Memoria %' })
            )
        ),

        (sidebarConfig.sections || []).filter(s => s.visible).map(s => {
            if (s.id === 'containers') return React.createElement(ContainerMonitor, { key: s.id, containers: latest.docker?.containers });
            if (s.id === 'services') return React.createElement(ServiceManager, { key: s.id, services: latest.services, serverId: selected });
            if (s.id === 'postman') return React.createElement(DataMonitoringDashboard, { key: s.id, currentServer: servers.find(s => s.server_id === selected), userInfo });
            return null;
        }),

        editingThresholds && React.createElement(ThresholdModal, { serverId: editingThresholds, onClose: () => setEditingThresholds(null) })
    );
  };

  return React.createElement('div', { className: 'app-container' },
    React.createElement(Sidebar),
    React.createElement('main', { className: sidebarCollapsed ? 'main-content main-content-collapsed' : 'main-content' },
        currentView === 'dashboard' ? React.createElement(DashboardView) : React.createElement(AdminPanel)
    ),
    showSidebarSettings && React.createElement(SidebarSettingsModal, { config: sidebarConfig, setConfig: setSidebarConfig, onClose: () => setShowSidebarSettings(false) })
  );
}

const root = window.ReactDOM.createRoot(document.getElementById('root'));
root.render(window.React.createElement(App));
