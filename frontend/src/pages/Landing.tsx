import { Link } from 'react-router-dom'
import GlassCard from '../components/GlassCard'

/**
 * The one page a signed-out visitor sees, and so the only one a search engine
 * can read. Everything else needs an account and renders as the sign-in form,
 * which is why this page carries the whole description of what Eevie is.
 *
 * Deliberately plain HTML underneath — one h1, sections with headings, real
 * prose — because that is what a crawler indexes and what a screen reader
 * announces.
 */

const STEPS = [
  {
    n: '01',
    title: 'Log the fill-up',
    body: 'A charge or a tank, with the odometer reading at the time. Two numbers and a date — the whole entry takes a few seconds at the charger.',
  },
  {
    n: '02',
    title: 'The numbers derive themselves',
    body: 'Distance comes from consecutive readings, consumption from the level either side. Nothing is stored that could be worked out, so nothing can drift out of step.',
  },
  {
    n: '03',
    title: 'Ask what another car would have cost',
    body: 'Any car against any car — the one you drive, one you are weighing up, or the same car judged two different ways.',
  },
]

const POINTS = [
  {
    title: 'Priced at the time, not today',
    body: 'Each stretch of driving is costed at the pump price or electricity tariff that applied when you drove it. Pricing a year of history at this week’s rate would be wrong in whichever direction fuel has moved since.',
  },
  {
    title: 'Either direction',
    body: 'Built for an EV owner asking what petrol would have cost, and equally for a diesel owner asking what an EV would have saved. Neither side is the special one.',
  },
  {
    title: 'Like-for-like, or not — your call',
    body: 'Both cars use the figures you entered, so two cars quoted the same come out identical. Weigh your own car towards what it actually achieves instead, and the page says plainly that the comparison has stopped being even.',
  },
]

export default function Landing() {
  return (
    <div className="relative z-[1] mx-auto w-full max-w-5xl px-5 py-10 md:py-16">
      <header className="flex items-center justify-between">
        <span className="flex items-center gap-2.5">
          <span
            aria-hidden="true"
            className="grid h-8 w-8 place-items-center rounded-lg"
            style={{ background: 'linear-gradient(135deg, var(--accent-2), var(--accent))' }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent-ink)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M13 2 4 14h7l-1 8 9-12h-7z" />
            </svg>
          </span>
          <span className="text-base font-semibold tracking-tight text-ink">Eevie</span>
        </span>

        <Link
          to="/sign-in"
          className="btn-primary focus-ring rounded-lg px-4 py-2 text-sm font-medium"
        >
          Sign in
        </Link>
      </header>

      <main>
        <section className="py-14 md:py-20">
          <h1 className="gradient-text max-w-3xl text-4xl font-semibold leading-tight tracking-tight md:text-6xl">
            What your car actually costs to run
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-ink-2">
            Log every charge and fill-up against your odometer, and find out what a kilometre
            really costs you — then price the same driving in a different car, electric or not,
            at the rates that applied at the time.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link
              to="/sign-in"
              className="btn-primary focus-ring rounded-xl px-5 py-2.5 text-sm font-medium"
            >
              Start logging
            </Link>
            <a
              href="#how"
              className="focus-ring rounded-xl border border-edge px-5 py-2.5 text-sm font-medium text-ink-2 hover:text-ink"
            >
              How it works
            </a>
          </div>
        </section>

        <section aria-labelledby="problem" className="pb-14">
          <GlassCard className="p-7 md:p-10">
            <h2 id="problem" className="text-xl font-semibold tracking-tight text-ink md:text-2xl">
              A laboratory figure is not your car
            </h2>
            <p className="mt-4 max-w-3xl leading-relaxed text-ink-2">
              Manufacturers quote one number, produced under test conditions. It knows nothing
              about the traffic you sit in, the February morning that halves your range, or the
              hill you climb on the way home. Third-party “real world” estimates are still a
              single guess made on someone else’s roads.
            </p>
            <p className="mt-4 max-w-3xl leading-relaxed text-ink-2">
              The only figure that describes your car is the one your own driving produces.
              Eevie works it out from the two numbers you already have at every charger and
              every pump.
            </p>
          </GlassCard>
        </section>

        <section aria-labelledby="how" id="how" className="pb-14">
          <h2 id="how-heading" className="sr-only">How it works</h2>
          <p className="mb-4 text-[11px] uppercase tracking-wider text-ink-3">How it works</p>
          <div className="grid gap-3 md:grid-cols-3">
            {STEPS.map(step => (
              <GlassCard key={step.n} className="p-6">
                <span className="readout text-sm font-semibold" style={{ color: 'var(--accent)' }}>
                  {step.n}
                </span>
                <h3 className="mt-3 text-base font-semibold text-ink">{step.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-ink-3">{step.body}</p>
              </GlassCard>
            ))}
          </div>
        </section>

        <section aria-labelledby="different" className="pb-14">
          <h2 id="different" className="mb-4 text-[11px] uppercase tracking-wider text-ink-3">
            What it does differently
          </h2>
          <div className="grid gap-3 md:grid-cols-3">
            {POINTS.map(point => (
              <GlassCard key={point.title} className="p-6">
                <h3 className="text-base font-semibold text-ink">{point.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-ink-3">{point.body}</p>
              </GlassCard>
            ))}
          </div>
        </section>

        <section aria-labelledby="cta" className="pb-14">
          <GlassCard className="p-7 text-center md:p-10">
            <h2 id="cta" className="text-xl font-semibold tracking-tight text-ink md:text-2xl">
              Two numbers at the charger, and the rest follows
            </h2>
            <p className="mx-auto mt-3 max-w-xl leading-relaxed text-ink-2">
              Free to use. Your log is yours — nobody else can see what you drive.
            </p>
            <Link
              to="/sign-in"
              className="btn-primary focus-ring mt-6 inline-block rounded-xl px-5 py-2.5 text-sm font-medium"
            >
              Create an account
            </Link>
          </GlassCard>
        </section>
      </main>

      <footer className="border-t border-edge py-8 text-sm text-ink-3">
        <p>
          Eevie — running costs for electric and combustion cars, in Ireland and anywhere else
          the numbers make sense.
        </p>
      </footer>
    </div>
  )
}
