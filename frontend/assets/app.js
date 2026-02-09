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

// --- ADMIN COMPONENTS ---

function ServerAssignmentModal({ user, onClose }) {
    const [allServers, setAllServers] = useState([]);
    const [assignments, setAssignments] = useState({});
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const load = async () => {
            try {
                const [serversData, assignedData] = await Promise.all([
                    fetchJSON('/api/servers'),
                    fetchJSON(`/api/admin/users/${user.id}/servers`)
                ]);
                setAllServers(serversData);
                const map = {};
                serversData.forEach(s => { map[s.server_id] = { assigned: false, alerts: true }; });
                assignedData.forEach(a => {
                    if (map[a.server_id]) {
                        map[a.server_id].assigned = true;
                        map[a.server_id].alerts = a.receive_alerts;
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
    
    const handleSave = async () => {
        try {
            const payload = Object.entries(assignments).filter(([_, v]) => v.assigned).map(([sid, v]) => ({ server_id: sid, receive_alerts: v.alerts }));
            await fetchJSON(`/api/admin/users/${user.id}/servers`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ assignments: payload }) });
            onClose();
        } catch (e) { alert(e.message); }
    };

    return React.createElement('div', { className: 'modal-overlay' },
        React.createElement('div', { className: 'card', style: { width: 600, maxHeight: '80vh', overflowY: 'auto' } },
            React.createElement('div', { className: 'card-title', style: { marginBottom: 10 } }, `Asignar a ${user.name || user.email}`),
            loading ? 'Cargando...' : React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 8 } },
                allServers.map(s => {
                    const st = assignments[s.server_id] || { assigned: false, alerts: true };
                    return React.createElement('div', { key: s.server_id, style: { display: 'flex', alignItems: 'center', gap: 10, padding: 10, border: '1px solid var(--border)', borderRadius: 6, background: st.assigned ? 'var(--bg-element)' : 'transparent' } },
                        React.createElement('input', { type: 'checkbox', checked: st.assigned, onChange: () => toggleAssigned(s.server_id), style: { width: 'auto' } }),
                        React.createElement('span', { style: { flex: 1, fontWeight: 500 } }, s.server_id),
                        st.assigned && React.createElement('label', { style: { display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem' } },
                            React.createElement('input', { type: 'checkbox', checked: st.alerts, onChange: () => toggleAlerts(s.server_id), style: { width: 'auto' } }), 'Alertas'
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
  const [newGroup, setNewGroup] = useState('');

  const load = () => fetchJSON('/api/admin/groups').then(setGroups).catch(console.error);
  useEffect(() => { load(); }, []);

  const createGroup = async () => {
    if (!newGroup) return;
    try {
      await fetchJSON('/api/admin/groups', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ name: newGroup }) });
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

  return React.createElement('div', { className: 'card' },
    React.createElement('div', { className: 'card-title' }, 'Grupos de Servidores'),
    React.createElement('div', { style: { display: 'flex', gap: 10, marginBottom: 20 } },
      React.createElement('input', { placeholder: 'Nombre del grupo', value: newGroup, onChange: e => setNewGroup(e.target.value) }),
      React.createElement('button', { onClick: createGroup }, 'Crear')
    ),
    React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 10 } },
      groups.map(g => 
        React.createElement('div', { key: g.id, style: { display: 'flex', justifyContent: 'space-between', padding: 10, border: '1px solid var(--border)', borderRadius: 6 } },
          React.createElement('span', null, g.name),
          React.createElement('button', { className: 'secondary', style: { padding: '2px 8px', fontSize: '0.8rem' }, onClick: () => deleteGroup(g.id) }, 'Eliminar')
        )
      )
    )
  );
}

function AlertRulesManager() {
  const [rules, setRules] = useState([]);
  const [newRule, setNewRule] = useState({ alert_type: 'cpu', server_scope: 'global', target_id: '', email: '' });
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
        emails: [newRule.email]
      };

      await fetchJSON('/api/admin/alert-rules', { 
        method: 'POST', 
        headers: {'Content-Type':'application/json'}, 
        body: JSON.stringify(payload) 
      });
      setNewRule({ alert_type: 'cpu', server_scope: 'global', target_id: '', email: '' });
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
        ['cpu', 'memory', 'disk', 'offline'].map(m => React.createElement('option', { key: m, value: m }, m.toUpperCase()))
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
      React.createElement('button', { onClick: createRule, disabled: loading }, loading ? '...' : 'Añadir')
    ),
    React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 10 } },
      rules.map(r => 
        React.createElement('div', { key: r.id, style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 10, border: '1px solid var(--border)', borderRadius: 6 } },
          React.createElement('div', null, 
            React.createElement('div', { style: { fontWeight: 'bold' } }, r.alert_type.toUpperCase()),
            React.createElement('div', { style: { fontSize: '0.85rem', color: 'var(--text-muted)' } }, 
              `${r.server_scope.toUpperCase()} ${r.target_id ? `(${r.target_id})` : ''} -> ${r.emails && r.emails.join(', ')}`
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

// --- DASHBOARD COMPONENT ---

function DataMonitoringDashboard({ currentServer, userInfo }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      const res = await fetchJSON('/api/data-monitoring?limit=50');
      setData(res);
      setError(null);
    } catch (err) { setError(err.message); } 
    finally { setLoading(false); }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const flowCounts = {};
  data.forEach(d => { const f = d.flow || 'Unknown'; flowCounts[f] = (flowCounts[f] || 0) + 1; });
  const chartLabels = Object.keys(flowCounts);
  const chartData = Object.values(flowCounts);

  if (!userInfo || (!userInfo.is_admin && !userInfo.can_view_data_monitoring)) return null;
  if (!currentServer || !currentServer.data_monitoring_enabled) return null;

  return React.createElement('div', { className: 'card' },
    React.createElement('div', { className: 'card-header' },
      React.createElement('div', { className: 'card-title' }, '📊 Dashboard Postman'),
      React.createElement('div', { style: { display: 'flex', gap: 8 } },
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

  const Sidebar = () => React.createElement('div', { className: 'sidebar' },
    React.createElement('div', { className: 'sidebar-header' }, 
        React.createElement('span', { style: { marginRight: 8 } }, '⚡'), 'ServPulse'
    ),
    React.createElement('div', { className: 'sidebar-nav' },
        React.createElement('div', { className: `nav-item ${currentView === 'dashboard' ? 'active' : ''}`, onClick: () => setCurrentView('dashboard') }, '📊 Dashboard'),
        userInfo?.is_admin && React.createElement('div', { className: `nav-item ${currentView === 'admin' ? 'active' : ''}`, onClick: () => setCurrentView('admin') }, '⚙️ Administración')
    ),
    React.createElement('div', { className: 'sidebar-footer' },
        React.createElement('div', { style: { fontSize: '0.9rem', marginBottom: 10, color: 'var(--text-muted)' } }, userInfo?.name),
        React.createElement('button', { className: 'secondary', style: { width: '100%' }, onClick: handleLogout }, 'Salir')
    )
  );

  const DashboardView = () => {
    const latest = history[history.length - 1] || { cpu:{total:0}, memory:{used:0,total:0}, disk:{percent:0,used:0,total:0}, docker:{running_containers:0} };
    const cpuData = history.map(h => h.cpu.total);
    const memData = history.map(h => Math.round((h.memory.used / h.memory.total) * 100));
    
    return React.createElement('div', { className: 'fade-in' },
        !status.ok && React.createElement('div', { style: { padding: 15, background: 'rgba(239,68,68,0.1)', border: '1px solid var(--danger)', color: 'var(--danger)', borderRadius: 8, marginBottom: 20 } }, status.message),
        
        React.createElement('div', { className: 'card', style: { display: 'flex', gap: 15, alignItems: 'center', flexWrap: 'wrap' } },
            React.createElement('span', { style: { color: 'var(--text-muted)' } }, 'Servidor:'),
            React.createElement('select', { value: selected, onChange: e => setSelected(e.target.value), style: { width: 'auto', minWidth: 200 } },
                servers.length === 0 ? React.createElement('option', null, 'Sin servidores') :
                servers.map(s => React.createElement('option', { key: s.server_id, value: s.server_id }, `${s.server_id} ${s.group_name ? `(${s.group_name})` : ''}`))
            ),
            selected && React.createElement('span', { className: 'badge', style: { background: 'var(--bg-element)', padding: '4px 8px', borderRadius: 4, fontSize: '0.8rem' } }, 'Conectado'),
            React.createElement('div', { style: { marginLeft: 'auto' } },
                selected && React.createElement('button', { className: 'secondary', onClick: () => setEditingThresholds(selected) }, 'Configurar Umbrales')
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

        React.createElement(DataMonitoringDashboard, { currentServer: servers.find(s => s.server_id === selected), userInfo }),

        editingThresholds && React.createElement(ThresholdModal, { serverId: editingThresholds, onClose: () => setEditingThresholds(null) })
    );
  };

  return React.createElement('div', { className: 'app-container' },
    React.createElement(Sidebar),
    React.createElement('main', { className: 'main-content' },
        currentView === 'dashboard' ? React.createElement(DashboardView) : React.createElement(AdminPanel)
    )
  );
}

const root = window.ReactDOM.createRoot(document.getElementById('root'));
root.render(window.React.createElement(App));