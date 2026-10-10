import { Link, NavLink, Outlet } from 'react-router-dom';

const links = [
  { to: '/', label: 'Home', end: true },
  { to: '/discover', label: 'Discover skills' },
  { to: '/career', label: 'Career paths' },
  { to: '/dashboard', label: 'Labour market' },
];

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-line bg-paper/90 backdrop-blur sticky top-0 z-10">
        <div className="mx-auto max-w-6xl px-4 py-4 flex items-center justify-between">
          <Link to="/" className="font-display text-xl tracking-tight">
            ARUNYA
          </Link>
          <nav aria-label="Primary" className="flex gap-1 md:gap-2">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.end}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    isActive ? 'bg-ink text-paper' : 'text-ink-soft hover:bg-stone-200/60 hover:text-ink'
                  }`
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <div className="mx-auto max-w-6xl px-4 py-10">
          <Outlet />
        </div>
      </main>

      <footer className="border-t border-line bg-white/60">
        <div className="mx-auto max-w-6xl px-4 py-8 text-sm text-ink-soft space-y-2">
          <p className="font-medium text-ink">About the model behind this site</p>
          <p>
            Skill extraction uses a TF-IDF model over a 241-skill canonical registry built from
            the Indian Skills Dataset (820 occupations). Scores are <em>uncalibrated model
            scores</em>, not probabilities.
          </p>
          <p>
            Evaluation status: 0 of 30 pilot descriptions human-reviewed — model performance
            is not yet validated, and no accuracy claims are made.
          </p>
        </div>
      </footer>
    </div>
  );
}
