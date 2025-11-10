const { useEffect, useState, useRef } = React;

// Token del dashboard solo desde localStorage (emitido por login)
function getDashboardToken() {
  const token = localStorage.getItem('dashboard_token') || '';
  return token;
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
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    if (!ct.includes('application/json')) throw new Error('Respuesta no JSON');
    return await r.json();
  });
}

function rand(n) { return Math.round(Math.random() * n); }

function DemoData() {
  const server_id = 'demo-server';
  const now = new Date();
  const points = Array.from({ length: 50 }, (_, i) => {
    const cpu = Math.min(100, 20 + rand(40));
    const memUsed = Math.min(100, 30 + rand(50));
    const disk = Math.min(100, 40 + rand(40));
    return {
      server_id,
      ts: new Date(now.getTime() - (50 - i) * 1000).toISOString(),
      memory: { total: 16000, used: (memUsed/100)*16000, free: (1-memUsed/100)*16000, cache: 1200 },
      cpu: { total: cpu, per_core: [cpu - 5, cpu + 3, cpu - 2, cpu + 1] },
      disk: { total: 512, used: (disk/100)*512, free: (1-disk/100)*512, percent: disk },
      docker: { running_containers: rand(5), containers: [] }
    };
  });
  return { servers: [{ server_id }], history: points };
}

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

function App() {
  const { demo } = useQuery();
  const apiBase = getApiBase();
  const [apiBaseInput, setApiBaseInput] = useState(apiBase);
  const [authed, setAuthed] = useState(!!getDashboardToken());
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
    if (demo) {
      const d = DemoData();
      setServers(d.servers);
      setSelected(d.servers[0].server_id);
      setHistory(d.history);
      return;
    }
    const token = getDashboardToken();
    if (!token) {
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
        try { localStorage.removeItem('dashboard_token'); } catch {}
        setAuthed(false);
        setStatus({ ok: false, message: 'Sesión expirada o inválida. Inicie sesión.' });
      } else {
        setStatus({ ok: false, message: `Error de conexión${msg ? ': ' + msg : ''}` });
      }
    }
  };

  useEffect(() => {
    if (authed || demo) {
      load();
      const id = setInterval(load, 3000);
      return () => clearInterval(id);
    }
  }, [authed]);

  useEffect(() => {
    // Cuando cambia el servidor seleccionado, cargar su historial sin afectar otros estados
    const fetchHistory = async () => {
      if (!selected) return;
      try {
        const hist = await fetchJSON(`/api/metrics/history?server_id=${encodeURIComponent(selected)}&limit=200`);
        setHistory(hist);
      } catch (e) {
        console.error('Error cargando historial', e);
        const msg = e && e.message ? String(e.message) : '';
        if (msg.includes('HTTP 401')) {
          try { localStorage.removeItem('dashboard_token'); } catch {}
          setAuthed(false);
          setStatus({ ok: false, message: 'Sesión expirada o inválida. Inicie sesión.' });
        }
      }
    };
    if (!demo) fetchHistory();
  }, [selected]);

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
    } else {
      localStorage.setItem('alerts', JSON.stringify(next));
    }
  };

  const handleLogin = async () => {
    setLoginError('');
    try {
      const res = await fetchJSON('/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) });
      if (res && res.token) {
        try { localStorage.setItem('dashboard_token', res.token); } catch {}
        setAuthed(true);
        setStatus({ ok: true, message: '' });
      }
    } catch (e) {
      setLoginError('Credenciales inválidas.');
      console.error('Login error', e);
    }
  };

  const handleLogout = async () => {
    try { await fetchJSON('/api/logout', { method: 'POST' }); } catch {}
    try { localStorage.removeItem('dashboard_token'); } catch {}
    setAuthed(false);
    setServers([]);
    setSelected('');
    setHistory([]);
  };

  const AlertInput = (key, label) => (
    React.createElement('div', { className: 'card' },
      React.createElement('div', null, label),
      React.createElement('input', { type: 'number', value: alerts[key], onChange: e => setAlert(key, e.target.value) }),
      React.createElement('div', { className: 'muted' }, 'Umbral %')
    )
  );

  if (!authed && !demo) {
    return (
      React.createElement('div', { className: 'wrap', style: { display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' } },
        React.createElement('div', { className: 'card', style: { maxWidth: 420, width: '100%' } },
          React.createElement('div', { className: 'title' }, 'Acceso al Dashboard'),
          React.createElement('div', { className: 'muted', style: { marginBottom: 12 } }, 'Ingrese sus credenciales'),
          React.createElement('div', { style: { display: 'grid', gap: 12 } },
            React.createElement('input', { type: 'text', placeholder: 'Correo, usuario o nombre', value: email, onChange: e => setEmail(e.target.value) }),
            React.createElement('input', { type: 'password', placeholder: 'Contraseña', value: password, onChange: e => setPassword(e.target.value) }),
            loginError && React.createElement('div', { style: { color: '#ef4444' } }, loginError),
            React.createElement('button', { onClick: handleLogin }, 'Entrar')
          )
        )
      )
    );
  }

  return (
    React.createElement('div', { className: 'wrap' },
      React.createElement('div', { className: 'header' },
        React.createElement('div', { className: 'title' }, 'Dashboard de Monitoreo'),
        React.createElement('span', { className: 'pill' }, demo ? 'DEMO' : 'LIVE'),
        !demo && React.createElement('span', { className: 'muted', style: { marginLeft: 8 } }, `API: ${apiBase}`),
        !demo && React.createElement('div', { style: { display: 'inline-flex', gap: 8, marginLeft: 12, alignItems: 'center' } },
          React.createElement('input', {
            value: apiBaseInput,
            onChange: (e) => setApiBaseInput(e.target.value),
            placeholder: 'http://localhost:8001',
            style: { padding: '6px 8px', width: 260 }
          }),
          React.createElement('button', {
            onClick: () => {
              const v = (apiBaseInput || '').trim();
              const normalized = v.endsWith('/') ? v.slice(0, -1) : v;
              try { localStorage.setItem('api_base', normalized); } catch {}
              setStatus((s) => ({ ...s, ok: true, message: `API configurado: ${normalized}` }));
              // Forzar recarga de datos inmediatamente
              load();
            }
          }, 'Guardar API')
        ),
        !demo && React.createElement('div', { style: { marginLeft: 'auto' } },
          React.createElement('button', { onClick: handleLogout }, 'Salir')
        )
      ),
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
        React.createElement('span', { className: 'muted' }, 'Actualiza cada 3s')
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