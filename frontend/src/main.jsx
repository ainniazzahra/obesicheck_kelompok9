import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './styles.css';

class ErrorBoundary extends React.Component {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error) { console.error('Kesalahan render:', error); }
  render() {
    if (!this.state.failed) return this.props.children;
    return <div style={{ padding: 40, fontFamily: 'sans-serif' }} role="alert"><h2>Terjadi kesalahan pada tampilan</h2>
      <p>Muat ulang halaman. Jika berulang, periksa konsol browser dan log backend.</p>
      <button onClick={() => window.location.reload()}>Muat ulang</button></div>;
  }
}

createRoot(document.getElementById('root')).render(<React.StrictMode><ErrorBoundary><App /></ErrorBoundary></React.StrictMode>);
