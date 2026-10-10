import { useEffect, useMemo, useState } from 'react';
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { api, MarketSignals } from '../api';
import { Card, EmptyState, ErrorState, SectionTitle, Spinner } from '../components/ui';

const TREND_COLORS: Record<string, string> = {
  'Very High Growth': '#0f766e',
  'High Growth': '#65a30d',
  Emerging: '#b45309',
  Stable: '#a8a29e',
};
const TRENDS = Object.keys(TREND_COLORS);

export default function Dashboard() {
  const [data, setData] = useState<MarketSignals | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [activeTrends, setActiveTrends] = useState<string[]>(TRENDS);
  const [domainQuery, setDomainQuery] = useState('');

  useEffect(() => {
    api.marketSignals().then(setData).catch(setError);
  }, []);

  const salaryRows = useMemo(() => {
    if (!data) return [];
    const q = domainQuery.trim().toLowerCase();
    return data.salary_by_domain.filter((r) => !q || r.domain.toLowerCase().includes(q));
  }, [data, domainQuery]);

  const demandRows = useMemo(() => {
    if (!data) return [];
    const byDomain: Record<string, Record<string, number | string>> = {};
    for (const r of data.demand_by_domain) {
      if (!activeTrends.includes(r.trend)) continue;
      byDomain[r.domain] = byDomain[r.domain] || { domain: r.domain };
      (byDomain[r.domain] as Record<string, number>)[r.trend] =
        ((byDomain[r.domain] as Record<string, number>)[r.trend] || 0) + r.n_occupations;
    }
    return Object.values(byDomain);
  }, [data, activeTrends]);

  if (error) return <div className="max-w-4xl"><ErrorState error={error} onRetry={() => window.location.reload()} /></div>;
  if (!data) return <div className="max-w-4xl"><Spinner label="Loading labour-market data…" /></div>;

  return (
    <div className="max-w-6xl space-y-8">
      <SectionTitle sub="Two genuine signals from the supplied dataset: salary distributions and demand trends by domain. Both are cross-sectional snapshots — the dataset contains no time series, so no historical trends are shown.">
        Indian labour market dashboard
      </SectionTitle>

      <Card>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="font-display text-2xl">Salary by domain</h2>
            <p className="text-sm text-ink-soft">Median of occupation-level median salaries (LPA). Hover for the interquartile range.</p>
          </div>
          <input
            value={domainQuery}
            onChange={(e) => setDomainQuery(e.target.value)}
            placeholder="Filter domains…"
            aria-label="Filter domains"
            className="rounded-xl border border-line bg-paper px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-deep"
          />
        </div>
        {salaryRows.length === 0 ? (
          <div className="mt-4"><EmptyState title="No domains match" body="Clear the filter to see all domains." /></div>
        ) : (
          <div className="mt-4 h-[420px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={salaryRows} layout="vertical" margin={{ left: 8, right: 24 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e7e0d3" />
                <XAxis type="number" tick={{ fontSize: 12 }} label={{ value: 'LPA', position: 'insideBottomRight', fontSize: 12 }} />
                <YAxis type="category" dataKey="domain" width={190} tick={{ fontSize: 12 }} />
                <Tooltip
                  formatter={(_v, _n, props) => {
                    const p = props?.payload as { median_lpa: number; p25_lpa: number; p75_lpa: number; n_occupations: number } | undefined;
                    return p ? [`${p.median_lpa} LPA (IQR ${p.p25_lpa}–${p.p75_lpa}, n=${p.n_occupations})`, 'median'] : [];
                  }}
                />
                <Bar dataKey="median_lpa" name="median LPA" radius={[0, 6, 6, 0]}>
                  {salaryRows.map((r) => (
                    <Cell key={r.domain} fill="#0f766e" />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
        <p className="mt-3 text-xs text-ink-soft">
          Unit: {data.unit} n = {data.n_occupations} occupations across {data.n_domains} domains.
        </p>
      </Card>

      <Card>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="font-display text-2xl">Demand trends by domain</h2>
            <p className="text-sm text-ink-soft">Count of occupations per demand label within each domain.</p>
          </div>
          <fieldset className="flex flex-wrap gap-2">
            <legend className="sr-only">Demand trends to show</legend>
            {TRENDS.map((t) => (
              <label key={t} className="inline-flex items-center gap-1.5 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={activeTrends.includes(t)}
                  onChange={() =>
                    setActiveTrends(activeTrends.includes(t) ? activeTrends.filter((x) => x !== t) : [...activeTrends, t])
                  }
                  className="accent-teal-800"
                />
                <span className="inline-block h-3 w-3 rounded-sm" style={{ background: TREND_COLORS[t] }} />
                {t}
              </label>
            ))}
          </fieldset>
        </div>
        {demandRows.length === 0 ? (
          <div className="mt-4"><EmptyState title="Nothing to show" body="Select at least one demand trend." /></div>
        ) : (
          <div className="mt-4 h-[460px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={demandRows} margin={{ bottom: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e7e0d3" />
                <XAxis dataKey="domain" tick={{ fontSize: 11 }} interval={0} angle={-35} textAnchor="end" height={90} />
                <YAxis tick={{ fontSize: 12 }} label={{ value: 'occupations', angle: -90, position: 'insideLeft', fontSize: 12 }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {activeTrends.map((t) => (
                  <Bar key={t} dataKey={t} stackId="d" fill={TREND_COLORS[t]} name={t} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      <Card>
        <h2 className="font-display text-xl">Source & caveats</h2>
        <p className="mt-2 text-sm"><strong>Source.</strong> {data.source}</p>
        <ul className="mt-3 space-y-2">
          {data.caveats.map((c, i) => (
            <li key={i} className="text-sm text-ink-soft leading-relaxed">• {c}</li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
