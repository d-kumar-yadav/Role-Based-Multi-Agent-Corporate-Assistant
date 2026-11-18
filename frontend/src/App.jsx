import { useState } from 'react';
import Login from './Login';
import Chat from './Chat';

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));

  if (!token) {
    return <Login onLogin={(t) => { localStorage.setItem('token', t); setToken(t); }} />;
  }

  return (
    <Chat
      key={token}
      token={token}
      onLogout={() => {
        localStorage.removeItem('token');
        setToken(null);
      }}
    />
  );
}
