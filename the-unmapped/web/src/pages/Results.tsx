import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { ExtractResponse, SkillSummary, OccupationSummary } from '../api';
import { Badge, Card, EmptyState, SectionTitle } from '../components/ui';

interface LocationState {
  result: ExtractResponse;
  text: string;
  profileSkills: SkillSummary[];
  targetOccupation: OccupationSummary | null;
}

export default function Results() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as LocationState | null;

  if (!state?.result) return <Navigate to="/discover" replace />;

  const { result, text, profileSkills, targetOccupation } = state;

  const toCareer = () => {
    const extracted = result.skills
      .filter((s) => s.confidence === 'high' || s.confidence === 'review')
      .map((s) => ({ skill_id: s.skill_id, label: s.label }));
    const merged = [...profileSkills];
    for (const s of extracted) {
      if (!merged.some((m) => m.skill_id === s.skill_id)) merged.push(s);
    }
    navigate('/career', { state: { profileSkills: merged, targetOccupation } });
  };

  return (
    <div className="max-w-4xl space-y-6">
      <SectionTitle sub="What the extraction engine found in your description. Every prediction shows its evidence — direct quotes or explicit contextual inference.">
        Your skill analysis
      </SectionTitle>

      <Card>
        <h2 className="text-sm font-semibold uppercase tracking-widest text-ink-soft">Your description</h2>
        <p className="mt-2 leading-relaxed">{text}</p>
      </Card>

      {result.abstained ? (
        <Card>
          <EmptyState
            title="The engine abstained"
            body={result.abstention_reason || 'No skill reached the confidence threshold. Try describing specific tasks, tools, or responsibilities.'}
          />
        </Card>
      ) : (
        <div className="space-y-4">
          {result.skills.map((s) => (
            <Card key={s.skill_id}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="font-display text-xl">{s.label}</h3>
                  <p className="text-sm text-ink-soft font-mono">{s.skill_id}</p>
                </div>
                <div className="flex gap-2">
                  <Badge tone={s.confidence === 'high' ? 'high' : 'review'}>
                    {s.confidence === 'high' ? 'high confidence' : 'needs review'}
                  </Badge>
                  <Badge tone="info">
                    model score {s.score.toFixed(3)} <span className="opacity-70">(uncalibrated)</span>
                  </Badge>
                </div>
              </div>

              <div className="mt-3">
                {s.method === 'phrase_match' ? (
                  <p className="text-sm">
                    <Badge tone="high">direct match</Badge>{' '}
                    <span className="text-ink-soft">Found verbatim in your description:</span>{' '}
                    <q className="font-medium">{s.evidence.span}</q>
                  </p>
                ) : (
                  <p className="text-sm">
                    <Badge tone="review">contextual inference</Badge>{' '}
                    <span className="text-ink-soft">{s.evidence.note || 'Inferred from context — no verbatim span.'}</span>
                  </p>
                )}
              </div>

              {s.occupation_context.length > 0 && (
                <p className="mt-2 text-sm text-ink-soft">
                  Similar roles in the dataset:{' '}
                  {s.occupation_context.map((o) => o.title).join(' · ')}
                </p>
              )}

              {s.notes.length > 0 && (
                <div className="mt-2 rounded-lg bg-amber-warm/10 border border-amber-warm/30 px-3 py-2 text-sm">
                  {s.notes.map((n, i) => (
                    <p key={i}>⚠ {n.replace('ambiguous_with:', 'Ambiguous with skill ').replace(/:.*$/, '')} — kept separate, both need review.</p>
                  ))}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {!result.abstained && (
        <div className="flex flex-wrap gap-3">
          <button
            onClick={toCareer}
            className="rounded-xl bg-teal-deep px-6 py-3 font-medium text-white hover:bg-teal-ink transition-colors"
          >
            Plan a career move with these skills →
          </button>
          <Link
            to="/discover"
            className="rounded-xl border border-line bg-white px-6 py-3 font-medium hover:border-ink-soft"
          >
            Analyse another description
          </Link>
        </div>
      )}

      <p className="text-xs text-ink-soft leading-relaxed">
        Scores are uncalibrated cosine similarities from a TF-IDF model — useful for ranking,
        not probabilities. {result.evaluation_note}
      </p>
    </div>
  );
}
