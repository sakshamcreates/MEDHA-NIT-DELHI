import { Link } from 'react-router-dom';
import { Card } from '../components/ui';

export default function Landing() {
  return (
    <div className="space-y-14">
      <section className="pt-6 md:pt-12 max-w-3xl">
        <p className="text-sm font-semibold uppercase tracking-widest text-teal-ink">
          Career skill intelligence · India
        </p>
        <h1 className="font-display text-4xl md:text-6xl leading-[1.05] mt-4">
          Millions of Indians have skills the formal job market can't see.
        </h1>
        <p className="mt-6 text-lg text-ink-soft leading-relaxed">
          A shop assistant who manages stock, cash, and suppliers. A farmer who tests soil
          and schedules irrigation. Their work is real — but it never appears on a résumé
          in words an employer searches for. <strong className="text-ink">THE UNMAPPED</strong>{' '}
          turns plain-language descriptions of informal work into structured, verifiable
          skill profiles, and maps those profiles onto real occupations in the Indian
          labour market.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            to="/discover"
            className="rounded-xl bg-teal-deep px-6 py-3 font-medium text-white hover:bg-teal-ink transition-colors"
          >
            Discover my skills
          </Link>
          <Link
            to="/dashboard"
            className="rounded-xl border border-line bg-white px-6 py-3 font-medium hover:border-ink-soft transition-colors"
          >
            Explore the labour market
          </Link>
        </div>
      </section>

      <section className="grid md:grid-cols-3 gap-4">
        {[
          {
            t: 'Describe your work',
            d: 'Write what you actually do — in your own words, in any mix of formal and informal language. No jargon required.',
          },
          {
            t: 'Get structured skills',
            d: 'A transparent model matches your description against 241 canonical skills, showing exactly which words it matched — and which skills it inferred from context.',
          },
          {
            t: 'Plan your next move',
            d: 'See which skills a target occupation needs, which you already have, and a prioritized learning pathway for the gaps — grounded in real labour-market data.',
          },
        ].map((s) => (
          <Card key={s.t}>
            <h2 className="font-display text-xl">{s.t}</h2>
            <p className="mt-2 text-ink-soft leading-relaxed">{s.d}</p>
          </Card>
        ))}
      </section>

      <section className="max-w-3xl">
        <h2 className="font-display text-2xl">Built for the Indian labour market</h2>
        <p className="mt-3 text-ink-soft leading-relaxed">
          The engine is trained on a dataset of <strong className="text-ink">820 Indian
          occupations</strong> with salary bands, demand trends, education requirements, and
          qualifying examinations. The dashboard shows real salary distributions and demand
          signals by domain — cross-sectional snapshots from the supplied data, never
          invented trends.
        </p>
        <p className="mt-3 text-ink-soft leading-relaxed">
          We show our uncertainty openly: model scores are uncalibrated, the evaluation is
          still in progress, and twelve-month outcome predictions are not offered because
          they cannot be honestly calibrated.
        </p>
      </section>
    </div>
  );
}
