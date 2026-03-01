import React, { useState, useEffect } from 'react';
import { QRCodeSVG } from 'qrcode.react';

const App: React.FC = () => {
  const [active, setActive] = useState(false);
  const [tab, setTab] = useState('vpn');
  const [loading, setLoading] = useState(false);
  const [nodes, setNodes] = useState<any[]>([]);
  const [payments, setPayments] = useState<any[]>([]);
  const [showQR, setShowQR] = useState(false);
  const [stats, setStats] = useState({
    latency: '--',
    nodes: '--',
    uptime: '--',
    pqc: 'ML-DSA-65',
    balance: '42.08 X0T',
    logs: [] as string[]
  });

  const API_URL = `${window.location.protocol}//${window.location.host}/api`;

  useEffect(() => {
    const fetchStatus = () => {
      fetch(`${API_URL}/status`)
        .then(res => res.json())
        .then(data => {
          setStats(prev => ({ ...prev, ...data }));
        })
        .catch(console.error);
    };

    const fetchNodes = () => {
      fetch(`${API_URL}/maas/nodes`)
        .then(res => res.json())
        .then(setNodes)
        .catch(console.error);
    };

    const fetchPayments = () => {
      fetch(`${API_URL}/admin/payments`)
        .then(res => res.json())
        .then(setPayments)
        .catch(console.error);
    };

    fetchStatus();
    fetchNodes();
    fetchPayments();
    const interval = setInterval(() => {
      fetchStatus();
      if (tab === 'billing') fetchPayments();
    }, 5000);
    return () => clearInterval(interval);
  }, [tab]);

  const approvePayment = async (paymentId: number) => {
    try {
      const res = await fetch(`${API_URL}/admin/payments/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paymentId })
      });
      const data = await res.json();
      if (data.success) {
        alert("Payment Approved & Tokens Credited!");
      }
    } catch (e) {
      alert("Approval failed");
    }
  };

  const toggleConnection = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/vpn/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active })
      });
      const data = await res.json();
      if (data.success) {
        setActive(!active);
      }
    } catch (e) {
      alert('Connection failed: Mesh Backend unreachable');
    }
    setLoading(false);
  };

  const renderContent = () => {
    switch(tab) {
      case 'vpn':
        return (
          <>
            <button 
              className={`power-button ${active ? 'active' : ''}`}
              onClick={toggleConnection}
              disabled={loading}
            >
              <svg className="icon" viewBox="0 0 24 24">
                <path d="M13,3H11V13H13V3M17.83,5.17L16.41,6.59C17.42,7.57 18.05,8.9 18.05,10.37C18.05,13.28 15.39,15.65 12.05,15.65C8.71,15.65 6.05,13.28 6.05,10.37C6.05,8.9 6.68,7.57 7.69,6.59L6.27,5.17C4.88,6.41 4,8.19 4,10.17C4,14.04 7.14,17.17 11,17.17C14.86,17.17 18,14.04 18,10.17C18,8.19 17.12,6.41 15.73,5.17H17.83Z" />
              </svg>
            </button>
            
            <div style={{ marginTop: '30px', textAlign: 'center' }}>
              <div style={{ fontSize: '1.2rem', color: active ? 'var(--accent-color)' : 'var(--error-color)' }}>
                {loading ? 'Routing Traffic...' : active ? 'Secure Mesh Active' : 'Shields Offline'}
              </div>
              <button onClick={() => setShowQR(!showQR)} style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--accent-color)',
                fontSize: '0.7rem',
                textDecoration: 'underline',
                cursor: 'pointer',
                marginTop: '10px'
              }}>
                {showQR ? 'Hide Config' : 'Generate Mobile Config (QR)'}
              </button>
            </div>

            {showQR && (
              <div style={{ background: 'white', padding: '15px', borderRadius: '8px', marginTop: '20px' }}>
                <QRCodeSVG value={`vless://x0tta6bl4-secure-node@89.125.1.107:443?security=reality&pqc=ml-dsa-65#x0tta6bl4-PQC`} size={150} />
              </div>
            )}

            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-label">Latency</div>
                <div className="stat-value">{stats.latency}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Nodes</div>
                <div className="stat-value">{stats.nodes}</div>
              </div>
            </div>

            <div className="terminal" style={{
              width: '100%',
              maxWidth: '400px',
              height: '80px',
              background: 'rgba(0,0,0,0.5)',
              border: '1px solid rgba(0, 255, 157, 0.1)',
              marginTop: '20px',
              borderRadius: '4px',
              padding: '10px',
              fontSize: '0.65rem',
              fontFamily: 'monospace',
              color: 'var(--accent-color)',
              overflowY: 'hidden',
              display: 'flex',
              flexDirection: 'column-reverse'
            }}>
              {(stats.logs.length > 0 ? stats.logs : [
                '[MONITOR] Initializing x0tta6bl4 Mesh...',
                '[INFO] PQC Core ready'
              ]).map((log, i) => (
                <div key={i} style={{ opacity: 1 - (i * 0.2) }}>{log}</div>
              ))}
            </div>
          </>
        );
      case 'maas':
        return (
          <div style={{ width: '100%', maxWidth: '500px' }}>
            <h2 style={{ borderLeft: '3px solid var(--accent-color)', paddingLeft: '15px', marginBottom: '30px' }}>
              MaaS Marketplace
            </h2>
            {nodes.map(node => (
              <div key={node.id} style={{ 
                background: 'rgba(255,255,255,0.03)', 
                padding: '20px', 
                borderRadius: '8px', 
                marginBottom: '15px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                border: '1px solid rgba(255,255,255,0.05)'
              }}>
                <div>
                  <div style={{ fontSize: '1rem', fontWeight: 'bold' }}>{node.region}</div>
                  <div style={{ fontSize: '0.7rem', opacity: 0.5 }}>ID: {node.id}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ color: 'var(--accent-color)' }}>${node.price}</div>
                  <button style={{ 
                    background: 'transparent', 
                    border: '1px solid var(--accent-color)', 
                    color: 'var(--accent-color)',
                    padding: '4px 12px',
                    borderRadius: '4px',
                    fontSize: '0.8rem',
                    marginTop: '5px',
                    cursor: 'pointer'
                  }}>{node.status === 'Rented' ? 'Manage' : 'Rent'}</button>
                </div>
              </div>
            ))}
          </div>
        );
      case 'wallet':
        return (
          <div style={{ textAlign: 'center', width: '100%' }}>
            <h2 style={{ opacity: 0.5, fontSize: '0.8rem', letterSpacing: '2px' }}>AVAILABLE BALANCE</h2>
            <div style={{ fontSize: '3rem', fontWeight: 'bold', color: 'var(--accent-color)' }}>{stats.balance}</div>
            <div style={{ marginTop: '20px', display: 'flex', gap: '10px', justifyContent: 'center' }}>
              <button style={{ background: 'var(--accent-color)', color: 'black', padding: '10px 20px', borderRadius: '4px', border: 'none', fontWeight: 'bold' }}>DEPOSIT</button>
              <button style={{ background: 'transparent', color: 'white', border: '1px solid rgba(255,255,255,0.2)', padding: '10px 20px', borderRadius: '4px' }}>WITHDRAW</button>
            </div>
          </div>
        );
      case 'dao':
        return (
          <div style={{ width: '100%', maxWidth: '500px' }}>
            <h2 style={{ borderLeft: '3px solid var(--accent-color)', paddingLeft: '15px', marginBottom: '20px' }}>Governance</h2>
            {[
              { id: 'prop-01', title: 'Expand nodes to South America', votes: '1.2M', status: 'Voting' },
              { id: 'prop-02', title: 'Update PQC to Kyber-1024', votes: '4.5M', status: 'Passed' },
            ].map(prop => (
              <div key={prop.id} style={{ background: 'rgba(255,255,255,0.02)', padding: '15px', borderRadius: '8px', marginBottom: '10px' }}>
                <div style={{ fontSize: '0.9rem' }}>{prop.title}</div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '10px', fontSize: '0.7rem' }}>
                  <span>Votes: {prop.votes}</span>
                  <span style={{ color: prop.status === 'Voting' ? 'var(--accent-color)' : 'white' }}>{prop.status}</span>
                </div>
              </div>
            ))}
          </div>
        );
      case 'billing':
        return (
          <div style={{ width: '100%', maxWidth: '600px' }}>
            <h2 style={{ borderLeft: '3px solid var(--accent-color)', paddingLeft: '15px', marginBottom: '20px' }}>Admin: Pending Payments</h2>
            {payments.filter(p => p.status === 'pending').map(p => (
              <div key={p.id} style={{ background: 'rgba(255,255,255,0.03)', padding: '15px', borderRadius: '8px', marginBottom: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontSize: '0.9rem' }}>{p.email}</div>
                  <div style={{ fontSize: '0.7rem', opacity: 0.5 }}>{new Date(p.created_at).toLocaleString()}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ color: 'var(--accent-color)', fontWeight: 'bold' }}>${p.amount}</div>
                  <button onClick={() => approvePayment(p.id)} style={{ background: 'var(--accent-color)', border: 'none', color: 'black', padding: '4px 10px', borderRadius: '4px', fontSize: '0.7rem', marginTop: '5px', cursor: 'pointer', fontWeight: 'bold' }}>APPROVE</button>
                </div>
              </div>
            ))}
            {payments.filter(p => p.status === 'pending').length === 0 && <div style={{ opacity: 0.5, textAlign: 'center' }}>No pending orders.</div>}
          </div>
        );
    }
  };

  return (
    <div className="app-container">
      <header className="header">
        <div className="logo" style={{ fontWeight: 'bold', fontSize: '1.2rem', color: 'var(--accent-color)' }}>
          x0tta6bl4
        </div>
        <div className={`status-badge ${active ? 'pulse' : ''}`}>
          {loading ? 'PROCESSING...' : active ? 'PQC PROTECTED' : 'UNSECURED'}
        </div>
      </header>

      <main className="main-content">
        {renderContent()}
      </main>

      <nav className="nav-bar">
        <div className={`nav-item ${tab === 'vpn' ? 'active' : ''}`} onClick={() => setTab('vpn')}>SHIELD</div>
        <div className={`nav-item ${tab === 'maas' ? 'active' : ''}`} onClick={() => setTab('maas')}>MARKET</div>
        <div className={`nav-item ${tab === 'billing' ? 'active' : ''}`} onClick={() => setTab('billing')}>BILLING</div>
        <div className={`nav-item ${tab === 'wallet' ? 'active' : ''}`} onClick={() => setTab('wallet')}>WALLET</div>
        <div className={`nav-item ${tab === 'dao' ? 'active' : ''}`} onClick={() => setTab('dao')}>DAO</div>
      </nav>
    </div>
  );
};

export default App;
