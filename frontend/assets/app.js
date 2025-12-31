const { useEffect, useState, useRef } = React;

// Token del dashboard solo desde localStorage (emitido por login)
function getDashboardToken() {
  const token = localStorage.getItem('dashboard_token') || '';
  return token;
}

function getUserInfo() {
  try {
    const u = localStorage.getItem('user_info');
    return u ? JSON.parse(u) : null;
  } catch { return null; }
}

function useQuery() {
  // Deshabilitar demo en producción: siempre requiere login
  return { demo: false };
}

function getApiBase() {
  const params = new URLSearchParams(window.location.search);
  const override = params.get('api');
  const stored = localStorage.getItem('api_base');
  const base = override || stored || window.location.origin;
  const normalized = base.endsWith('/') ? base.slice(0, -1) : base;
  if (override && override !== stored) {
    try { localStorage.setItem('api_base', normalized); } catch {}
  }
  return normalized;
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
        try {
            const json = JSON.parse(txt);
            throw new Error(json.detail || `HTTP ${r.status}`);
        } catch (e) {
             throw new Error(txt || `HTTP ${r.status}`);
        }
    }
    if (!ct.includes('application/json')) throw new Error('Respuesta no JSON');
    return await r.json();
  });
}

function rand(n) { return Math.round(Math.random() * n); }

function MetricCard({ title, value, subtitle }) {
  return (
    React.createElement('div', { className: 'card' },
      React.createElement('div', { className: 'title' }, title),
      React.createElement('div', { style: { fontSize: 28, fontWeight: 700, color: '#22d3ee' } }, value),
      React.createElement('div', { className: 'muted' }, subtitle)
    )
  );
}

function LineChart({ labels, data, label, color='#22d3ee' }) {
  const ref = useRef(null);
  useEffect(() => {
    const ctx = ref.current.getContext('2d');
    const chart = new window.Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label,
          data,
          borderColor: color,
          tension: 0.3,
        }]
      },
      options: { responsive: true, plugins: { legend: { display: false } } }
    });
    return () => chart.destroy();
  }, [labels.join(','), data.join(',')]);
  return React.createElement('canvas', { height: 120, ref });
}

function AdminPanel() {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [newUser, setNewUser] = useState({ email: '', password: '', name: '', is_admin: false });

    const loadUsers = async () => {
        setLoading(true);
        try {
            const data = await fetchJSON('/api/admin/users');
            setUsers(data);
            setError('');
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadUsers();
    }, []);

    const handleDelete = async (id) => {
        if (!confirm('¿Estás seguro de eliminar este usuario?')) return;
        try {
            await fetchJSON(`/api/admin/users/${id}`, { method: 'DELETE' });
            loadUsers();
        } catch (e) {
            alert('Error: ' + e.message);
        }
    };

    const handleCreate = async () => {
        if (!newUser.email || !newUser.password) {
            alert('Email y contraseña obligatorios');
            return;
        }
        try {
            await fetchJSON('/api/admin/users', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newUser)
            });
            setNewUser({ email: '', password: '', name: '', is_admin: false });
            loadUsers();
        } catch (e) {
            alert('Error creando usuario: ' + e.message);
        }
    };

    return React.createElement('div', { className: 'wrap' },
        React.createElement('div', { className: 'header' },
             React.createElement('div', { className: 'title' }, 'Panel de Administración'),
        ),
        error && React.createElement('div', { style: { color: 'red', marginBottom: 10 } }, error),
        
        React.createElement('div', { className: 'card', style: { marginBottom: 20 } },
            React.createElement('div', { className: 'title' }, 'Crear Nuevo Usuario'),
            React.createElement('div', { style: { display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' } },
                React.createElement('input', { 
                    placeholder: 'Email', 
                    value: newUser.email, 
                    onChange: e => setNewUser({...newUser, email: e.target.value}) 
                }),
                React.createElement('input', { 
                    placeholder: 'Nombre', 
                    value: newUser.name, 
                    onChange: e => setNewUser({...newUser, name: e.target.value}) 
                }),
                React.createElement('input', { 
                    placeholder: 'Contraseña (min 6)', 
                    type: 'password',
                    value: newUser.password, 
                    onChange: e => setNewUser({...newUser, password: e.target.value}) 
                }),
                React.createElement('label', { style: { display: 'flex', alignItems: 'center', gap: 5, color: '#fff' } },
                    React.createElement('input', { 
                        type: 'checkbox', 
                        checked: newUser.is_admin, 
                        onChange: e => setNewUser({...newUser, is_admin: e.target.checked}) 
                    }),
                    'Es Admin'
                ),
                React.createElement('button', { onClick: handleCreate }, 'Crear Usuario')
            )
        ),

        React.createElement('div', { className: 'card' },
            React.createElement('div', { className: 'title' }, 'Usuarios Registrados'),
            loading ? 'Cargando...' : React.createElement('table', { style: { width: '100%', borderCollapse: 'collapse', color: '#fff' } },
                React.createElement('thead', null,
                    React.createElement('tr', { style: { textAlign: 'left', borderBottom: '1px solid #444' } },
                        React.createElement('th', { style: { padding: 8 } }, 'ID'),
                        React.createElement('th', { style: { padding: 8 } }, 'Email'),
                        React.createElement('th', { style: { padding: 8 } }, 'Nombre'),
                        React.createElement('th', { style: { padding: 8 } }, 'Rol'),
                        React.createElement('th', { style: { padding: 8 } }, 'Acciones')
                    )
                ),
                React.createElement('tbody', null,
                    users.map(u => 
                        React.createElement('tr', { key: u.id, style: { borderBottom: '1px solid #222' } },
                            React.createElement('td', { style: { padding: 8 } }, u.id),
                            React.createElement('td', { style: { padding: 8 } }, u.email),
                            React.createElement('td', { style: { padding: 8 } }, u.name || '-'),
                            React.createElement('td', { style: { padding: 8 } }, u.is_admin ? 'Admin' : 'User'),
                            React.createElement('td', { style: { padding: 8 } },
                                React.createElement('button', { 
                                    style: { backgroundColor: '#ef4444', fontSize: '0.8rem', padding: '4px 8px' },
                                    onClick: () => handleDelete(u.id)
                                }, 'Eliminar')
                            )
                        )
                    )
                )
            )
        )
    );
}

function App() {
  const { demo } = useQuery();
  const apiBase = getApiBase();
  const [apiBaseInput, setApiBaseInput] = useState(apiBase);
  const [authed, setAuthed] = useState(!!getDashboardToken());
  const [userInfo, setUserInfo] = useState(getUserInfo());
  const [currentView, setCurrentView] = useState('dashboard'); // 'dashboard' | 'admin'

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  
  const [servers, setServers] = useState([]);
  const [selected, setSelected] = useState('');
  const [history, setHistory] = useState([]);
  const [alerts, setAlerts] = useState({ cpu_total_percent: 90, memory_used_percent: 90, disk_used_percent: 90 });
  const [status, setStatus] = useState({ ok: true, message: '' });
  const [showChooser, setShowChooser] = useState(false);

  const load = async () => {
    const token = getDashboardToken();
    if (!token && !demo) {
      setStatus({ ok: false, message: 'No autenticado' });
      return;
    }
    try {
      const health = await fetchJSON('/api/health');
      setStatus({ ok: !!health.ok, message: health.ok ? '' : 'Backend no disponible' });
      const ss = await fetchJSON('/api/servers');
      setServers(ss);
      const cfg = await fetchJSON('/api/alerts');
      setAlerts(cfg);
    } catch (e) {
      console.error('Error cargando datos', e);
      const msg = e && e.message ? String(e.message) : '';
      if (msg.includes('HTTP 401')) {
        try { localStorage.removeItem('dashboard_token'); localStorage.removeItem('user_info'); } catch {}
        setAuthed(false);
        setStatus({ ok: false, message: 'Sesión expirada o inválida. Inicie sesión.' });
      } else {
        setStatus({ ok: false, message: `Error de conexión${msg ? ': ' + msg : ''}` });
      }
    }
  };

  useEffect(() => {
    if ((authed || demo) && currentView === 'dashboard') {
      load();
      const id = setInterval(load, 40000 * 60); // Ajustado a mucho tiempo o mantener polling corto? 
      // El usuario pidió que el agente envíe cada 40 min, pero el dashboard debería refrescar más seguido si quiere ver algo
      // O tal vez el dashboard también debe ser lento? Dejémoslo en 10s para no saturar si hay pocos datos.
      // OJO: Si el agente envía cada 40 min, polling cada 3s es inútil. Pongámoslo en 30s.
      return () => clearInterval(id);
    }
  }, [authed, currentView]);

  // Polling específico para historial
  useEffect(() => {
    const fetchHistory = async () => {
      if (!selected) return;
      try {
        const hist = await fetchJSON(`/api/metrics/history?server_id=${encodeURIComponent(selected)}&limit=200`);
        setHistory(hist);
      } catch (e) {
        console.error('Error cargando historial', e);
      }
    };
    if (!demo && selected && currentView === 'dashboard') {
        fetchHistory();
        // Si el agente envía cada 40m, no tiene sentido actualizar esto muy seguido.
        const id = setInterval(fetchHistory, 60000); 
        return () => clearInterval(id);
    }
  }, [selected, currentView]);

  const latest = history[history.length - 1] || { memory:{total:0,used:0,free:0,cache:0}, cpu:{total:0,per_core:[]}, disk:{total:0,used:0,free:0,percent:0}, docker:{running_containers:0} };
  const labels = history.map(h => new Date(h.ts).toLocaleTimeString());
  const cpuData = history.map(h => h.cpu.total);
  const memData = history.map(h => Math.round((h.memory.used / h.memory.total) * 100));
  const diskData = history.map(h => Math.round(h.disk.percent));

  const setAlert = async (key, value) => {
    const next = { ...alerts, [key]: Number(value) };
    setAlerts(next);
    if (!demo) {
      try {
        await fetchJSON('/api/alerts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(next) });
      } catch (e) { console.error('Error actualizando alertas', e); }
    }
  };

  const handleLogin = async () => {
    setLoginError('');
    try {
      const res = await fetchJSON('/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) });
      if (res && res.token) {
        try { 
            localStorage.setItem('dashboard_token', res.token);
            localStorage.setItem('user_info', JSON.stringify(res));
        } catch {}
        setUserInfo(res);
        setAuthed(true);
        setStatus({ ok: true, message: '' });
      }
    } catch (e) {
      setLoginError(e.message || 'Credenciales inválidas.');
    }
  };

  const handleLogout = async () => {
    try { await fetchJSON('/api/logout', { method: 'POST' }); } catch {}
    try { localStorage.removeItem('dashboard_token'); localStorage.removeItem('user_info'); } catch {}
    setAuthed(false);
    setServers([]);
    setSelected('');
    setHistory([]);
    setUserInfo(null);
    setCurrentView('dashboard');
  };

  const AlertInput = (key, label) => (
    React.createElement('div', { className: 'card' },
      React.createElement('div', null, label),
      React.createElement('input', { type: 'number', value: alerts[key], onChange: e => setAlert(key, e.target.value) }),
      React.createElement('div', { className: 'muted' }, 'Umbral %')
    )
  );

  // VISTA LOGIN
  if (!authed && !demo) {
    return (
      React.createElement('div', { className: 'wrap', style: { display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' } },
        React.createElement('div', { className: 'card', style: { maxWidth: 420, width: '100%' } },
          React.createElement('div', { className: 'title' }, 'Acceso al Dashboard'),
          React.createElement('div', { className: 'muted', style: { marginBottom: 12 } }, 'Ingrese sus credenciales'),
          React.createElement('div', { style: { display: 'grid', gap: 12 } },
            React.createElement('input', { type: 'text', placeholder: 'Correo', value: email, onChange: e => setEmail(e.target.value) }),
            React.createElement('input', { type: 'password', placeholder: 'Contraseña', value: password, onChange: e => setPassword(e.target.value) }),
            loginError && React.createElement('div', { style: { color: '#ef4444' } }, loginError),
            React.createElement('button', { onClick: handleLogin }, 'Entrar')
          )
        )
      )
    );
  }

  // HEADER COMUN
  const renderHeader = () => (
      React.createElement('div', { className: 'header' },
        React.createElement('div', { className: 'title' }, 'Dashboard de Monitoreo'),
        React.createElement('span', { className: 'pill' }, demo ? 'DEMO' : 'LIVE'),
        !demo && React.createElement('div', { style: { display: 'flex', gap: 10, marginLeft: 20 } },
            React.createElement('button', { 
                onClick: () => setCurrentView('dashboard'),
                style: { opacity: currentView === 'dashboard' ? 1 : 0.5 }
            }, 'Dashboard'),
            userInfo && userInfo.is_admin && React.createElement('button', { 
                onClick: () => setCurrentView('admin'),
                style: { opacity: currentView === 'admin' ? 1 : 0.5 }
            }, 'Admin Usuarios')
        ),
        !demo && React.createElement('div', { style: { marginLeft: 'auto', display: 'flex', gap: 10, alignItems: 'center' } },
          React.createElement('span', { className: 'muted' }, userInfo ? userInfo.name : ''),
          React.createElement('button', { onClick: handleLogout }, 'Salir')
        )
      )
  );

  // VISTA ADMIN
  if (currentView === 'admin') {
      return React.createElement('div', null,
        renderHeader(),
        React.createElement(AdminPanel)
      );
  }

  // VISTA DASHBOARD
  return (
    React.createElement('div', { className: 'wrap' },
      renderHeader(),
      !status.ok && React.createElement('div', { className: 'card', style: { border: '1px solid #ef4444', marginBottom: 12 } },
        React.createElement('div', { style: { color: '#ef4444' } }, status.message || 'Sin datos en vivo'),
        React.createElement('div', { className: 'muted' }, 'Verifique token, TLS y disponibilidad del backend')
      ),
      React.createElement('div', { className: 'card', style: { marginBottom: 16, display: 'flex', alignItems: 'center', gap: 12 } },
        React.createElement('label', null, 'Servidor: '),
        React.createElement('select', { value: selected, onChange: e => setSelected(e.target.value) },
          servers.map(s => React.createElement('option', { key: s.server_id, value: s.server_id }, s.server_id))
        ),
        React.createElement('button', { onClick: () => setShowChooser(v => !v) }, 'Cambiar servidor'),
        React.createElement('span', { className: 'muted' }, 'Intervalo: 40m')
      ),
      showChooser && React.createElement('div', { className: 'card', style: { marginBottom: 16 } },
        React.createElement('div', { className: 'title' }, 'Servidores conectados'),
        servers.length === 0
          ? React.createElement('div', { className: 'muted' }, 'Sin servidores registrados')
          : React.createElement('div', { style: { display: 'flex', flexWrap: 'wrap', gap: 8 } },
              servers.map(s => React.createElement('button', {
                key: s.server_id,
                onClick: () => { setSelected(s.server_id); setShowChooser(false); },
                style: { background: s.server_id === selected ? '#22d3ee' : undefined }
              }, s.server_id))
            ),
        React.createElement('div', { style: { marginTop: 8 } },
          React.createElement('button', { onClick: () => setShowChooser(false) }, 'Cerrar')
        )
      ),
      React.createElement('div', { className: 'grid' },
        React.createElement(MetricCard, { title: 'CPU Total', value: `${latest.cpu.total || 0}%`, subtitle: 'Uso total' }),
        React.createElement(MetricCard, { title: 'Memoria Usada', value: `${Math.round((latest.memory.used / latest.memory.total) * 100) || 0}%`, subtitle: `${Math.round(latest.memory.used)} / ${Math.round(latest.memory.total)} MB` }),
        React.createElement(MetricCard, { title: 'Disco Usado', value: `${Math.round(latest.disk.percent) || 0}%`, subtitle: `${Math.round(latest.disk.used)} / ${Math.round(latest.disk.total)} GB` }),
      ),
      React.createElement('div', { className: 'row', style: { marginTop: 16 } },
        React.createElement('div', { className: 'card' },
          React.createElement('div', { className: 'title' }, 'CPU (%)'),
          React.createElement(LineChart, { labels, data: cpuData, label: 'CPU' })
        ),
        React.createElement('div', { className: 'card' },
          React.createElement('div', { className: 'title' }, 'Contenedores Docker'),
          React.createElement('div', { style: { fontSize: 28, fontWeight: 700, color: '#22d3ee' } }, latest.docker.running_containers || 0),
          React.createElement('div', { className: 'muted' }, 'Activos')
        )
      ),
      React.createElement('div', { className: 'row', style: { marginTop: 16 } },
        React.createElement('div', { className: 'card' },
          React.createElement('div', { className: 'title' }, 'Memoria (%)'),
          React.createElement(LineChart, { labels, data: memData, label: 'Mem' })
        ),
        React.createElement('div', { className: 'card' },
          React.createElement('div', { className: 'title' }, 'Disco (%)'),
          React.createElement(LineChart, { labels, data: diskData, label: 'Disk' })
        )
      ),
      React.createElement('div', { className: 'grid', style: { marginTop: 16 } },
        AlertInput('cpu_total_percent', 'Alerta CPU total'),
        AlertInput('memory_used_percent', 'Alerta memoria usada'),
        AlertInput('disk_used_percent', 'Alerta disco usado')
      )
    )
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(React.createElement(App));
