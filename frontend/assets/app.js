const { useEffect, useState, useRef } = React;

// v11 - Force version bump
console.log("ServPulse Dashboard v2.1 Loaded");

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
  let base = override || stored || window.location.origin;
  if (base === 'null' || base.startsWith('file:')) {
      base = 'http://localhost:8000';
  }
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
        let json;
        try {
            json = JSON.parse(txt);
        } catch (e) {
             throw new Error(txt || `HTTP ${r.status}`);
        }
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

function ServerAssignmentModal({ user, onClose }) {
    const [allServers, setAllServers] = useState([]);
    // State: server_id -> { assigned: bool, alerts: bool }
    const [assignments, setAssignments] = useState({});
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const load = async () => {
            try {
                const [serversData, assignedData] = await Promise.all([
                    fetchJSON('/api/servers'), // Asume que admin ve todos
                    fetchJSON(`/api/admin/users/${user.id}/servers`)
                ]);
                setAllServers(serversData);
                
                // Initialize map
                const map = {};
                serversData.forEach(s => {
                    map[s.server_id] = { assigned: false, alerts: true };
                });
                
                // Apply existing assignments
                // API returns [{server_id, receive_alerts}, ...]
                assignedData.forEach(a => {
                    if (map[a.server_id]) {
                        map[a.server_id].assigned = true;
                        map[a.server_id].alerts = a.receive_alerts;
                    }
                });
                
                setAssignments(map);
            } catch (e) {
                alert('Error cargando servidores: ' + e.message);
                onClose();
            } finally {
                setLoading(false);
            }
        };
        load();
    }, [user.id]);

    const toggleAssigned = (sid) => {
        setAssignments(prev => ({
            ...prev,
            [sid]: { ...prev[sid], assigned: !prev[sid].assigned }
        }));
    };
    
    const toggleAlerts = (sid) => {
        setAssignments(prev => ({
            ...prev,
            [sid]: { ...prev[sid], alerts: !prev[sid].alerts }
        }));
    };

    const handleSave = async () => {
        try {
            const payload = Object.entries(assignments)
                .filter(([_, val]) => val.assigned)
                .map(([sid, val]) => ({
                    server_id: sid,
                    receive_alerts: val.alerts
                }));

            await fetchJSON(`/api/admin/users/${user.id}/servers`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ assignments: payload })
            });
            alert('Asignación guardada');
            onClose();
        } catch (e) {
            alert('Error guardando: ' + e.message);
        }
    };

    return React.createElement('div', { 
        style: { 
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, 
            background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 
        } 
    },
        React.createElement('div', { className: 'card', style: { width: 600, maxHeight: '80vh', overflowY: 'auto' } },
            React.createElement('div', { className: 'title' }, `Asignar Servidores a ${user.name || user.email}`),
            React.createElement('div', { className: 'muted', style: { marginBottom: 15 } }, 'Selecciona los servidores que el usuario puede ver. Marca la casilla "Alertas" para que reciba notificaciones de ese servidor.'),
            
            loading ? 'Cargando...' : React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 8, margin: '20px 0' } },
                allServers.length === 0 ? 'No hay servidores registrados' :
                allServers.map(s => {
                    const st = assignments[s.server_id] || { assigned: false, alerts: true };
                    return React.createElement('div', { key: s.server_id, style: { display: 'flex', alignItems: 'center', gap: 10, padding: 8, border: '1px solid #333', borderRadius: 4, background: st.assigned ? '#1e293b' : 'transparent' } },
                        // Checkbox Assigned
                        React.createElement('input', { 
                            type: 'checkbox', 
                            checked: st.assigned, 
                            onChange: () => toggleAssigned(s.server_id),
                            style: { cursor: 'pointer', transform: 'scale(1.2)' }
                        }),
                        // Server ID
                        React.createElement('span', { style: { flex: 1, fontWeight: 500, color: st.assigned ? '#fff' : '#94a3b8' } }, s.server_id),
                        
                        // Checkbox Alerts (Only if assigned)
                        st.assigned && React.createElement('label', { style: { display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.9rem', cursor: 'pointer', color: st.alerts ? '#38bdf8' : '#64748b' } },
                            React.createElement('input', {
                                type: 'checkbox',
                                checked: st.alerts,
                                onChange: () => toggleAlerts(s.server_id)
                            }),
                            'Alertas'
                        )
                    );
                })
            ),
            React.createElement('div', { style: { display: 'flex', gap: 10, justifyContent: 'flex-end' } },
                React.createElement('button', { onClick: onClose, style: { background: '#444' } }, 'Cancelar'),
                React.createElement('button', { onClick: handleSave }, 'Guardar')
            )
        )
    );
}

function GroupSelectionModal({ groups, onSelect, onClose }) {
    const [newGroup, setNewGroup] = useState('');

    return React.createElement('div', { 
        style: { 
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, 
            background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000 
        },
        onClick: (e) => { if(e.target === e.currentTarget) onClose(); }
    },
        React.createElement('div', { className: 'card', style: { width: 400, maxWidth: '90%' } },
            React.createElement('div', { className: 'title' }, 'Seleccionar Grupo'),
            React.createElement('div', { className: 'muted', style: { marginBottom: 15 } }, 'Elige un grupo existente o crea uno nuevo.'),
            
            // Grid de grupos existentes
            React.createElement('div', { style: { display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 20, maxHeight: '40vh', overflowY: 'auto' } },
                groups.length === 0 ? React.createElement('div', { className: 'muted' }, 'No hay grupos creados aún.') :
                groups.map(g => 
                    React.createElement('button', {
                        key: g,
                        onClick: () => onSelect(g),
                        style: {
                            background: '#1e293b',
                            border: '1px solid #475569',
                            color: '#e2e8f0',
                            padding: '8px 12px',
                            borderRadius: 20,
                            cursor: 'pointer',
                            transition: 'all 0.2s',
                            fontSize: '0.9rem'
                        },
                        onMouseOver: e => e.currentTarget.style.borderColor = '#38bdf8',
                        onMouseOut: e => e.currentTarget.style.borderColor = '#475569'
                    }, g)
                )
            ),

            React.createElement('div', { style: { borderTop: '1px solid #334155', paddingTop: 15 } },
                React.createElement('div', { style: { fontSize: '0.9rem', marginBottom: 8, color: '#94a3b8' } }, 'Crear Nuevo Grupo'),
                React.createElement('div', { style: { display: 'flex', gap: 8 } },
                    React.createElement('input', {
                        placeholder: 'Nombre del nuevo grupo...',
                        value: newGroup,
                        onChange: e => setNewGroup(e.target.value),
                        onKeyDown: e => {
                            if (e.key === 'Enter' && newGroup.trim()) onSelect(newGroup.trim());
                        },
                        style: { 
                            flex: 1,
                            background: '#0f172a',
                            border: '1px solid #475569',
                            borderRadius: 4,
                            padding: '8px 12px',
                            color: '#e2e8f0',
                            outline: 'none'
                        }
                    }),
                    React.createElement('button', {
                        onClick: () => { if(newGroup.trim()) onSelect(newGroup.trim()); },
                        disabled: !newGroup.trim(),
                        style: { 
                            background: newGroup.trim() ? '#3b82f6' : '#94a3b8',
                            color: 'white',
                            border: 'none',
                            borderRadius: 4,
                            padding: '0 16px',
                            cursor: newGroup.trim() ? 'pointer' : 'not-allowed',
                            fontWeight: 500
                        }
                    }, 'Crear')
                )
            ),
            
            React.createElement('button', { 
                onClick: onClose, 
                style: { marginTop: 15, width: '100%', background: 'transparent', border: '1px solid #475569', color: '#94a3b8' } 
            }, 'Cancelar')
        )
    );
}

function ServerGroupRow({ server, onUpdate, selected, onToggle, onOpenPicker, onToggleDataMonitoring }) {
    const [group, setGroup] = useState(server.group_name || '');
    const [saving, setSaving] = useState(false);
    
    // Update local state when server prop changes (e.g. bulk update)
    useEffect(() => {
        setGroup(server.group_name || '');
    }, [server.group_name]);

    const hasChanged = group !== (server.group_name || '');

    const handleSave = async () => {
        setSaving(true);
        await onUpdate(server.server_id, group);
        setSaving(false);
    };

    return React.createElement('tr', { style: { borderBottom: '1px solid #334155', transition: 'background 0.2s', background: selected ? '#1e3a8a' : 'transparent' } },
        React.createElement('td', { style: { padding: '12px 16px', width: 40 } },
            React.createElement('input', { 
                type: 'checkbox', 
                checked: selected, 
                onChange: () => onToggle(server.server_id),
                style: { transform: 'scale(1.2)', cursor: 'pointer' }
            })
        ),
        React.createElement('td', { style: { padding: '12px 16px', color: '#cbd5e1' } }, 
            React.createElement('div', { style: { fontWeight: 500 } }, server.server_id)
        ),
        React.createElement('td', { style: { padding: '12px 16px' } },
            React.createElement('div', { style: { display: 'flex', gap: 6 } },
                React.createElement('input', { 
                    value: group, 
                    onChange: e => setGroup(e.target.value),
                    placeholder: 'Sin grupo asignado',
                    list: 'groups-datalist',
                    style: { 
                        background: '#0f172a', 
                        border: '1px solid #475569', 
                        borderRadius: '4px',
                        color: '#fff', 
                        padding: '6px 10px', 
                        width: '100%',
                        outline: 'none',
                        flex: 1
                    }
                }),
                React.createElement('button', {
                    onClick: () => onOpenPicker(server),
                    title: 'Seleccionar Grupo',
                    style: {
                        background: '#334155',
                        border: '1px solid #475569',
                        borderRadius: 4,
                        cursor: 'pointer',
                        padding: '0 10px'
                    }
                }, '📂')
            )
        ),
        React.createElement('td', { style: { padding: '12px 16px', textAlign: 'center' } },
            React.createElement('input', {
                type: 'checkbox',
                checked: !!server.data_monitoring_enabled,
                onChange: () => onToggleDataMonitoring(server.server_id, !server.data_monitoring_enabled),
                style: { transform: 'scale(1.2)', cursor: 'pointer' }
            })
        ),
        React.createElement('td', { style: { padding: '12px 16px' } },
            hasChanged && React.createElement('button', { 
                onClick: handleSave,
                disabled: saving,
                style: { 
                    fontSize: '0.8rem', 
                    padding: '6px 12px', 
                    backgroundColor: saving ? '#94a3b8' : '#22c55e', 
                    color: '#fff', 
                    border: 'none', 
                    borderRadius: '4px',
                    cursor: saving ? 'wait' : 'pointer',
                    fontWeight: 500,
                    boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
                } 
            }, saving ? 'Guardando...' : 'Guardar')
        )
    );
}

function ServerGroupManager() {
    const [servers, setServers] = useState([]);
    const [loading, setLoading] = useState(false);
    const [selectedIds, setSelectedIds] = useState([]);
    const [bulkGroup, setBulkGroup] = useState('');
    const [bulkSaving, setBulkSaving] = useState(false);
    const [showGroupModal, setShowGroupModal] = useState(false);
    const [targetServerForModal, setTargetServerForModal] = useState(null);
    
    // Grupos guardados localmente para mejorar la UX (permitir "crear" sin asignar inmediatamente)
    const [savedGroups, setSavedGroups] = useState(() => {
        try { return JSON.parse(localStorage.getItem('saved_groups') || '[]'); } 
        catch { return []; }
    });

    const addSavedGroup = (g) => {
        if (g && !savedGroups.includes(g)) {
            const newGroups = [...savedGroups, g].sort();
            setSavedGroups(newGroups);
            localStorage.setItem('saved_groups', JSON.stringify(newGroups));
        }
    };

    const load = async () => {
        setLoading(true);
        try {
            const data = await fetchJSON('/api/servers');
            setServers(data);
        } catch (e) { console.error(e); }
        finally { setLoading(false); }
    };

    useEffect(() => { load(); }, []);

    const updateGroup = async (sid, groupName) => {
        try {
            await fetchJSON(`/api/admin/servers/${sid}/group`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ group_name: groupName || null })
            });
            // Update local state to remove "Guardar" button until changed again
            setServers(prev => prev.map(s => s.server_id === sid ? { ...s, group_name: groupName } : s));
        } catch(e) { alert(e.message); }
    };

    const toggleId = (id) => {
        setSelectedIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
    };

    const toggleAll = () => {
        if (selectedIds.length === servers.length) setSelectedIds([]);
        else setSelectedIds(servers.map(s => s.server_id));
    };

    const handleBulkUpdate = async () => {
        if (!bulkGroup) return alert('Escribe o selecciona un nombre de grupo para aplicar');
        if (selectedIds.length === 0) return alert('Selecciona al menos un servidor de la lista');
        
        setBulkSaving(true);
        try {
            await Promise.all(selectedIds.map(id => 
                fetchJSON(`/api/admin/servers/${id}/group`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ group_name: bulkGroup })
                })
            ));
            
            setServers(servers.map(s => selectedIds.includes(s.server_id) ? { ...s, group_name: bulkGroup } : s));
            setSelectedIds([]);
            setBulkGroup('');
            alert(`Grupo "${bulkGroup}" asignado a ${selectedIds.length} servidores.`);
        } catch (e) { 
            alert('Error en actualización masiva: ' + e.message); 
        } finally {
            setBulkSaving(false);
        }
    };

    const openPickerForServer = (server) => {
        setTargetServerForModal(server);
        setShowGroupModal(true);
    };

    const toggleDataMonitoring = async (sid, enabled) => {
        try {
            await fetchJSON(`/api/admin/servers/${sid}/data-monitoring`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled })
            });
            setServers(prev => prev.map(s => s.server_id === sid ? { ...s, data_monitoring_enabled: enabled } : s));
        } catch (e) {
            alert(e.message);
        }
    };

    const uniqueGroups = [...new Set([
        ...servers.map(s => s.group_name).filter(g => g),
        ...savedGroups
    ])].sort();

    return React.createElement('div', { className: 'card', style: { marginBottom: 20, border: '1px solid #334155', background: '#1e293b' } },
        React.createElement('div', { className: 'title', style: { borderBottom: '1px solid #334155', paddingBottom: 10, marginBottom: 10 } }, 'Gestión de Grupos y Dashboard Postman'),
        
        // Modal de selección de grupos
        showGroupModal && React.createElement(GroupSelectionModal, {
            groups: uniqueGroups,
            onClose: () => { setShowGroupModal(false); setTargetServerForModal(null); },
            onSelect: (g) => { 
                addSavedGroup(g); // Guardar localmente para que aparezca en el futuro
                if (targetServerForModal) {
                    updateGroup(targetServerForModal.server_id, g);
                } else {
                    setBulkGroup(g); 
                }
                setShowGroupModal(false);
                setTargetServerForModal(null);
            }
        }),

        // Datalist global para el componente
        React.createElement('datalist', { id: 'groups-datalist' },
            uniqueGroups.map(g => React.createElement('option', { key: g, value: g }))
        ),

        // BARRA DE ACCIONES MASIVAS
        React.createElement('div', { style: { background: '#0f172a', padding: 15, borderRadius: 6, marginBottom: 15, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' } },
            React.createElement('div', { style: { fontWeight: 600, color: '#38bdf8' } }, 'Acción Masiva:'),
            React.createElement('div', { style: { display: 'flex', gap: 5, flex: 1, minWidth: 250 } },
                React.createElement('input', {
                    placeholder: 'Grupo a Asignar',
                    value: bulkGroup,
                    onChange: e => setBulkGroup(e.target.value),
                    list: 'groups-datalist',
                    style: { padding: '8px 12px', borderRadius: '4px 0 0 4px', border: '1px solid #475569', background: '#1e293b', color: '#fff', flex: 1 }
                }),
                React.createElement('button', {
                    onClick: () => { setTargetServerForModal(null); setShowGroupModal(true); },
                    style: { padding: '0 12px', background: '#334155', border: '1px solid #475569', borderLeft: 'none', borderRadius: '0 4px 4px 0', cursor: 'pointer', color: '#cbd5e1' },
                    title: 'Ver lista de grupos'
                }, '📂')
            ),
            React.createElement('button', {
                onClick: handleBulkUpdate,
                disabled: bulkSaving || selectedIds.length === 0,
                style: { 
                    padding: '8px 16px', 
                    background: bulkSaving ? '#94a3b8' : '#3b82f6', 
                    color: 'white', 
                    border: 'none', 
                    borderRadius: 4,
                    cursor: bulkSaving ? 'wait' : 'pointer'
                }
            }, bulkSaving ? 'Aplicando...' : `Asignar a ${selectedIds.length} seleccionados`)
        ),

        loading ? React.createElement('div', { style: { padding: 20, textAlign: 'center', color: '#94a3b8' } }, 'Cargando servidores...') : 
        React.createElement('div', { style: { overflowX: 'auto' } },
            React.createElement('table', { style: { width: '100%', borderCollapse: 'collapse', textAlign: 'left' } },
                React.createElement('thead', null,
                    React.createElement('tr', { style: { borderBottom: '2px solid #334155', color: '#94a3b8', fontSize: '0.85rem', textTransform: 'uppercase' } },
                        React.createElement('th', { style: { padding: '8px 16px', width: 40 } }, 
                            React.createElement('input', { type: 'checkbox', checked: selectedIds.length > 0 && selectedIds.length === servers.length, onChange: toggleAll, style: { transform: 'scale(1.2)', cursor: 'pointer' } })
                        ),
                        React.createElement('th', { style: { padding: '8px 16px' } }, 'Servidor'),
                        React.createElement('th', { style: { padding: '8px 16px' } }, 'Grupo'),
                        React.createElement('th', { style: { padding: '8px 16px' } }, 'Dashboard Postman'),
                        React.createElement('th', { style: { padding: '8px 16px', width: 120 } }, 'Acción')
                    )
                ),
                React.createElement('tbody', null,
                    servers.map(s => React.createElement(ServerGroupRow, { 
                        key: s.server_id, 
                        server: s, 
                        onUpdate: updateGroup,
                        selected: selectedIds.includes(s.server_id),
                        onToggle: toggleId,
                        onOpenPicker: openPickerForServer,
                        onToggleDataMonitoring: toggleDataMonitoring
                    }))
                )
            )
        )
    );
}

function AlertRulesManager() {
    const [rules, setRules] = useState([]);
    const [servers, setServers] = useState([]);
    const [newRule, setNewRule] = useState({ alert_type: 'cpu', server_scope: 'global', target_id: '', emails: '' });
    const [filterGroup, setFilterGroup] = useState('');
    
    // Test Email State
    const [testEmail, setTestEmail] = useState('');
    const [sendingTest, setSendingTest] = useState(false);

    const load = async () => {
        try {
            const [rData, sData] = await Promise.all([
                fetchJSON('/api/admin/alert-rules'),
                fetchJSON('/api/servers')
            ]);
            setRules(rData);
            setServers(sData);
        } catch (e) { console.error(e); }
    };
    
    useEffect(() => { load(); }, []);

    const groups = [...new Set(servers.map(s => s.group_name).filter(g => g))];
    const filteredServers = filterGroup 
        ? servers.filter(s => s.group_name === filterGroup)
        : servers;

    const handleCreate = async () => {
        try {
            const payload = {
                ...newRule,
                emails: newRule.emails.split(',').map(e => e.trim()).filter(e => e)
            };
            if (payload.emails.length === 0) { alert('Añade al menos un email'); return; }
            if (newRule.server_scope !== 'global' && !newRule.target_id) { alert('Especifica ID de servidor o Grupo'); return; }

            await fetchJSON('/api/admin/alert-rules', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            setNewRule({ alert_type: 'cpu', server_scope: 'global', target_id: '', emails: '' });
            setFilterGroup('');
            load();
        } catch(e) { alert(e.message); }
    };

    const handleDelete = async (id) => {
        if(!confirm('Borrar regla?')) return;
        await fetchJSON(`/api/admin/alert-rules/${id}`, { method: 'DELETE' });
        load();
    };

    const handleTestEmail = async () => {
        if (!testEmail || !testEmail.includes('@')) return alert('Ingrese un email válido');
        setSendingTest(true);
        try {
            const res = await fetchJSON('/api/admin/test-email', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: testEmail, name: 'Test User' })
            });
            alert(res.message);
        } catch (e) {
            alert('Error enviando prueba: ' + e.message);
        } finally {
            setSendingTest(false);
        }
    };

    return React.createElement('div', { className: 'card', style: { marginBottom: 20 } },
        React.createElement('div', { className: 'title' }, 'Reglas de Alerta Avanzadas'),
        
        // Test Email Section
        React.createElement('div', { style: { marginBottom: 20, padding: 15, background: '#0f172a', borderRadius: 6, border: '1px solid #334155' } },
            React.createElement('div', { style: { fontWeight: 600, marginBottom: 10, color: '#38bdf8' } }, 'Prueba de Configuración de Correo'),
            React.createElement('div', { style: { display: 'flex', gap: 10 } },
                React.createElement('input', {
                    placeholder: 'Email para prueba',
                    value: testEmail,
                    onChange: e => setTestEmail(e.target.value),
                    style: { flex: 1, padding: '8px 12px', borderRadius: 4, border: '1px solid #475569', background: '#1e293b', color: '#fff' }
                }),
                React.createElement('button', {
                    onClick: handleTestEmail,
                    disabled: sendingTest,
                    style: { padding: '8px 16px', background: sendingTest ? '#94a3b8' : '#22c55e', color: 'white', border: 'none', borderRadius: 4, cursor: sendingTest ? 'wait' : 'pointer' }
                }, sendingTest ? 'Enviando...' : 'Enviar Prueba')
            )
        ),

        React.createElement('div', { style: { display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', marginBottom: 20, padding: 10, background: '#1e293b', borderRadius: 6 } },
            React.createElement('select', { value: newRule.alert_type, onChange: e => setNewRule({...newRule, alert_type: e.target.value}), style: { padding: 8, background: '#333', color: '#fff', border: 'none' } },
                ['cpu', 'memory', 'disk', 'offline'].map(t => React.createElement('option', { key: t, value: t }, t.toUpperCase()))
            ),
            React.createElement('select', { value: newRule.server_scope, onChange: e => setNewRule({...newRule, server_scope: e.target.value}), style: { padding: 8, background: '#333', color: '#fff', border: 'none' } },
                React.createElement('option', { value: 'global' }, 'Global'),
                React.createElement('option', { value: 'server' }, 'Servidor Específico'),
                React.createElement('option', { value: 'group' }, 'Grupo de Servidores')
            ),
            
            // Selector dinámico según alcance
            newRule.server_scope === 'server' ? React.createElement(React.Fragment, null,
                React.createElement('select', { 
                    value: filterGroup, 
                    onChange: e => setFilterGroup(e.target.value),
                    style: { padding: 8, background: '#0f172a', color: '#94a3b8', border: '1px solid #334155' } 
                },
                    React.createElement('option', { value: '' }, 'Filtro Grupo (Todos)'),
                    groups.map(g => React.createElement('option', { key: g, value: g }, g))
                ),
                React.createElement('select', { 
                    value: newRule.target_id, 
                    onChange: e => setNewRule({...newRule, target_id: e.target.value}),
                    style: { padding: 8, background: '#333', color: '#fff', border: 'none' }
                },
                    React.createElement('option', { value: '' }, 'Selecciona Servidor...'),
                    filteredServers.map(s => React.createElement('option', { key: s.server_id, value: s.server_id }, `${s.server_id} ${s.group_name ? `(${s.group_name})` : ''}`))
                )
            ) : newRule.server_scope === 'group' ? React.createElement('select', {
                value: newRule.target_id,
                onChange: e => setNewRule({...newRule, target_id: e.target.value}),
                style: { padding: 8, background: '#333', color: '#fff', border: 'none' }
            },
                React.createElement('option', { value: '' }, 'Selecciona Grupo...'),
                groups.map(g => React.createElement('option', { key: g, value: g }, g))
            ) : null,

            React.createElement('input', { 
                placeholder: 'Emails (separados por coma)',
                value: newRule.emails,
                onChange: e => setNewRule({...newRule, emails: e.target.value})
            }),
            React.createElement('button', { onClick: handleCreate }, 'Crear Regla')
        ),

        React.createElement('table', { style: { width: '100%', borderCollapse: 'collapse' } },
            React.createElement('thead', null,
                React.createElement('tr', { style: { textAlign: 'left', borderBottom: '1px solid #444' } },
                    React.createElement('th', { style: { padding: 8 } }, 'Tipo'),
                    React.createElement('th', { style: { padding: 8 } }, 'Alcance'),
                    React.createElement('th', { style: { padding: 8 } }, 'Objetivo'),
                    React.createElement('th', { style: { padding: 8 } }, 'Destinatarios'),
                    React.createElement('th', { style: { padding: 8 } }, 'Acción')
                )
            ),
            React.createElement('tbody', null,
                rules.map(r => React.createElement('tr', { key: r.id, style: { borderBottom: '1px solid #222' } },
                    React.createElement('td', { style: { padding: 8 } }, r.alert_type.toUpperCase()),
                    React.createElement('td', { style: { padding: 8 } }, r.server_scope),
                    React.createElement('td', { style: { padding: 8 } }, r.target_id || '-'),
                    React.createElement('td', { style: { padding: 8 } }, r.emails.join(', ')),
                    React.createElement('td', { style: { padding: 8 } },
                        React.createElement('button', { onClick: () => handleDelete(r.id), style: { background: '#ef4444', fontSize: '0.8rem', padding: '2px 6px' } }, 'X')
                    )
                ))
            )
        )
    );
}

function ThresholdRow({ server, threshold, onSave }) {
    const [editing, setEditing] = useState(false);
    const [values, setValues] = useState({
        cpu: threshold?.cpu_threshold ?? '',
        memory: threshold?.memory_threshold ?? '',
        disk: threshold?.disk_threshold ?? ''
    });
    const [error, setError] = useState('');

    useEffect(() => {
        setValues({
            cpu: threshold?.cpu_threshold ?? '',
            memory: threshold?.memory_threshold ?? '',
            disk: threshold?.disk_threshold ?? ''
        });
        setError('');
    }, [threshold]);

    const handleSave = () => {
        setError('');
        const v = {};
        
        const validate = (val, name) => {
            if (val === '' || val === null || val === undefined) return undefined;
            const n = parseFloat(val);
            if (isNaN(n) || n < 0.1 || n > 100) {
                return `Error en ${name}: debe ser 0.1 - 100`;
            }
            return n;
        };

        const cpu = validate(values.cpu, 'CPU');
        if (typeof cpu === 'string') { setError(cpu); return; }
        if (cpu !== undefined) v.cpu_threshold = cpu;

        const mem = validate(values.memory, 'Memoria');
        if (typeof mem === 'string') { setError(mem); return; }
        if (mem !== undefined) v.memory_threshold = mem;

        const disk = validate(values.disk, 'Disco');
        if (typeof disk === 'string') { setError(disk); return; }
        if (disk !== undefined) v.disk_threshold = disk;
        
        onSave(server.server_id, v);
        setEditing(false);
    };

    if (editing) {
        return React.createElement('tr', { style: { background: '#1e293b' } },
            React.createElement('td', { style: { padding: 12 } }, 
                React.createElement('div', null, server.server_id),
                error && React.createElement('div', { style: { color: '#ef4444', fontSize: '0.7rem', marginTop: 4 } }, error)
            ),
            React.createElement('td', { style: { padding: 12 } }, 
                React.createElement('input', { type: 'number', step: '0.1', value: values.cpu, onChange: e => setValues({...values, cpu: e.target.value}), placeholder: 'Global', style: { width: 70, padding: 6, background: '#0f172a', color: '#fff', border: error.includes('CPU') ? '1px solid #ef4444' : '1px solid #475569', borderRadius: 4 } })
            ),
            React.createElement('td', { style: { padding: 12 } }, 
                React.createElement('input', { type: 'number', step: '0.1', value: values.memory, onChange: e => setValues({...values, memory: e.target.value}), placeholder: 'Global', style: { width: 70, padding: 6, background: '#0f172a', color: '#fff', border: error.includes('Memoria') ? '1px solid #ef4444' : '1px solid #475569', borderRadius: 4 } })
            ),
            React.createElement('td', { style: { padding: 12 } }, 
                React.createElement('input', { type: 'number', step: '0.1', value: values.disk, onChange: e => setValues({...values, disk: e.target.value}), placeholder: 'Global', style: { width: 70, padding: 6, background: '#0f172a', color: '#fff', border: error.includes('Disco') ? '1px solid #ef4444' : '1px solid #475569', borderRadius: 4 } })
            ),
             React.createElement('td', { style: { padding: 12, display: 'flex', gap: 8 } },
                React.createElement('button', { onClick: handleSave, style: { background: '#22c55e', border: 'none', borderRadius: 4, padding: '6px 10px', cursor: 'pointer', color: '#fff' }, title: 'Guardar' }, '✔'),
                React.createElement('button', { onClick: () => { setEditing(false); setError(''); }, style: { background: '#ef4444', border: 'none', borderRadius: 4, padding: '6px 10px', cursor: 'pointer', color: '#fff' }, title: 'Cancelar' }, '✘')
            )
        );
    }

    return React.createElement('tr', { style: { borderBottom: '1px solid #334155' } },
        React.createElement('td', { style: { padding: 12 } }, server.server_id),
        React.createElement('td', { style: { padding: 12, color: threshold?.cpu_threshold ? '#fff' : '#94a3b8' } }, threshold?.cpu_threshold ? `${threshold.cpu_threshold}%` : 'Global'),
        React.createElement('td', { style: { padding: 12, color: threshold?.memory_threshold ? '#fff' : '#94a3b8' } }, threshold?.memory_threshold ? `${threshold.memory_threshold}%` : 'Global'),
        React.createElement('td', { style: { padding: 12, color: threshold?.disk_threshold ? '#fff' : '#94a3b8' } }, threshold?.disk_threshold ? `${threshold.disk_threshold}%` : 'Global'),
        React.createElement('td', { style: { padding: 12 } },
            React.createElement('button', { onClick: () => setEditing(true), style: { background: '#3b82f6', border: 'none', borderRadius: 4, padding: '6px 12px', cursor: 'pointer', color: '#fff', fontSize: '0.8rem' } }, 'Editar')
        )
    );
}

function ThresholdManager() {
    const [thresholds, setThresholds] = useState([]);
    const [servers, setServers] = useState([]);
    const [loading, setLoading] = useState(false);

    const load = async () => {
        setLoading(true);
        try {
            const [tData, sData] = await Promise.all([
                fetchJSON('/api/umbrales'),
                fetchJSON('/api/servers')
            ]);
            setThresholds(tData);
            setServers(sData);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { load(); }, []);

    const handleUpdate = async (serverId, values) => {
        try {
            await fetchJSON(`/api/umbrales/${serverId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(values)
            });
            load(); 
        } catch (e) {
            alert('Error actualizando: ' + e.message);
        }
    };

    const data = servers.map(s => {
        const t = thresholds.find(x => x.server_id === s.server_id);
        return { server: s, threshold: t };
    });

    const handleExport = async () => {
        try {
            const data = await fetchJSON('/api/umbrales/export');
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'umbrales_config.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (e) {
            alert('Error exportando: ' + e.message);
        }
    };

    const handleImport = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        const reader = new FileReader();
        reader.onload = async (evt) => {
            try {
                const json = JSON.parse(evt.target.result);
                const res = await fetchJSON('/api/umbrales/import', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(json)
                });
                alert(`Importación completada: ${res.count} registros procesados.`);
                load();
            } catch (err) {
                alert('Error importando: ' + err.message);
            }
        };
        reader.readAsText(file);
        e.target.value = ''; // reset file input
    };

    return React.createElement('div', { className: 'card', style: { marginBottom: 20, border: '1px solid #334155', background: '#1e293b' } },
        React.createElement('div', { className: 'title', style: { borderBottom: '1px solid #334155', paddingBottom: 10, marginBottom: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center' } }, 
            'Gestión de Umbrales de Alerta',
            React.createElement('div', { style: { display: 'flex', gap: 10 } },
                React.createElement('button', { onClick: handleExport, style: { fontSize: '0.8rem', padding: '4px 8px', background: '#334155', border: '1px solid #475569', color: '#cbd5e1', borderRadius: 4, cursor: 'pointer' } }, '⬇ Exportar'),
                React.createElement('label', { style: { fontSize: '0.8rem', padding: '4px 8px', background: '#334155', border: '1px solid #475569', color: '#cbd5e1', borderRadius: 4, cursor: 'pointer', display: 'inline-block' } },
                    '⬆ Importar',
                    React.createElement('input', { type: 'file', accept: '.json', style: { display: 'none' }, onChange: handleImport })
                )
            )
        ),
        React.createElement('div', { className: 'muted', style: { marginBottom: 15 } }, 'Define umbrales personalizados por servidor. Valores en blanco usan la configuración global.'),
        
        loading ? React.createElement('div', { style: { padding: 20, textAlign: 'center' } }, 'Cargando...') : 
        React.createElement('div', { style: { overflowX: 'auto' } },
            React.createElement('table', { style: { width: '100%', borderCollapse: 'collapse', textAlign: 'left' } },
                React.createElement('thead', null,
                    React.createElement('tr', { style: { borderBottom: '2px solid #334155', color: '#94a3b8', fontSize: '0.85rem', textTransform: 'uppercase' } },
                        React.createElement('th', { style: { padding: 12 } }, 'Servidor'),
                        React.createElement('th', { style: { padding: 12 } }, 'CPU'),
                        React.createElement('th', { style: { padding: 12 } }, 'Memoria'),
                        React.createElement('th', { style: { padding: 12 } }, 'Disco'),
                        React.createElement('th', { style: { padding: 12 } }, 'Acción')
                    )
                ),
                React.createElement('tbody', null,
                    data.map(item => React.createElement(ThresholdRow, { 
                        key: item.server.server_id, 
                        server: item.server, 
                        threshold: item.threshold, 
                        onSave: handleUpdate 
                    }))
                )
            )
        )
    );
}



function UserEditModal({ user, onClose }) {
    const [values, setValues] = useState({ 
        name: user.name || '', 
        is_admin: user.is_admin, 
        receive_alerts: user.receive_alerts,
        can_view_data_monitoring: user.can_view_data_monitoring,
        password: '' 
    });
    const [loading, setLoading] = useState(false);

    const handleSave = async () => {
        setLoading(true);
        try {
            const payload = {
                name: values.name,
                is_admin: values.is_admin,
                receive_alerts: values.receive_alerts,
                can_view_data_monitoring: values.can_view_data_monitoring
            };
            if (values.password && values.password.length >= 6) {
                payload.password = values.password;
            }

            await fetchJSON(`/api/admin/users/${user.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            onClose();
        } catch (e) {
            alert('Error actualizando usuario: ' + e.message);
        } finally {
            setLoading(false);
        }
    };

    return React.createElement('div', { 
        style: { 
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, 
            background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 
        } 
    },
        React.createElement('div', { className: 'card', style: { width: 400 } },
            React.createElement('div', { className: 'title' }, `Editar Usuario ${user.email}`),
            React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 15 } },
                React.createElement('div', null,
                    React.createElement('label', { style: { display: 'block', marginBottom: 5, color: '#94a3b8' } }, 'Nombre'),
                    React.createElement('input', { 
                        value: values.name, 
                        onChange: e => setValues({...values, name: e.target.value}),
                        style: { width: '100%', padding: 8, background: '#1e293b', border: '1px solid #475569', color: '#fff', borderRadius: 4 }
                    })
                ),
                React.createElement('div', null,
                    React.createElement('label', { style: { display: 'block', marginBottom: 5, color: '#94a3b8' } }, 'Nueva Contraseña (opcional)'),
                    React.createElement('input', { 
                        type: 'password',
                        placeholder: 'Dejar en blanco para no cambiar',
                        value: values.password, 
                        onChange: e => setValues({...values, password: e.target.value}),
                        style: { width: '100%', padding: 8, background: '#1e293b', border: '1px solid #475569', color: '#fff', borderRadius: 4 }
                    })
                ),
                React.createElement('label', { style: { display: 'flex', alignItems: 'center', gap: 5, color: '#fff' } },
                    React.createElement('input', { 
                        type: 'checkbox', 
                        checked: values.is_admin, 
                        onChange: e => setValues({...values, is_admin: e.target.checked}) 
                    }),
                    'Es Admin'
                ),
                React.createElement('label', { style: { display: 'flex', alignItems: 'center', gap: 5, color: '#fff' } },
                    React.createElement('input', { 
                        type: 'checkbox', 
                        checked: values.receive_alerts, 
                        onChange: e => setValues({...values, receive_alerts: e.target.checked}) 
                    }),
                    'Recibir Alertas'
                ),
                React.createElement('label', { style: { display: 'flex', alignItems: 'center', gap: 5, color: '#fff' } },
                    React.createElement('input', { 
                        type: 'checkbox', 
                        checked: values.can_view_data_monitoring, 
                        onChange: e => setValues({...values, can_view_data_monitoring: e.target.checked}) 
                    }),
                    'Ver dashboard Postman'
                ),
                React.createElement('div', { style: { display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 10 } },
                    React.createElement('button', { onClick: onClose, style: { background: '#444' } }, 'Cancelar'),
                    React.createElement('button', { onClick: handleSave, disabled: loading }, loading ? 'Guardando...' : 'Guardar')
                )
            )
        )
    );
}

function AdminPanel() {
    const [activeTab, setActiveTab] = useState('users');
    const [users, setUsers] = useState([]);
    const [recipients, setRecipients] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [newUser, setNewUser] = useState({ email: '', password: '', name: '', is_admin: false, receive_alerts: false, can_view_data_monitoring: false });
    const [newRecipient, setNewRecipient] = useState({ email: '', name: '', recipient_type: 'OTROS' });
    const [assigningUser, setAssigningUser] = useState(null);
    const [editingUser, setEditingUser] = useState(null);

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

    const loadRecipients = async () => {
        try {
            const data = await fetchJSON('/api/admin/recipients');
            setRecipients(data);
        } catch (e) { console.error(e); }
    };

    useEffect(() => {
        loadUsers();
        loadRecipients();
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

    const handleDeleteRecipient = async (id) => {
        if (!confirm('¿Eliminar destinatario?')) return;
        try {
            await fetchJSON(`/api/admin/recipients/${id}`, { method: 'DELETE' });
            loadRecipients();
        } catch (e) {
            alert('Error: ' + e.message);
        }
    };

    const handleCreate = async () => {
        if (!newUser.email || !newUser.password) {
            alert('Email y contraseña obligatorios');
            return;
        }
        if (newUser.password.length < 6) {
            alert('La contraseña debe tener al menos 6 caracteres');
            return;
        }
        try {
            await fetchJSON('/api/admin/users', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newUser)
            });
            setNewUser({ email: '', password: '', name: '', is_admin: false, receive_alerts: false, can_view_data_monitoring: false });
            loadUsers();
        } catch (e) {
            alert('Error creando usuario: ' + e.message);
        }
    };

    const handleCreateRecipient = async () => {
        if (!newRecipient.email) return;
        try {
            await fetchJSON('/api/admin/recipients', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newRecipient)
            });
            setNewRecipient({ email: '', name: '', recipient_type: 'OTROS' });
            loadRecipients();
        } catch (e) {
            alert('Error creando destinatario: ' + e.message);
        }
    };

    const tabs = [
        { id: 'users', label: 'Usuarios' },
        { id: 'recipients', label: 'Destinatarios Extra' },
        { id: 'groups', label: 'Grupos de Servidores' },
        { id: 'rules', label: 'Reglas de Alerta' },
        { id: 'thresholds', label: 'Umbrales de Alerta' }
    ];

    return React.createElement('div', { className: 'wrap' },
        React.createElement('div', { className: 'header', style: { flexDirection: 'column', alignItems: 'flex-start', gap: 10, paddingBottom: 0 } },
             React.createElement('div', { className: 'title' }, 'Panel de Administración'),
             React.createElement('div', { style: { display: 'flex', gap: 2, width: '100%', borderBottom: '1px solid #334155' } },
                tabs.map(tab => 
                    React.createElement('button', {
                        key: tab.id,
                        onClick: () => setActiveTab(tab.id),
                        style: {
                            background: activeTab === tab.id ? '#1e293b' : 'transparent',
                            color: activeTab === tab.id ? '#38bdf8' : '#94a3b8',
                            border: 'none',
                            borderBottom: activeTab === tab.id ? '2px solid #38bdf8' : '2px solid transparent',
                            padding: '10px 20px',
                            cursor: 'pointer',
                            fontWeight: 500,
                            borderRadius: '6px 6px 0 0',
                            transition: 'all 0.2s'
                        }
                    }, tab.label)
                )
             )
        ),
        
        React.createElement('div', { style: { marginTop: 20 } },
            error && React.createElement('div', { style: { color: 'red', marginBottom: 10 } }, error),
            
            // CONTENIDO TABS
            activeTab === 'groups' && React.createElement(ServerGroupManager),
            activeTab === 'rules' && React.createElement(AlertRulesManager),
            activeTab === 'thresholds' && React.createElement(ThresholdManager),

            activeTab === 'users' && React.createElement(React.Fragment, null,
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
                        React.createElement('label', { style: { display: 'flex', alignItems: 'center', gap: 5, color: '#fff' } },
                            React.createElement('input', { 
                                type: 'checkbox', 
                                checked: newUser.receive_alerts, 
                                onChange: e => setNewUser({...newUser, receive_alerts: e.target.checked}) 
                            }),
                            'Recibir Alertas'
                        ),
                        React.createElement('label', { style: { display: 'flex', alignItems: 'center', gap: 5, color: '#fff' } },
                            React.createElement('input', { 
                                type: 'checkbox', 
                                checked: newUser.can_view_data_monitoring, 
                                onChange: e => setNewUser({...newUser, can_view_data_monitoring: e.target.checked}) 
                            }),
                            'Ver dashboard Postman'
                        ),
                        React.createElement('button', { onClick: handleCreate }, 'Crear Usuario')
                    )
                ),
                React.createElement('div', { className: 'card', style: { marginBottom: 40 } },
                    React.createElement('div', { className: 'title' }, 'Usuarios Registrados'),
                    loading ? 'Cargando...' : React.createElement('table', { style: { width: '100%', borderCollapse: 'collapse', color: '#fff' } },
                        React.createElement('thead', null,
                            React.createElement('tr', { style: { textAlign: 'left', borderBottom: '1px solid #444' } },
                                React.createElement('th', { style: { padding: 8 } }, 'ID'),
                                React.createElement('th', { style: { padding: 8 } }, 'Email'),
                                React.createElement('th', { style: { padding: 8 } }, 'Nombre'),
                                React.createElement('th', { style: { padding: 8 } }, 'Rol'),
                                React.createElement('th', { style: { padding: 8 } }, 'Alertas'),
                                React.createElement('th', { style: { padding: 8 } }, 'Dashboard Postman'),
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
                                    React.createElement('td', { style: { padding: 8 } }, u.receive_alerts ? 'Sí' : 'No'),
                                    React.createElement('td', { style: { padding: 8 } }, u.can_view_data_monitoring ? 'Sí' : 'No'),
                                    React.createElement('td', { style: { padding: 8, display: 'flex', gap: 5 } },
                                        React.createElement('button', { 
                                            style: { backgroundColor: '#3b82f6', fontSize: '0.8rem', padding: '4px 8px' },
                                            onClick: () => setAssigningUser(u)
                                        }, 'Servidores'),
                                        React.createElement('button', { 
                                            style: { backgroundColor: '#ef4444', fontSize: '0.8rem', padding: '4px 8px' },
                                            onClick: () => handleDelete(u.id)
                                        }, 'Eliminar')
                                    )
                                )
                            )
                        )
                    )
                ),
                assigningUser && React.createElement(ServerAssignmentModal, { user: assigningUser, onClose: () => setAssigningUser(null) }),
                editingUser && React.createElement(UserEditModal, { user: editingUser, onClose: () => { setEditingUser(null); loadUsers(); } })
            ),

            activeTab === 'recipients' && React.createElement(React.Fragment, null,
                React.createElement('div', { className: 'card', style: { marginBottom: 20 } },
                    React.createElement('div', { className: 'title' }, 'Destinatarios de Alertas Extra'),
                    React.createElement('div', { className: 'muted', style: {marginBottom: 10} }, 'Personas adicionales que recibirán las alertas por correo.'),
                    React.createElement('div', { style: { display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' } },
                        React.createElement('input', { 
                            placeholder: 'Email', 
                            value: newRecipient.email, 
                            onChange: e => setNewRecipient({...newRecipient, email: e.target.value}) 
                        }),
                        React.createElement('input', { 
                            placeholder: 'Nombre (Opcional)', 
                            value: newRecipient.name, 
                            onChange: e => setNewRecipient({...newRecipient, name: e.target.value}) 
                        }),
                        React.createElement('select', {
                            value: newRecipient.recipient_type,
                            onChange: e => setNewRecipient({...newRecipient, recipient_type: e.target.value}),
                            style: { background: '#1e293b', border: '1px solid #475569', color: '#fff', borderRadius: 4, padding: '8px' }
                        },
                            React.createElement('option', { value: 'VS' }, 'Grupo de VS (Vendedores)'),
                            React.createElement('option', { value: 'SV' }, 'Grupo de SV (Supervisores)'),
                            React.createElement('option', { value: 'OTROS' }, 'Otros')
                        ),
                        React.createElement('button', { onClick: handleCreateRecipient }, 'Añadir Destinatario')
                    )
                ),
                React.createElement('div', { className: 'card' },
                    React.createElement('div', { className: 'title' }, 'Lista de Destinatarios'),
                    React.createElement('table', { style: { width: '100%', borderCollapse: 'collapse', color: '#fff' } },
                        React.createElement('thead', null,
                            React.createElement('tr', { style: { textAlign: 'left', borderBottom: '1px solid #444' } },
                                React.createElement('th', { style: { padding: 8 } }, 'ID'),
                                React.createElement('th', { style: { padding: 8 } }, 'Email'),
                                React.createElement('th', { style: { padding: 8 } }, 'Nombre'),
                                React.createElement('th', { style: { padding: 8 } }, 'Grupo'),
                                React.createElement('th', { style: { padding: 8 } }, 'Acciones')
                            )
                        ),
                        React.createElement('tbody', null,
                            recipients.map(r => 
                                React.createElement('tr', { key: r.id, style: { borderBottom: '1px solid #222' } },
                                    React.createElement('td', { style: { padding: 8 } }, r.id),
                                    React.createElement('td', { style: { padding: 8 } }, r.email),
                                    React.createElement('td', { style: { padding: 8 } }, r.name || '-'),
                                    React.createElement('td', { style: { padding: 8 } }, r.recipient_type || 'OTROS'),
                                    React.createElement('td', { style: { padding: 8 } },
                                        React.createElement('button', { 
                                            style: { backgroundColor: '#ef4444', fontSize: '0.8rem', padding: '4px 8px' },
                                            onClick: () => handleDeleteRecipient(r.id)
                                        }, 'Eliminar')
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

function ThresholdModal({ serverId, onClose }) {
    const [values, setValues] = useState({ cpu: '', memory: '', disk: '' });
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        const load = async () => {
            try {
                const t = await fetchJSON(`/api/umbrales/${serverId}`);
                setValues({
                    cpu: t?.cpu_threshold ?? '',
                    memory: t?.memory_threshold ?? '',
                    disk: t?.disk_threshold ?? ''
                });
            } catch (e) {
                console.error(e);
            } finally {
                setLoading(false);
            }
        };
        load();
    }, [serverId]);

    const handleSave = async () => {
        setError('');
        const v = {};
        const validate = (val, name) => {
            if (val === '' || val === null || val === undefined) return undefined;
            const n = parseFloat(val);
            if (isNaN(n) || n < 0.1 || n > 100) return `Error en ${name}: 0.1 - 100`;
            return n;
        };

        const cpu = validate(values.cpu, 'CPU');
        if (typeof cpu === 'string') { setError(cpu); return; }
        if (cpu !== undefined) v.cpu_threshold = cpu;

        const mem = validate(values.memory, 'Memoria');
        if (typeof mem === 'string') { setError(mem); return; }
        if (mem !== undefined) v.memory_threshold = mem;

        const disk = validate(values.disk, 'Disco');
        if (typeof disk === 'string') { setError(disk); return; }
        if (disk !== undefined) v.disk_threshold = disk;

        try {
            await fetchJSON(`/api/umbrales/${serverId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(v)
            });
            alert('Umbrales actualizados');
            onClose();
        } catch (e) {
            alert('Error: ' + e.message);
        }
    };

    return React.createElement('div', { 
        style: { 
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, 
            background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 
        } 
    },
        React.createElement('div', { className: 'card', style: { width: 400 } },
            React.createElement('div', { className: 'title' }, `Umbrales para ${serverId}`),
            loading ? 'Cargando...' : React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 15 } },
                React.createElement('div', null,
                    React.createElement('label', { style: { display: 'block', marginBottom: 5, color: '#94a3b8' } }, 'CPU (%)'),
                    React.createElement('input', { 
                        type: 'number', step: '0.1', 
                        value: values.cpu, 
                        onChange: e => setValues({...values, cpu: e.target.value}),
                        placeholder: 'Global',
                        style: { width: '100%', padding: 8, background: '#1e293b', border: '1px solid #475569', color: '#fff', borderRadius: 4 }
                    })
                ),
                React.createElement('div', null,
                    React.createElement('label', { style: { display: 'block', marginBottom: 5, color: '#94a3b8' } }, 'Memoria (%)'),
                    React.createElement('input', { 
                        type: 'number', step: '0.1', 
                        value: values.memory, 
                        onChange: e => setValues({...values, memory: e.target.value}),
                        placeholder: 'Global',
                        style: { width: '100%', padding: 8, background: '#1e293b', border: '1px solid #475569', color: '#fff', borderRadius: 4 }
                    })
                ),
                React.createElement('div', null,
                    React.createElement('label', { style: { display: 'block', marginBottom: 5, color: '#94a3b8' } }, 'Disco (%)'),
                    React.createElement('input', { 
                        type: 'number', step: '0.1', 
                        value: values.disk, 
                        onChange: e => setValues({...values, disk: e.target.value}),
                        placeholder: 'Global',
                        style: { width: '100%', padding: 8, background: '#1e293b', border: '1px solid #475569', color: '#fff', borderRadius: 4 }
                    })
                ),
                error && React.createElement('div', { style: { color: '#ef4444' } }, error),
                React.createElement('div', { style: { display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 10 } },
                    React.createElement('button', { onClick: onClose, style: { background: '#444' } }, 'Cancelar'),
                    React.createElement('button', { onClick: handleSave }, 'Guardar')
                )
            )
        )
    );
}

function BarChart({ labels, data, label, color='#22d3ee' }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
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
          borderColor: color,
          borderWidth: 1
        }]
      },
      options: { 
        responsive: true, 
        plugins: { legend: { display: false } },
        scales: {
            y: { beginAtZero: true, grid: { color: '#334155' }, ticks: { color: '#94a3b8' } },
            x: { grid: { color: '#334155' }, ticks: { color: '#94a3b8' } }
        }
      }
    });
    return () => chart.destroy();
  }, [JSON.stringify(labels), JSON.stringify(data)]);
  return React.createElement('canvas', { height: 100, ref });
}

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
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const flowCounts = {};
  data.forEach(d => {
      const f = d.flow || 'Unknown';
      flowCounts[f] = (flowCounts[f] || 0) + 1;
  });
  const chartLabels = Object.keys(flowCounts);
  const chartData = Object.values(flowCounts);

  const handleDownload = () => {
    const token = getDashboardToken();
    const url = '/api/data-monitoring/export';
    fetch(url, { headers: { 'X-Dashboard-Token': token } })
    .then(response => {
        if (!response.ok) throw new Error('Download failed');
        return response.blob();
    })
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `monitoring_data_${new Date().toISOString().slice(0,10)}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    })
    .catch(err => alert('Error descargando CSV: ' + err.message));
  };

  if (!userInfo) {
    return null;
  }

  if (!userInfo.is_admin && !userInfo.can_view_data_monitoring) {
    return React.createElement('div', { className: 'card', style: { marginTop: 16 } },
      React.createElement('div', { className: 'title', style: { marginBottom: 8 } }, 'Dashboard Postman (Datos Ingestados)'),
      React.createElement('div', { style: { color: '#94a3b8' } }, 'No tienes permiso para ver este dashboard. Pide acceso a un administrador.')
    );
  }

  if (!currentServer) {
    return null;
  }

  if (!currentServer.data_monitoring_enabled) {
    return React.createElement('div', { className: 'card', style: { marginTop: 16 } },
      React.createElement('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 } },
        React.createElement('div', { className: 'title' }, 'Dashboard Postman (Datos Ingestados)'),
      ),
      React.createElement('div', { style: { color: '#94a3b8' } }, 'Este dashboard está desactivado para el servidor seleccionado. Actívalo desde Admin → Grupos de Servidores.')
    );
  }

  return React.createElement('div', { className: 'card', style: { marginTop: 16 } },
    React.createElement('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 } },
      React.createElement('div', { className: 'title' }, 'Dashboard Postman (Datos Ingestados)'),
      React.createElement('div', { style: { display: 'flex', gap: 8 } },
        React.createElement('button', { onClick: handleDownload, style: { background: '#10b981', border: 'none', color: 'white', cursor: 'pointer', borderRadius: 4, padding: '4px 12px', fontSize: '0.85rem' } }, 'Descargar CSV'),
        React.createElement('button', { onClick: fetchData, style: { background: 'none', border: '1px solid #444', color: '#ccc', cursor: 'pointer', borderRadius: 4, padding: '4px 8px' } }, 'Refrescar')
      )
    ),
    error && React.createElement('div', { style: { color: '#ef4444', marginBottom: 8 } }, error),
    
    chartLabels.length > 0 && React.createElement('div', { style: { marginBottom: 24 } },
        React.createElement('div', { className: 'title', style: { fontSize: '0.9rem', marginBottom: 8, color: '#94a3b8' } }, 'Distribución por Flujo'),
        React.createElement(BarChart, { labels: chartLabels, data: chartData, label: 'Eventos', color: '#3b82f6' })
    ),

    React.createElement('div', { style: { overflowX: 'auto' } },
      React.createElement('table', { style: { width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' } },
        React.createElement('thead', null,
          React.createElement('tr', { style: { textAlign: 'left', borderBottom: '1px solid #444' } },
            ['ID', 'App', 'Caja', 'Usuario', 'Flujo', 'Patente', 'Tipo Veh.', 'Producto', 'Created At', 'Entity ID', 'Working Day', 'Received At'].map(h => 
                React.createElement('th', { key: h, style: { padding: 8, color: '#94a3b8' } }, h)
            )
          )
        ),
        React.createElement('tbody', null,
          data.length === 0 
            ? React.createElement('tr', null, React.createElement('td', { colSpan: 12, style: { padding: 8, textAlign: 'center', color: '#888' } }, 'Sin datos'))
            : data.map(row => 
                React.createElement('tr', { key: row.id, style: { borderBottom: '1px solid #333' } },
                  React.createElement('td', { style: { padding: 8 } }, row.id),
                  React.createElement('td', { style: { padding: 8 } }, row.app),
                  React.createElement('td', { style: { padding: 8 } }, row.cashRegisterNumber),
                  React.createElement('td', { style: { padding: 8 } }, row.userName),
                  React.createElement('td', { style: { padding: 8 } }, row.flow),
                  React.createElement('td', { style: { padding: 8 } }, row.patent || '-'),
                  React.createElement('td', { style: { padding: 8 } }, row.vehicleType || '-'),
                  React.createElement('td', { style: { padding: 8 } }, row.product || '-'),
                  React.createElement('td', { style: { padding: 8 } }, row.createdAt),
                  React.createElement('td', { style: { padding: 8 } }, row.entityId),
                  React.createElement('td', { style: { padding: 8 } }, row.workingDay),
                  React.createElement('td', { style: { padding: 8, color: '#888', fontSize: '0.75rem' } }, new Date(row.received_at).toLocaleString())
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
  const [editingThresholdsServerId, setEditingThresholdsServerId] = useState(null);

  const load = async () => {
    const token = getDashboardToken();
    if (!token && !demo) {
      setStatus({ ok: false, message: 'No autenticado' });
      return;
    }
    try {
      const health = await fetchJSON('/api/health');
      if (!health.ok) {
        setStatus({ ok: false, message: `Backend Error: ${health.error || 'Unknown error'}` });
        return;
      }
      setStatus({ ok: true, message: '' });

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
        const apiBase = getApiBase();
        setStatus({ ok: false, message: `Error conectando a ${apiBase}: ${msg}` });
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

  const latest = history[history.length - 1] || { memory:{total:0,used:0,free:0,cache:0}, cpu:{total:0,per_core:[]}, disk:{total:0,used:0,free:0,percent:0}, docker:{running_containers:0, containers:[]} };
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

  const handleDeleteServer = async (serverId, e) => {
    e.stopPropagation();
    if (!confirm(`¿Eliminar servidor ${serverId}?`)) return;
    try {
        await fetchJSON(`/api/admin/servers/${serverId}`, { method: 'DELETE' });
        load(); // Reload servers
        if (selected === serverId) setSelected('');
    } catch (e) {
        alert('Error eliminando servidor: ' + e.message);
    }
  };

  const handleUpdateInterval = async (serverId, val) => {
    const newVal = parseInt(val);
    // Optimistic update
    setServers(servers.map(s => s.server_id === serverId ? { ...s, report_interval: newVal } : s));

    try {
        await fetchJSON(`/api/admin/servers/${serverId}/config`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ report_interval: newVal })
        });
        // Success
    } catch (e) {
        alert('Error actualizando intervalo: ' + e.message);
        load(); // Revert
    }
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
        React.createElement('div', { className: 'title', style: { display: 'flex', alignItems: 'center', gap: '12px' } },
            React.createElement('div', { 
                style: { 
                    height: '40px', 
                    width: '40px', 
                    background: `url("assets/logo.svg") center/contain no-repeat`,
                    filter: 'drop-shadow(0 0 4px rgba(56, 189, 248, 0.5))'
                }
            }),
            'ServPulse 2.1'
        ),
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

  const currentServer = servers.find(s => s.server_id === selected);
  const currentInterval = currentServer ? (currentServer.report_interval || 2400) : 2400;

  const INTERVAL_OPTIONS = [
      { label: 'Tiempo Real (10s)', value: 10 },
      { label: '5 Minutos', value: 300 },
      { label: '30 Minutos', value: 1800 },
      { label: '40 Minutos (Default)', value: 2400 },
      { label: '1 Hora', value: 3600 },
      { label: '24 Horas', value: 86400 },
  ];

  // VISTA DASHBOARD
  return (
    React.createElement('div', { className: 'wrap' },
      renderHeader(),
      !status.ok && React.createElement('div', { className: 'card', style: { border: '1px solid #ef4444', marginBottom: 12 } },
        React.createElement('div', { style: { color: '#ef4444' } }, status.message || 'Sin datos en vivo'),
        React.createElement('div', { className: 'muted' }, 'Verifique token, TLS y disponibilidad del backend')
      ),
        React.createElement('div', { className: 'card', style: { marginBottom: 16, display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' } },
        React.createElement('label', null, 'Servidor: '),
        React.createElement('select', { value: selected, onChange: e => setSelected(e.target.value) },
          servers.map(s => React.createElement('option', { key: s.server_id, value: s.server_id }, s.group_name ? `${s.server_id} (${s.group_name})` : s.server_id))
        ),
        React.createElement('button', { onClick: () => setShowChooser(v => !v) }, 'Cambiar servidor'),
        selected && React.createElement('div', { style: { marginLeft: 10, padding: '4px 8px', background: '#334155', borderRadius: 4, fontSize: '0.8rem' } },
            `ID: ${selected}`
        ),
        selected && React.createElement('button', { 
            onClick: () => setEditingThresholdsServerId(selected),
            style: { marginLeft: 10, padding: '4px 8px', background: '#3b82f6', borderRadius: 4, fontSize: '0.8rem', border: 'none', color: 'white', cursor: 'pointer' } 
        }, 'Umbrales'),
        
        React.createElement('div', { style: { marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 } },
            React.createElement('span', { className: 'muted' }, 'Intervalo:'),
            (userInfo && userInfo.is_admin && selected) 
                ? React.createElement('select', { 
                    value: currentInterval, 
                    onChange: e => handleUpdateInterval(selected, e.target.value),
                    style: { padding: '4px 8px', borderRadius: 4, background: '#1e293b', color: '#fff', border: '1px solid #444' }
                  },
                    INTERVAL_OPTIONS.map(o => React.createElement('option', { key: o.value, value: o.value }, o.label))
                  )
                : React.createElement('span', { className: 'muted' }, 
                    INTERVAL_OPTIONS.find(o => o.value === currentInterval)?.label || `${currentInterval}s`
                  )
        )
      ),
      showChooser && React.createElement('div', { className: 'card', style: { marginBottom: 16 } },
        React.createElement('div', { className: 'title' }, 'Servidores conectados'),
        servers.length === 0
          ? React.createElement('div', { className: 'muted' }, 'Sin servidores registrados')
          : React.createElement('div', { style: { display: 'grid', gap: 8, gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))' } },
              servers.map(s => React.createElement('div', {
                key: s.server_id,
                style: { 
                    border: '1px solid #444', 
                    padding: 8, 
                    borderRadius: 4, 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center',
                    background: s.server_id === selected ? '#1e293b' : undefined,
                    borderColor: s.server_id === selected ? '#22d3ee' : '#444',
                    cursor: 'pointer'
                },
                onClick: () => { setSelected(s.server_id); setShowChooser(false); }
              }, 
                React.createElement('div', null,
                  React.createElement('span', { style: { fontWeight: 500 } }, s.server_id),
                  React.createElement('div', { className: 'muted', style: { fontSize: '0.75rem', marginTop: 4 } }, s.group_name ? `Grupo: ${s.group_name} · Postman: ${s.data_monitoring_enabled ? 'ON' : 'OFF'}` : `Postman: ${s.data_monitoring_enabled ? 'ON' : 'OFF'}`)
                ),
                userInfo && userInfo.is_admin && React.createElement('button', {
                    style: { backgroundColor: '#ef4444', fontSize: '0.7rem', padding: '2px 6px', marginLeft: 8, zIndex: 10 },
                    onClick: (e) => handleDeleteServer(s.server_id, e)
                }, 'Eliminar')
              ))
            ),
        React.createElement('div', { style: { marginTop: 8 } },
          React.createElement('button', { onClick: () => setShowChooser(false) }, 'Cerrar')
        )
      ),
      React.createElement(DataMonitoringDashboard, { currentServer, userInfo }),
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
      ),
      editingThresholdsServerId && React.createElement(ThresholdModal, { 
          serverId: editingThresholdsServerId, 
          onClose: () => setEditingThresholdsServerId(null) 
      })
    )
  );
}

const root = window.ReactDOM.createRoot(document.getElementById('root'));
root.render(window.React.createElement(App));
