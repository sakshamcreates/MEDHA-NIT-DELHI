import { FormEvent, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError, api, OccupationSummary, SkillSummary } from '../api';
import { Card, FieldError, SectionTitle, Spinner } from '../components/ui';

const EXAMPLE =
  "For two years I did the accounts for my father's textile shop in Hoshiarpur. " +
  "I entered every sale in Tally, made bills in Excel, and filed the GST returns with our CA. " +
  "I also handled cash, paid the suppliers, and kept the stock register updated.";

export default function Discover() {
  const navigate = useNavigate();
  const [text, setText] = useState('');
  const [skills, setSkills] = useState<SkillSummary[]>([]);
  const [occupations, setOccupations] = useState<OccupationSummary[]>([]);
  const [pickedSkills, setPickedSkills] = useState<SkillSummary[]>([]);
  const [skillQuery, setSkillQuery] = useState('');
  const [occQuery, setOccQuery] = useState('');
  const [pickedOcc, setPickedOcc] = useState<OccupationSummary | null>(null);
  const [errors, setErrors] = useState<{ text?: string; form?: string }>({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.skills().then(setSkills).catch(() => {});
    api.occupations().then(setOccupations).catch(() => {});
  }, []);

  const addSkill = (label: string) => {
    const s = skills.find((x) => x.label.toLowerCase() === label.trim().toLowerCase());
    if (s && !pickedSkills.some((p) => p.skill_id === s.skill_id)) {
      setPickedSkills([...pickedSkills, s]);
    }
    setSkillQuery('');
  };

  const pickOccupation = (title: string) => {
    const o = occupations.find((x) => x.title.toLowerCase() === title.trim().toLowerCase());
    setPickedOcc(o ?? null);
    setOccQuery(o ? o.title : title);
  };

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const errs: typeof errors = {};
    if (!text.trim()) errs.text = 'Please describe your work experience.';
    else if (text.trim().length > 5000) errs.text = 'Please keep your description under 5,000 characters.';
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setSubmitting(true);
    setErrors({});
    try {
      const result = await api.extract(text.trim(), 10);
      navigate('/results', {
        state: {
          result,
          text: text.trim(),
          profileSkills: pickedSkills,
          targetOccupation: pickedOcc,
        },
      });
    } catch (err) {
      setErrors({ form: err instanceof ApiError ? err.message : 'Something went wrong.' });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-3xl">
      <SectionTitle sub="Describe informal work in your own words. The engine matches it against 241 canonical skills — showing its evidence, not just its answers.">
        Discover your skills
      </SectionTitle>

      <Card>
        <form onSubmit={onSubmit} noValidate>
          <label htmlFor="desc" className="block text-sm font-medium">
            Your work experience <span className="text-red-700">*</span>
          </label>
          <textarea
            id="desc"
            rows={6}
            value={text}
            onChange={(e) => setText(e.target.value)}
            aria-describedby={errors.text ? 'desc-err' : undefined}
            aria-invalid={!!errors.text}
            placeholder="e.g. I drive a delivery van across the city, plan my routes each morning, handle cash on delivery…"
            className="mt-2 w-full rounded-xl border border-line bg-paper px-4 py-3 leading-relaxed focus:outline-none focus:ring-2 focus:ring-teal-deep"
          />
          {errors.text && <FieldError id="desc-err" message={errors.text} />}
          <div className="mt-2 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setText(EXAMPLE)}
              className="text-sm text-teal-ink underline underline-offset-2 hover:text-teal-deep"
            >
              Try an example description
            </button>
            <span className="text-xs text-ink-soft">{text.length}/5000</span>
          </div>

          <div className="mt-6">
            <label htmlFor="skillq" className="block text-sm font-medium">
              Skills you already know you have <span className="text-ink-soft font-normal">(optional)</span>
            </label>
            <input
              id="skillq"
              list="skill-list"
              value={skillQuery}
              onChange={(e) => setSkillQuery(e.target.value)}
              onBlur={() => skillQuery && addSkill(skillQuery)}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addSkill(skillQuery); } }}
              placeholder="Start typing a skill, e.g. Data Entry"
              className="mt-2 w-full rounded-xl border border-line bg-paper px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-teal-deep"
            />
            <datalist id="skill-list">
              {skills.slice(0, 241).map((s) => (
                <option key={s.skill_id} value={s.label} />
              ))}
            </datalist>
            {pickedSkills.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {pickedSkills.map((s) => (
                  <span key={s.skill_id} className="inline-flex items-center gap-1 rounded-full bg-teal-deep/10 border border-teal-deep/30 px-3 py-1 text-sm">
                    {s.label}
                    <button
                      type="button"
                      aria-label={`Remove ${s.label}`}
                      onClick={() => setPickedSkills(pickedSkills.filter((p) => p.skill_id !== s.skill_id))}
                      className="text-teal-ink hover:text-red-700"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="mt-6">
            <label htmlFor="occq" className="block text-sm font-medium">
              Target occupation <span className="text-ink-soft font-normal">(optional — used on the career page)</span>
            </label>
            <input
              id="occq"
              list="occ-list"
              value={occQuery}
              onChange={(e) => pickOccupation(e.target.value)}
              placeholder="Start typing, e.g. Accountants and Auditors"
              className="mt-2 w-full rounded-xl border border-line bg-paper px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-teal-deep"
            />
            <datalist id="occ-list">
              {occupations.map((o) => (
                <option key={o.id} value={o.title} />
              ))}
            </datalist>
            {occQuery && !pickedOcc && (
              <p className="mt-1 text-sm text-amber-warm">No exact match — pick an occupation from the list.</p>
            )}
          </div>

          {errors.form && (
            <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
              {errors.form}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="mt-6 w-full rounded-xl bg-teal-deep px-6 py-3 font-medium text-white hover:bg-teal-ink disabled:opacity-60 transition-colors"
          >
            {submitting ? 'Analysing…' : 'Analyse my description'}
          </button>
        </form>
        {submitting && <Spinner label="Running the extraction engine…" />}
      </Card>
    </div>
  );
}
