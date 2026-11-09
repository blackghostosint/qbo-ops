// qbo-ops desktop pane: QuickBooks connection health + quick reports.
// SDK-only imports; theme vars; boring-and-true by design.
// NOTE (per catalog review): the desktop SDK exports host/request/etc. via the
// default export shape; `ctx` arrives as the register(ctx) argument, and JSX
// comes from react/jsx-runtime (the file loads uncompiled — no JSX syntax).
import pluginSdk from '@hermes/plugin-sdk';
import { jsx } from 'react/jsx-runtime';

const { useQuery } = pluginSdk;

const id = 'qbo-ops';

function HealthChip() {
  const q = useQuery({
    queryKey: ['qbo-health'],
    queryFn: () => pluginSdk.request('plugins.api', { plugin: id, path: '/health' }).catch(() => ({})),
    refetchInterval: 60000,
  });
  const d = q.data && q.data.response ? q.data.response : q.data || {};
  const status = d.status;
  const color = status === 'connected' ? 'var(--ui-accent)'
    : status === 'reauth_required' ? '#e0a83c'
    : 'var(--ui-text-quaternary)';
  return jsx('div', {
    style: { display: 'flex', alignItems: 'center', gap: '6px', padding: '0 8px' },
    children: [
      jsx('span', { style: { width: '8px', height: '8px', borderRadius: '50%', background: color, display: 'inline-block' } }),
      jsx('span', { style: { fontSize: '12px', color: 'var(--ui-text-secondary)' },
        children: status === 'connected' ? (d.company || 'QBO connected') : 'QBO not connected' }),
    ],
  });
}

function QboPane({ ctx }) {
  const health = useQuery({
    queryKey: ['qbo-health'],
    queryFn: () => ctx.rest('/health', { timeoutMs: 15000 }).catch((e) => ({ status: 'error', message: String(e) })),
    refetchInterval: 120000,
  });
  const pnl = useQuery({
    queryKey: ['qbo-pnl'],
    queryFn: () => ctx.rest('/pnl', { timeoutMs: 30000 }).catch(() => ({})),
    enabled: health.data && health.data.status === 'connected',
  });
  const audit = useQuery({
    queryKey: ['qbo-audit'],
    queryFn: () => ctx.rest('/audit', { timeoutMs: 30000 }).catch(() => ({})),
    enabled: health.data && health.data.status === 'connected',
  });
  const st = health.data && health.data.status;
  return jsx('div', {
    style: { padding: '12px', display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px', color: 'var(--ui-text-secondary)' },
    children: [
      jsx('div', { style: { fontWeight: 600, color: 'var(--ui-text-primary)' }, children: 'QuickBooks Online' }),
      st === 'connected' ? jsx('div', { children: `Connected: ${(health.data && health.data.company) || ''}` })
        : jsx('div', {
            children: st === 'reauth_required'
              ? ((health.data && health.data.message) || 'Re-authentication required — run: hermes auth add qbo-ops:quickbooks')
              : ((health.data && health.data.message) || 'Not configured. Ask your agent: "set up QuickBooks".'),
          }),
      st === 'connected' && pnl.data && jsx('div', {
        children: `This month: income $${(pnl.data.income == null ? '—' : pnl.data.income.toLocaleString())} · net $${(pnl.data.net_income == null ? '—' : pnl.data.net_income.toLocaleString())}`,
      }),
      st === 'connected' && audit.data && jsx('div', {
        children: `Close audit: ${audit.data.flag_count == null ? '—' : audit.data.flag_count} flagged`,
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
      render: () => jsx(QboPane, { ctx: c }),
    });
  },
};
