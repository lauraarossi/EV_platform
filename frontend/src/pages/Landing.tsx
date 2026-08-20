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
    title: 'Note it down',
    body: 'Input each charge or fill up, with the odometer reading at the time. Two numbers and a date — the whole entry takes a few seconds.',
  },
  {
    n: '02',
    title: 'Watch the picture build',
    body: 'Distance, efficiency, running costs and emissions all follow from consecutive entries. There is nothing to calculate and nothing to keep in step.',
  },
  {
    n: '03',
    title: 'Start asking questions',
    body: 'Does it do better in summer? Is the motorway run cheaper than the back roads? What would that other car on your shortlist have managed?',
  },
]

const POINTS = [
  {
    title: 'How efficient is it, really?',
    body: 'Your own kWh or litres per 100 km, measured across every interval you have logged, sitting next to the figure on the spec sheet. Most cars have a story to tell here, and it is rarely the one in the brochure.',
  },
  {
    title: 'How does it compare?',
    body: 'Any car against any car — one you own, one you are curious about, or the same car judged two different ways. Same distance, same prices, so what you are looking at is the difference between the cars.',
  },
  {
    title: 'What is it emitting?',
    body: 'CO2 from the fuel burned or the electricity generated, worked out the same way for both, so the environmental picture sits beside the financial one instead of being a separate argument.',
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
            Get to know your car
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-ink-2">
            Every charge and every fill-up tells you something. Note them down against your
            odometer and the real picture builds itself — how efficient your car actually is,
            what it costs to run, what it emits, and how it measures up against anything else
            you are curious about.
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
              Your car has its own numbers
            </h2>
            <p className="mt-4 max-w-3xl leading-relaxed text-ink-2">
              The figure on the spec sheet came from a laboratory. Yours comes from the roads you
              actually drive: the traffic you sit in, the hill on the way home, the cold early mornings. 
              Both are true; only one of them is about your car.
            </p>
            <p className="mt-4 max-w-3xl leading-relaxed text-ink-2">
              After a handful of entries you will know things about it that no brochure could
              tell you.
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
            Questions it answers
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
              Your car is already telling you things
            </h2>
            <p className="mx-auto mt-3 max-w-xl leading-relaxed text-ink-2">
              Start writing them down and see what turns up. Free to use, and your log is
              yours — nobody else can see what you drive.
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
          Eevie — efficiency, running costs and emissions for electric and combustion cars, in
          Ireland and anywhere else the numbers make sense.
        </p>
      </footer>
    </div>
  )
}
