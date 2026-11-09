// qbo-ops desktop pane: QuickBooks connection health + quick reports.
// SDK-only imports; theme vars; boring-and-true by design.
//
// Chip contract (learned from ContribBoundary in the app source): a chip whose
// render() throws degrades to an error chip — so the chip is PURE JSX with no
// hooks (chips render outside the QueryClientProvider scope; the bundled
// hello-runtime reference chip uses only useValue/atoms for the same reason).
// Live data lives in the pane, which CAN use useQuery.
import { useQuery } from '@hermes/plugin-sdk';
import { jsx } from 'react/jsx-runtime';

const id = 'qbo-ops';

// Pure static chip — never throws, never fetches. Shows state only when the
// pane reports it (single source of truth; the chip is a courtesy marker).
function HealthChip() {
  return jsx('span', {
    className: 'inline-flex h-full items-center gap-1 px-1.5 text-[0.6875rem] text-(--ui-text-tertiary)',
    children: [
      jsx('span', {
        'aria-hidden': true,
        style: { width: '7px', height: '7px', borderRadius: '50%', background: 'var(--ui-text-quaternary)', display: 'inline-block' },
      }),
      jsx('span', { children: 'qbo' }),
    ],
  });
}

function QboPane({ ctx }) {
  const health = useQuery({
    queryKey: ['qbo-health'],
    queryFn: () => ctx.rest('/health', { timeoutMs: 15000 }),
    refetchInterval: 120000,
    retry: 1,
  });
  const pnl = useQuery({
    queryKey: ['qbo-pnl'],
    queryFn: () => ctx.rest('/pnl', { timeoutMs: 30000 }),
    enabled: !!(health.data && health.data.status === 'connected'),
    retry: 1,
  });
  const audit = useQuery({
    queryKey: ['qbo-audit'],
    queryFn: () => ctx.rest('/audit', { timeoutMs: 30000 }),
    enabled: !!(health.data && health.data.status === 'connected'),
    retry: 1,
  });
  const st = health.data && health.data.status;
  const isLoading = health.isLoading || health.isLoading === undefined && !health.data;
  const fmt = (n) => {
    if (n == null || isNaN(n)) return '—';
    const abs = '$' + Math.abs(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return n < 0 ? '-' + abs : abs;
  };
  return jsx('div', {
    style: { padding: '12px', display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px', color: 'var(--ui-text-secondary)' },
    children: [
      jsx('div', { style: { fontWeight: 600, color: 'var(--ui-text-primary)' }, children: 'QuickBooks Online' }),
      isLoading
        ? jsx('div', { children: 'Checking connection…' })
        : st === 'connected'
          ? jsx('div', { style: { color: 'var(--ui-accent)' }, children: `Connected: ${(health.data && health.data.company) || ''}` })
          : jsx('div', {
              children: st === 'reauth_required'
                ? ((health.data && health.data.message) || 'Re-authentication required — run: hermes auth add qbo-ops:quickbooks')
                : st === 'error'
                  ? ((health.data && health.data.message) || 'Connection error — ask your agent to run a health check.')
                  : ((health.data && health.data.message) || 'Not configured. Ask your agent: "set up QuickBooks".'),
            }),
      st === 'connected' && pnl.data && pnl.data.income != null && jsx('div', {
        children: `This month: income ${fmt(pnl.data.income)} · net ${fmt(pnl.data.net_income)}`,
      }),
      st === 'connected' && audit.data && audit.data.flag_count != null && jsx('div', {
        children: `Close audit: ${audit.data.flag_count} flagged`,
      }),
      jsx('div', { style: { opacity: 0.55, fontSize: '11px' },
        children: 'Interactive versions: ask your agent ("how did last month look?")' }),
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
      data: { placement: 'right', width: '280px' },
      render: () => jsx(QboPane, { ctx: c }),
    });
  },
};
