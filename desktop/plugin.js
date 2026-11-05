// qbo-ops desktop pane: QuickBooks connection health + quick reports.
// SDK-only imports; theme vars; boring-and-true by design.
import { ctx as sdkCtx, jsx, useQuery, atom, useValue } from '@hermes/plugin-sdk';

const id = 'qbo-ops';

function HealthChip() {
  const q = useQuery({
    queryKey: ['qbo-health'],
    queryFn: () => sdkCtx.rest('/health', { timeoutMs: 15000 }),
    refetchInterval: 60000,
  });
  const status = q.data?.status;
  const color = status === 'connected' ? 'var(--ui-accent)'
    : status === 'reauth_required' ? '#e0a83c'
    : 'var(--ui-text-quaternary)';
  return jsx('div', {
    style: { display: 'flex', alignItems: 'center', gap: '6px', padding: '0 8px' },
    children: [
      jsx('span', { style: { width: '8px', height: '8px', borderRadius: '50%', background: color, display: 'inline-block' } }),
      jsx('span', { style: { fontSize: '12px', color: 'var(--ui-text-secondary)' },
        children: status === 'connected' ? (q.data?.company || 'QBO connected') : 'QBO not connected' }),
    ],
  });
}

function QboPane() {
  const health = useQuery({
    queryKey: ['qbo-health'],
    queryFn: () => sdkCtx.rest('/health', { timeoutMs: 15000 }),
    refetchInterval: 120000,
  });
  const pnl = useQuery({
    queryKey: ['qbo-pnl'],
    queryFn: () => sdkCtx.rest('/pnl', { timeoutMs: 30000 }),
    enabled: health.data?.status === 'connected',
  });
  const audit = useQuery({
    queryKey: ['qbo-audit'],
    queryFn: () => sdkCtx.rest('/audit', { timeoutMs: 30000 }),
    enabled: health.data?.status === 'connected',
  });
  const st = health.data?.status;
  return jsx('div', {
    style: { padding: '12px', display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px', color: 'var(--ui-text-secondary)' },
    children: [
      jsx('div', { style: { fontWeight: 600, color: 'var(--ui-text-primary)' }, children: 'QuickBooks Online' }),
      st === 'connected' ? jsx('div', { children: `Connected: ${health.data?.company || ''}` })
        : jsx('div', {
            children: st === 'reauth_required'
              ? (health.data?.message || 'Re-authentication required.')
              : (health.data?.message || 'Not configured. Ask your agent: "set up QuickBooks".'),
          }),
      st === 'connected' && pnl.data && jsx('div', {
        children: `This month: income $${pnl.data.income?.toLocaleString()} · net $${pnl.data.net_income?.toLocaleString()}`,
      }),
      st === 'connected' && audit.data && jsx('div', {
        children: `Close audit: ${audit.data.flag_count} flagged entr${audit.data.flag_count === 1 ? 'y' : 'ies'}`,
      }),
    ],
  });
}

export default {
  id,
  name: 'QuickBooks Online',
  register(c) {
    c.register({
      id: 'qbo-status',
      area: 'statusBar.right',
      order: 50,
      render: () => jsx(HealthChip),
    });
    c.register({
      id: 'qbo-pane',
      area: 'panes',
      title: 'QuickBooks',
      data: { placement: 'right' },
      render: () => jsx(QboPane),
    });
  },
};
