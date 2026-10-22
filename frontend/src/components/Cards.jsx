import React from 'react';

export function Feature({ icon, title, desc }) {
  return <div className="feature-card"><span className="feature-icon">{icon}</span><h3>{title}</h3><p>{desc}</p></div>;
}
export function Stat({ title, value, note }) {
  return <div className="stat-card"><span>{title}</span><strong>{value}</strong><small>{note}</small></div>;
}
