import { FormEvent, useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { ApiError, api, OccupationSummary, RecommendResponse, SkillSummary } from '../api';
import { Badge, Card, EmptyState, ErrorState, SectionTitle, Spinner } from '../components/ui';

const EDUCATIONS = ["10th Pass", "12th Pass", "Diploma", "Bachelor's", "Master's", "PhD"];

export default function Career() {
  const location = useLocation();
  const incoming = (location.state as { profileSkills?: SkillSummary[]; targetOccupation?: OccupationSummary | null } | null) || {};

  const [occupations, setOccupations] = useState<OccupationSummary[]>([]);
  const [skills, setSkills] = useState<SkillSummary[]>([]);
  const [occQuery, setOccQuery] = useState(incoming.targetOccupation?.title || '');
  const [pickedOcc, setPickedOcc] = useState<OccupationSummary | null>(incoming.targetOccupation || null);
  const [profile, setProfile] = useState<SkillSummary[]>(incoming.profileSkills || []);
  const [skillQuery, setSkillQuery] = useState('');
  const [education, setEducation] = useState('');
  const [result, setResult] = useState<RecommendResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api.occupations().then(setOccupations).catch(() => {});
    api.skills().then(setSkills).catch(() => {});
  }, []);

  const pickOccupation = (title: string) => {
    const o = occupations.find((x) => x.title.toLowerCase() === title.trim().toLowerCase());
    setPickedOcc(o ?? null);
    setOccQuery(title);
  };

  const addSkill = (label: string) => {
    const s = skills.find((x) => x.label.toLowerCase() === label.trim().toLowerCase());
    if (s && !profile.some((p) => p.skill_id === s.skill_id)) setProfile([...profile, s]);
    setSkillQuery('');
  };

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!pickedOcc) {
      setError(new ApiError(400, 'Please choose a target occupation from the list.'));
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.recommend(
        profile.map((s) => s.skill_id),
        pickedOcc.id,
        education || null,
      );
      setResult(r);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-4xl space-y-6">
      <SectionTitle sub="Pick a target occupation and your current skills. The recommender shows what matches, what's missing, and a prioritized pathway — all explained, nothing invented.">
        Plan a career transition
      </SectionTitle>

      <Card>
        <form onSubmit={onSubmit} className="space-y-5">
          <div>
            <label htmlFor="occ" className="block text-sm font-medium">Target occupation <span className="text-red-700">*</span></label>
            <input
              id="occ" list="occ-list2" value={occQuery}
              onChange={(e) => pickOccupation(e.target.value)}
              placeholder="e.g. Accountants and Auditors"
              className="mt-2 w-full rounded-xl border border-line bg-paper px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-teal-deep"
            />
            <datalist id="occ-list2">{occupations.map((o) => <option key={o.id} value={o.title} />)}</datalist>
          </div>
          <div>
            <label htmlFor="pskill" className="block text-sm font-medium">Your skills</label>
            <input
              id="pskill" list="skill-list2" value={skillQuery}
              onChange={(e) => setSkillQuery(e.target.value)}
              onBlur={() => skillQuery && addSkill(skillQuery)}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addSkill(skillQuery); } }}
              placeholder="Type a skill and press Enter"
              className="mt-2 w-full rounded-xl border border-line bg-paper px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-teal-deep"
            />
            <datalist id="skill-list2">{skills.map((s) => <option key={s.skill_id} value={s.label} />)}</datalist>
            <div className="mt-2 flex flex-wrap gap-2">
              {profile.map((s) => (
                <span key={s.skill_id} className="inline-flex items-center gap-1 rounded-full bg-teal-deep/10 border border-teal-deep/30 px-3 py-1 text-sm">
                  {s.label}
                  <button type="button" aria-label={`Remove ${s.label}`}
                    onClick={() => setProfile(profile.filter((p) => p.skill_id !== s.skill_id))}
                    className="text-teal-ink hover:text-red-700">×</button>
                </span>
              ))}
              {profile.length === 0 && <span className="text-sm text-ink-soft">No skills added yet — or start from the <a className="underline text-teal-ink" href="/discover">skill discovery</a> page.</span>}
            </div>
          </div>
          <div>
            <label htmlFor="edu" className="block text-sm font-medium">Your education <span className="font-normal text-ink-soft">(optional)</span></label>
            <select id="edu" value={education} onChange={(e) => setEducation(e.target.value)}
              className="mt-2 w-full rounded-xl border border-line bg-paper px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-teal-deep">
              <option value="">Prefer not to say</option>
              {EDUCATIONS.map((e) => <option key={e} value={e}>{e}</option>)}
            </select>
          </div>
          <button type="submit" disabled={loading}
            className="w-full rounded-xl bg-teal-deep px-6 py-3 font-medium text-white hover:bg-teal-ink disabled:opacity-60">
            {loading ? 'Computing…' : 'Show my transition plan'}
          </button>
        </form>
        {loading && <Spinner label="Running the recommender…" />}
      </Card>

      {!!error && <ErrorState error={error} onRetry={() => setError(null)} />}

      {result && (
        <div className="space-y-6">
          <Card>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="font-display text-2xl">{result.target_occupation.title}</h2>
                <p className="text-ink-soft">{result.target_occupation.domain} · requires {result.target_occupation.education_required}</p>
                <p className="mt-1 text-sm text-ink-soft">
                  Median salary ₹{result.target_occupation.salary_lpa_median} LPA · demand: {result.target_occupation.demand_trend}
                  {result.target_occupation.qualifying_exams.length > 0 &&
                    ` · exams: ${result.target_occupation.qualifying_exams.join(', ')}`}
                </p>
              </div>
              <div className="text-right">
                <p className="font-display text-4xl">{result.heuristic_rank_score.toFixed(2)}</p>
                <p className="text-xs text-ink-soft max-w-[180px]">heuristic ranking score — <strong>not a probability</strong></p>
              </div>
            </div>
            <p className="mt-4 leading-relaxed">{result.explanation}</p>
            <p className="mt-2 text-xs text-ink-soft">
              Score parts: {Object.entries(result.score_breakdown).map(([k, v]) => `${k} ${v.toFixed(2)}`).join(' · ')}
            </p>
          </Card>

          <div className="grid md:grid-cols-2 gap-4">
            <Card>
              <h3 className="font-medium">Matching skills ({result.matched_skills.length})</h3>
              {result.matched_skills.length === 0
                ? <p className="mt-2 text-sm text-ink-soft">None yet — the pathway below is your starting point.</p>
                : <ul className="mt-2 space-y-1">{result.matched_skills.map((s) => <li key={s.skill_id} className="text-sm">✓ {s.label}</li>)}</ul>}
            </Card>
            <Card>
              <h3 className="font-medium">Missing skills ({result.missing_skills.length})</h3>
              <ul className="mt-2 space-y-1">{result.missing_skills.map((s) => <li key={s.skill_id} className="text-sm">○ {s.label}</li>)}</ul>
            </Card>
          </div>

          <Card>
            <h3 className="font-display text-xl">Prioritized learning pathway</h3>
            <div className="mt-4 space-y-4">
              {result.pathway.map((p, i) => (
                <div key={p.skill_id} className="border-l-2 border-teal-deep/40 pl-4">
                  <p className="font-medium">{i + 1}. {p.label} <span className="text-sm text-ink-soft">· priority {p.priority_score.toFixed(2)}</span></p>
                  <p className="text-sm text-ink-soft">{p.why}</p>
                  <ul className="mt-1 space-y-1">
                    {p.next_steps.map((ns, j) => (
                      <li key={j} className="text-sm">
                        <Badge tone={ns.source === 'dataset' ? 'high' : 'info'}>
                          {ns.source === 'dataset' ? 'from dataset' : 'suggestion'}
                        </Badge>{' '}{ns.text}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </Card>

          <Card>
            <h3 className="font-medium">Twelve-month feasibility</h3>
            <div className="mt-2 rounded-xl border border-line bg-paper px-4 py-3">
              <Badge tone="warn">unavailable</Badge>
              <p className="mt-2 text-sm leading-relaxed">{result.twelve_month_feasibility.reason}</p>
              <p className="mt-1 text-sm text-ink-soft">{result.twelve_month_feasibility.what_is_needed}</p>
            </div>
          </Card>

          {result.warnings.length > 0 && (
            <Card>
              <h3 className="font-medium">Data-quality warnings</h3>
              <ul className="mt-2 space-y-1">
                {result.warnings.map((w, i) => <li key={i} className="text-sm text-ink-soft">⚠ {w}</li>)}
              </ul>
            </Card>
          )}
        </div>
      )}

      {!result && !loading && !error && (
        <EmptyState title="No plan yet" body="Choose a target occupation and add your skills, then run the recommender." />
      )}
    </div>
  );
}
