import { useState } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const DEMO_PERSONAS = [
  {
    name: 'Alice Johnson',
    role: 'employee',
    department: 'Sales',
    email: 'alice.johnson@meridianglobal.example',
    clearance: 'Public & Internal',
    desc: 'Regular employee with basic company access',
    badgeColor: 'bg-neutral-100 text-neutral-800 border-neutral-300',
  },
  {
    name: 'Bob Smith',
    role: 'manager',
    department: 'Sales',
    email: 'bob.smith@meridianglobal.example',
    clearance: 'Confidential & Approvals',
    desc: 'Department manager who approves expense/leave claims',
    badgeColor: 'bg-blue-50 text-blue-800 border-blue-200',
  },
  {
    name: 'Meera Iyer',
    role: 'hr',
    department: 'HR',
    email: 'meera.iyer@meridianglobal.example',
    clearance: 'HR Only (Leaves, POSH, Appraisals)',
    desc: 'HR officer with full access to HR policies',
    badgeColor: 'bg-purple-50 text-purple-800 border-purple-200',
  },
  {
    name: 'Vikram Singh',
    role: 'finance',
    department: 'Finance',
    email: 'vikram.singh@meridianglobal.example',
    clearance: 'Finance Only (Budgets, Travel limits)',
    desc: 'Finance officer managing expense approvals & invoices',
    badgeColor: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  },
  {
    name: 'Suresh Pillai',
    role: 'it',
    department: 'IT',
    email: 'suresh.pillai@meridianglobal.example',
    clearance: 'IT Only (Credentials, VPN, Assets)',
    desc: 'IT administrator with system & security permissions',
    badgeColor: 'bg-amber-50 text-amber-800 border-amber-200',
  },
  {
    name: 'Marcus Vance (CTO)',
    role: 'executive',
    department: 'Engineering',
    email: 'cto@meridianglobal.example',
    clearance: 'Executive Clearance',
    desc: 'Chief Technology Officer with cross-domain access',
    badgeColor: 'bg-rose-50 text-rose-800 border-rose-200',
  },
  {
    name: 'Elena Vance (CEO)',
    role: 'executive',
    department: 'Executive',
    email: 'ceo@meridianglobal.example',
    clearance: 'Full Company Clearance',
    desc: 'Chief Executive Officer with universal system clearance',
    badgeColor: 'bg-neutral-900 text-white border-neutral-800',
  },
];

export default function Login({ onLogin }) {
  const [email, setEmail] = useState('alice.johnson@meridianglobal.example');
  const [password, setPassword] = useState('password123');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const executeLogin = async (userEmail, userPassword) => {
    setError('');
    setLoading(true);

    try {
      const payload = new URLSearchParams({ username: userEmail, password: userPassword });
      const res = await fetch(`${API_BASE}/auth/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: payload,
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Authentication failed');

      onLogin(data.access_token);
    } catch (err) {
      setError(err.message || 'Error connecting to server');
    } finally {
      setLoading(false);
    }
  };

  const handleManualSubmit = (e) => {
    e.preventDefault();
    executeLogin(email, password);
  };

  const handlePersonaClick = (persona) => {
    setEmail(persona.email);
    setPassword('password123');
    executeLogin(persona.email, 'password123');
  };

  const formatRole = (role, dept) => {
    let r = role || '';
    if (r.toLowerCase() === 'hr') r = 'HR';
    else if (r.toLowerCase() === 'it') r = 'IT';
    else r = r.charAt(0).toUpperCase() + r.slice(1);
    return dept ? `${r} · ${dept}` : r;
  };

  return (
    <div className="min-h-screen bg-neutral-50 flex flex-col items-center justify-center px-4 py-6">
      {/* 2) Header (top, centered, small) */}
      <div className="flex items-center gap-2.5 mb-5">
        <div className="w-8 h-8 rounded-lg bg-neutral-950 text-white flex items-center justify-center font-bold text-sm shadow-sm">
          M
        </div>
        <span className="text-base font-semibold text-neutral-950 tracking-tight">Meridian Copilot</span>
      </div>

      {/* 3) Main card */}
      <div className="w-full max-w-md bg-white border border-neutral-200 rounded-xl p-6 shadow-sm space-y-5">
        <div>
          <h1 className="text-lg font-semibold text-neutral-950">Sign in</h1>
          <p className="text-sm text-neutral-500 mt-0.5">Use your company account.</p>
        </div>

        <form onSubmit={handleManualSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-neutral-600 mb-1.5">Employee Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@meridianglobal.example"
              className="w-full h-10 px-3 border border-neutral-300 rounded-lg text-sm text-neutral-900 placeholder:text-neutral-400 focus:border-neutral-900 focus:outline-none transition"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-neutral-600 mb-1.5">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full h-10 px-3 border border-neutral-300 rounded-lg text-sm text-neutral-900 placeholder:text-neutral-400 focus:border-neutral-900 focus:outline-none transition"
            />
          </div>

          {error && <p className="text-xs text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full h-10 bg-neutral-950 text-white rounded-lg text-sm font-medium hover:bg-neutral-800 disabled:bg-neutral-300 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        {/* 4) Persona picker */}
        <div className="pt-4 border-t border-neutral-200 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-neutral-400">Demo accounts</span>
            <code className="text-xs text-neutral-500 font-mono">password123</code>
          </div>

          <div className="max-h-56 overflow-y-auto space-y-0.5">
            {DEMO_PERSONAS.map((p) => {
              const isSelected = email === p.email;
              return (
                <button
                  key={p.email}
                  type="button"
                  onClick={() => handlePersonaClick(p)}
                  disabled={loading}
                  className={`w-full h-10 flex items-center justify-between px-2.5 rounded-md text-left transition-colors ${
                    isSelected ? 'bg-neutral-100' : 'hover:bg-neutral-50'
                  }`}
                >
                  <span className="text-sm text-neutral-900">{p.name}</span>
                  <span className="text-xs text-neutral-500">{formatRole(p.role, p.department)}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
