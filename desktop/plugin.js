// qbo-ops desktop pane: QuickBooks connection health + quick reports.
// SDK-only imports; theme vars; boring-and-true by design.
// Import style follows the SDK reference examples (named imports — the SDK
// module has no default export). JSX comes from react/jsx-runtime (the file
// loads uncompiled — no JSX syntax).
import { useQuery } from '@hermes/plugin-sdk';
import { jsx } from 'react/jsx-runtime';

const id = 'qbo-ops';

function HealthChip() {
  const q = useQuery({
    queryKey: ['qbo-health'],
    queryFn: () => Promise.reject(new Error('unconfigured')),
    refetchInterval: 60000,
    retry: false,
  });
  // Unconfigured is the expected state until the user connects; render calm.
  return jsx('div', {
    style: { display: 'flex', alignItems: 'center', gap: '6px', padding: '0 8px' },
    children: [
      jsx('span', { style: { width: '8px', height: '8px', borderRadius: '50%', background: 'var(--ui-text-quaternary)', display: 'inline-block' } }),
      jsx('span', { style: { fontSize: '12px', color: 'var(--ui-text-secondary)' },
        children: 'QBO not connected' }),
    ],
  });
}

function QboPane({ ctx }) {
  const health = useQuery({
    queryKey: ['qbo-health'],
    queryFn: () => ctx.rest('/health', { timeoutMs: 15000 }),
    refetchInterval: 120000,
  });
  const pnl = useQuery({
    queryKey: ['qbo-pnl'],
    queryFn: () => ctx.rest('/pnl', { timeoutMs: 30000 }),
    enabled: health.data && health.data.status === 'connected',
  });
  const audit = useQuery({
    queryKey: ['qbo-audit'],
    queryFn: () => ctx.rest('/audit', { timeoutMs: 30000 }),
    enabled: health.data && health.data.status === 'connected',
  });
  const st = health.data && health.data.status;
  const fmt = (n) => n == null ? '—' : '$' + Math.abs(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).replace(/^/, n < 0 ? '-' : '');
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
        children: `This month: income ${fmt(pnl.data.income)} · net ${fmt(pnl.data.net_income)}`,
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
