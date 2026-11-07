import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import ReactMarkdown from 'react-markdown';
import { Activity, ArrowDown, ArrowUpRight, Bot, Check, ChevronDown, CircleHelp, FileText, Files, GitBranch, LogOut, MessageSquare, Plus, Search, Send, Shield, Sparkles, ThumbsDown, ThumbsUp, Upload, X } from 'lucide-react';
import './styles.css';

const API = import.meta.env.VITE_API_URL || '/api/v1';
const iconMap = { pdf: 'Pdf', docx: 'Doc', txt: 'Text' };
function csrfValue() {
  const token = document.cookie.split('; ').find(part => part.startsWith('csrf_token='));
  return token ? decodeURIComponent(token.slice('csrf_token='.length)) : '';
}
function apiFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  const method = (options.method || 'GET').toUpperCase();
  const csrf = csrfValue();
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && csrf) headers.set('X-CSRF-Token', csrf);
  return fetch(url, { ...options, headers, credentials: 'include' });
}
function App() {
  const [token, setToken] = useState(false);
  const [user, setUser] = useState(null);
  const [loginError, setLoginError] = useState('');
  const [apiHealth, setApiHealth] = useState('checking');
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('adminpass');
  const [files, setFiles] = useState([]);
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [activeTab, setActiveTab] = useState('Ask');
  const [selected, setSelected] = useState(null);
  const [selectedSource, setSelectedSource] = useState(null);
  const [notice, setNotice] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);
    fetch(`${API}/health/live`, { signal: controller.signal })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(data => setApiHealth(data.status === 'alive' ? 'ready' : 'degraded'))
      .catch(() => setApiHealth('offline'))
      .finally(() => clearTimeout(timeout));
    return () => { clearTimeout(timeout); controller.abort(); };
  }, []);
  useEffect(() => {
    apiFetch(`${API}/auth/csrf`).catch(() => {});
    apiFetch(`${API}/auth/me`).then(r => r.ok ? r.json() : Promise.reject()).then(data => { setUser(data); setToken(true); }).catch(() => {});
  }, []);
  useEffect(() => {
    if (!token) return;
    apiFetch(`${API}/documents`).then(r => r.ok ? r.json() : Promise.reject())
      .then(rows => setFiles(rows.map(d => ({ id: d.document_id, documentId: d.document_id, name: d.filename, status: d.status === 'ready' ? 'Ready' : d.status === 'failed' ? 'Failed' : 'Processing', type: d.filename.split('.').pop().toLowerCase() }))))
      .catch(() => setNotice('Could not load documents from the workspace'));
  }, [token]);
  useEffect(() => {
    if (!selected || selected === 'Knowledge graph') { setSelectedSource(null); return; }
    setSelectedSource(null);
    apiFetch(`${API}/chunks/${encodeURIComponent(selected)}`).then(r => r.ok ? r.json() : Promise.reject())
      .then(setSelectedSource).catch(() => setSelectedSource({ error: 'Source unavailable or access denied.' }));
  }, [selected]);
  useEffect(() => {
    if (!token) return;
    const timer = setInterval(() => apiFetch(`${API}/auth/refresh`, { method: 'POST' }).then(r => {
      if (r.status === 401) { setToken(false); setUser(null); }
    }).catch(() => {}), 10 * 60 * 1000);
    return () => clearInterval(timer);
  }, [token]);
  useEffect(() => {
    if (!token || !files.some(f => f.documentId && f.status === 'Processing')) return;
    const timer = setInterval(async () => {
      const pending = files.filter(f => f.documentId && f.status === 'Processing');
      for (const file of pending) {
        try {
          const r = await apiFetch(`${API}/ingest/status/${encodeURIComponent(file.documentId)}`);
          if (!r.ok) continue;
          const status = (await r.json()).status;
          if (['ready', 'failed'].includes(status)) setFiles(prev => prev.map(f => f.documentId === file.documentId ? { ...f, status: status === 'ready' ? 'Ready' : 'Failed' } : f));
        } catch { /* Keep showing the last known status while the API reconnects. */ }
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [token, files]);
  async function login(e) {
    e.preventDefault(); setLoginError('');
    const form = new URLSearchParams({ username, password });
    try { const r = await apiFetch(`${API}/auth/token`, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: form }); const data = await r.json(); if (!r.ok) throw Error(data.detail || 'Login failed'); const me = await apiFetch(`${API}/auth/me`); if (!me.ok) throw Error('Login succeeded but the session could not be loaded'); setUser(await me.json()); setToken(true); }
    catch (err) { setLoginError(err.message === 'Failed to fetch' ? 'API se connect nahi hua. Backend check karke phir try karein.' : err.message); }
  }
  async function upload(e) {
    const incoming = [...e.target.files]; e.target.value = '';
    for (const file of incoming) {
      const id = `${Date.now()}-${file.name}`; const row = { id, name: file.name, status: 'Uploading', type: file.name.split('.').pop().toLowerCase() };
      setFiles(prev => [row, ...prev]); const form = new FormData(); form.append('file', file); form.append('allowed_roles', user?.roles?.includes('admin') ? 'admin,analyst,intern,viewer' : 'analyst,intern,viewer');
      try { const r = await apiFetch(`${API}/ingest/upload`, { method: 'POST', body: form }); const data = await r.json(); if (!r.ok) throw Error(data.detail || 'Upload failed'); setFiles(prev => prev.map(f => f.id === id ? { ...f, documentId: data.document_id, status: data.status === 'exists' ? 'Ready' : 'Processing' } : f)); setNotice(`${file.name} upload ho gaya`); }
    catch (err) { setFiles(prev => prev.map(f => f.id === id ? { ...f, status: 'Failed', error: err.message } : f)); }
    }
  }
  async function retryDocument(documentId) {
    setFiles(prev => prev.map(file => file.documentId === documentId ? { ...file, status: 'Processing' } : file));
    try {
      const response = await apiFetch(`${API}/ingest/retry/${encodeURIComponent(documentId)}`, { method: 'POST' });
      const data = await response.json();
      if (!response.ok) throw Error(data.detail || 'Retry failed');
      setNotice('Retry started');
    } catch (error) {
      setFiles(prev => prev.map(file => file.documentId === documentId ? { ...file, status: 'Failed', error: error.message } : file));
    }
  }
  async function sendFeedback(message, rating) {
    try {
      const r = await apiFetch(`${API}/feedback`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: message.question, answer: message.answer, rating, citations: message.citations || [] }) });
      if (!r.ok) throw Error('Feedback could not be saved');
      setNotice('Thanks — feedback saved');
    } catch (error) { setNotice(error.message); }
  }
  async function ask(e) {
    e?.preventDefault(); const q = question.trim(); if (!q || busy) return;
    setQuestion(''); setBusy(true); setMessages(prev => [...prev, { role: 'user', text: q }, { role: 'assistant', loading: true }]);
    try { const r = await apiFetch(`${API}/query`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: q }) }); const data = await r.json(); if (!r.ok) throw Error(data.detail || 'Query failed'); setMessages(prev => [...prev.slice(0, -1), { role: 'assistant', ...data }]); }
    catch (err) { setMessages(prev => [...prev.slice(0, -1), { role: 'assistant', error: err.message }]); }
    finally { setBusy(false); }
  }
  async function logout() { try { await apiFetch(`${API}/auth/logout`, { method: 'POST' }); } finally { setToken(false); setUser(null); setFiles([]); setMessages([]); } }
  if (!token || !user) return <main className="login-page"><div className="login-card"><div className="brand-mark"><GitBranch size={22}/></div><h1>Welcome back</h1><p className="muted">Sign in to your GraphRAG workspace.</p><div className={`api-state ${apiHealth}`}><span className="api-light"/><span>{apiHealth === "checking" ? "Checking API connection…" : apiHealth === "ready" ? "API is reachable" : apiHealth === "degraded" ? "API responded but reports degraded services" : "API is offline. Start the backend and data services first."}</span></div><form onSubmit={login}><label>Username</label><input value={username} onChange={e => setUsername(e.target.value)} autoComplete="username"/><label>Password</label><input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password"/>{loginError && <div className="error-box">{loginError}</div>}<button className="primary full">Sign in <ArrowUpRight size={16}/></button></form>{import.meta.env.DEV && <div className="demo-hint"><Shield size={14}/> Demo access: admin / adminpass · intern / internpass</div>}</div><span className="login-foot">Private by design GRAPH KNOWLEDGE SYSTEM</span></main>;

  const navItems = [{ name: 'Ask', icon: MessageSquare }, { name: 'Documents', icon: Files }];
  const latestAnswer = [...messages].reverse().find(m => m.role === 'assistant' && !m.loading && !m.error);
  return <div className="app-shell"><aside className="sidebar"><div className="brand"><div className="brand-mark small"><GitBranch size={18}/></div><div><strong>graph<span>rag</span></strong><small>Knowledge workspace</small></div></div><button className="workspace-select"><div className="tenant-avatar">{(user.username || 'A')[0].toUpperCase()}</div><span><b>{user.username || 'Workspace'}</b><small>{user.tenant_id || 'Personal workspace'}</small></span><ChevronDown size={15}/></button><div className="nav-label">Workspace</div><nav>{navItems.map(item => <button key={item.name} onClick={() => setActiveTab(item.name)} className={`nav-item ${activeTab === item.name ? 'active' : ''}`}><item.icon size={17}/>{item.name}{item.name === 'Documents' && files.length > 0 && <span className="nav-count">{files.length}</span>}</button>)}</nav><div className="sidebar-spacer"/><div className="usage-card"><div className="usage-title"><span>Index status</span></div><strong>{files.filter(f => f.status === 'Ready').length} <small>documents ready</small></strong><div className="usage-bar"><i style={{width: `${Math.min(files.length * 12, 100)}%`}}/></div><p>Current session uploads</p></div><button className="user-row" onClick={logout}><div className="user-avatar">{(user.username || 'U')[0].toUpperCase()}</div><span><b>{user.username}</b><small>{user.roles?.join(' · ')}</small></span><LogOut size={16}/></button></aside>
    <main className="main-area"><header className="topbar"><div className="breadcrumbs"><span>Workspace</span><span className="slash">/</span><b>{activeTab}</b></div><div className="top-actions"><span className="secure-tag"><Shield size={13}/> Secure session</span><button className="icon-button" title="Help"><CircleHelp size={18}/></button><div className="top-avatar">{(user.username || 'U')[0].toUpperCase()}</div></div></header>
    {activeTab === 'Documents' ? <section className="page-content"><div className="page-heading"><div><h1>Documents</h1><p className="muted">Manage the files powering your answers.</p></div><label className="primary upload-cta"><Plus size={17}/> Add documents<input type="file" accept=".pdf,.docx,.txt" multiple onChange={upload}/></label></div><div className="metric-row"><div className="metric"><span>Total documents</span><strong>{files.length}</strong><small>in this session</small></div><div className="metric"><span>Ready to search</span><strong>{files.filter(f=>f.status==='Ready').length}</strong><small>indexed successfully</small></div><div className="metric"><span>Processing</span><strong>{files.filter(f=>f.status==='Processing'||f.status==='Uploading').length}</strong><small>usually takes a moment</small></div></div><div className="document-table"><div className="table-title"><b>All documents</b><span>{files.length} files</span></div>{files.length ? files.map(f=><div className="doc-row" key={f.id}><div className={`file-badge ${f.type}`}>{iconMap[f.type] || 'File'}</div><div className="doc-name"><b>{f.name}</b><small>{f.documentId || 'Uploading to your workspace'}</small></div><span className={`status ${f.status.toLowerCase()}`}><i/>{f.status}</span>{f.status === "Failed" && f.documentId && user?.roles?.some(role => ["admin", "analyst"].includes(role)) && <button className="retry-button" onClick={() => retryDocument(f.documentId)}>Retry</button>}<span className="doc-access"><Shield size={13}/> Workspace</span><button className="icon-button" title="Document options"><ArrowDown size={15}/></button></div>) : <div className="empty-docs"><div className="empty-icon"><Upload size={21}/></div><b>Your knowledge base starts here</b><p>Upload a PDF, DOCX, or TXT file to make it searchable.</p><label className="secondary upload-cta"><Upload size={15}/> Choose files<input type="file" accept=".pdf,.docx,.txt" multiple onChange={upload}/></label></div>}</div><div className="info-note"><Shield size={16}/><span><b>Private by default.</b> Documents are scoped to your workspace and filtered by your access role.</span></div></section> : <section className="chat-layout"><div className="chat-main"><div className="chat-heading"><div><h1>Ask your knowledge base</h1><p className="muted">Answers grounded in your documents, connected by context.</p></div><button className="secondary new-chat" onClick={() => setMessages([])}><Plus size={16}/> New chat</button></div><div className="conversation">{messages.length === 0 ? <div className="welcome"><div className="spark-icon"><Sparkles size={21}/></div><span className="welcome-caption">YouR KNOWLEDGE, CONNECTED</span><h2>What would you like to know?</h2><p>Ask a question across your uploaded documents. Every answer includes its sources.</p><div className="suggestions">{['Summarize the key ideas in my documents','What are the main entities and how are they connected?','Find details about a specific project'].map(q=><button key={q} onClick={()=>setQuestion(q)}>{q}<ArrowUpRight size={14}/></button>)}</div></div> : messages.map((m,i)=><div key={i} className={`message ${m.role}`}>{m.role==='user'?<><div className="user-message-avatar">{(user.username||'U')[0].toUpperCase()}</div><div className="message-body"><div className="message-meta">You <span>·</span> JUST NOW</div><div className="user-bubble">{m.text}</div></div></>:<><div className="bot-avatar"><GitBranch size={17}/></div><div className="message-body"><div className="message-meta">GRAPH<span>RAG</span> <span>·</span> {m.loading?'Thinking':m.confidence ? `${m.confidence.toUpperCase()} CONFIDENCE` : 'Response'}</div>{m.loading?<div className="typing"><i/><i/><i/> Searching documents and graph context…</div>:m.error?<div className="error-box">{m.error}</div>:<><div className="answer"><ReactMarkdown>{m.answer || 'I could not find a grounded answer in the available documents.'}</ReactMarkdown></div>{m.invalid_citations?.length>0&&<div className="citation-warning">Some citations could not be verified: {m.invalid_citations.join(', ')}</div>}{m.citations?.length>0&&<div className="citation-list">{m.citations.map((id,n)=><button key={`${id}-${n}`} onClick={()=>setSelected(id)} className="citation-chip"><FileText size={13}/>{id}<ArrowUpRight size={12}/></button>)}</div>}{m.graph_edges?.length>0&&<div className="graph-card"><div className="graph-card-title"><span><GitBranch size={15}/> Connected knowledge</span><span>{m.graph_edges.length} relationships</span></div><div className="graph-flow">{m.graph_edges.slice(0,4).map((edge,n)=><React.Fragment key={n}><span className="graph-node">{edge.source || edge.from || edge.start || edge.source_name || 'Entity'}</span><span className="graph-edge" title={edge.relation || edge.type}>{edge.relation || edge.type || '→'}<i/></span>{n===Math.min(m.graph_edges.length,4)-1&&<span className="graph-node">{edge.target || edge.to || edge.end || edge.target_name || 'Entity'}</span>}</React.Fragment>)}</div></div>}<div className="answer-actions"><span>{m.retrieved_chunks ?? 0} source chunks, {m.query_trace?.total_latency_ms ?? '—'} ms</span><div><button onClick={()=>sendFeedback(m,'up')} title="Helpful"><ThumbsUp size={15}/></button><button onClick={()=>sendFeedback(m,'down')} title="Not helpful"><ThumbsDown size={15}/></button></div></div></>}</div></>}</div>)}</div><form className="composer" onSubmit={ask}><textarea value={question} onChange={e=>setQuestion(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();ask();}}} placeholder="Ask a question about your documents..." rows={1}/><div className="composer-bottom"><span><Shield size={13}/> Answers are scoped to your access</span><button className="send-button" disabled={!question.trim()||busy} aria-label="Send question"><Send size={16}/></button></div></form><div className="composer-foot">AI-generated answers can be inaccurate. Verify important details with the linked sources.</div></div>
    <aside className="right-panel"><div className="panel-header"><div><span className="panel-kicker">Your workspace</span><h3>Knowledge base</h3></div><button className="icon-button" onClick={()=>setActiveTab('Documents')} title="View documents"><ArrowUpRight size={17}/></button></div><div className="panel-stat"><div className="stat-icon"><Files size={17}/></div><div><b>{files.length} documents</b><small>{files.filter(f=>f.status==='Ready').length} ready to search</small></div></div><div className="panel-docs">{files.slice(0,5).map(f=><button className="panel-doc" key={f.id}><span className={`file-badge mini ${f.type}`}>{iconMap[f.type]||'File'}</span><span><b>{f.name}</b><small><i className={`status-dot ${f.status.toLowerCase()}`}/>{f.status}</small></span></button>)}{files.length===0&&<div className="panel-empty">Your uploaded files will appear here.</div>}</div><label className="add-doc-button"><Plus size={15}/> Add a document<input type="file" accept=".pdf,.docx,.txt" multiple onChange={upload}/></label><div className="panel-divider"/><div className="panel-section-title"><span>Recent graph</span><Activity size={14}/></div>{latestAnswer?.graph_edges?.length ? <div className="mini-graph"><div className="mini-graph-visual"><span className="node n1"/><span className="node n2"/><span className="node n3"/><i className="edge e1"/><i className="edge e2"/><i className="edge e3"/></div><div className="mini-graph-caption"><b>{latestAnswer.seed_entities?.length||0} entities connected</b><small>From your latest answer</small></div><button className="view-graph" onClick={()=>setSelected('Knowledge graph')}>Explore graph <ArrowUpRight size={14}/></button></div>:<div className="graph-placeholder"><div className="placeholder-visual"><span/><span/><span/><i/><i/></div><b>Your graph will appear here</b><p>Ask a question to explore connected entities across your knowledge base.</p></div>}<div className="right-bottom"><div className="secure-line"><Shield size={15}/><span><b>Access controlled</b><small>Only authorized sources are retrieved.</small></span><Check size={14}/></div></div></aside></section>}
    </main>{notice&&<div className="toast"><Check size={15}/>{notice}<button onClick={()=>setNotice('')}><X size={14}/></button></div>}{selected&&<div className="modal-backdrop" onClick={()=>setSelected(null)}><div className="source-modal" onClick={e=>e.stopPropagation()}><button className="modal-close" onClick={()=>setSelected(null)}><X size={18}/></button><h2>{selected}</h2><div className="source-preview"><FileText size={18}/>{selectedSource?.text ? <div><b>{selectedSource.filename} · chunk {selectedSource.position + 1}</b><p>{selectedSource.text}</p></div> : <p>{selectedSource?.error || "Loading source…"}</p>}</div><button className="secondary" onClick={()=>setSelected(null)}>Close</button></div></div>}</div>;
}

createRoot(document.getElementById('root')).render(<App/>);
