/**
 * Realistic mock brain for building UI before the live API is ready.
 * Owner: Claude. Used by lib/brain-api.ts when NEXT_PUBLIC_BRAIN_API=mock.
 *
 * The data mirrors the DEMO_MODE seed: one student, three courses
 * (Econometrics, Probability & Statistics, Calculus II), ~40 items,
 * cross-course links, and a gap (weeks 6 and 7 missing in Econometrics).
 * `simulateHeroDemo()` plays the hero demo: three Telegram captures arrive
 * (slide photo, YouTube lecture, PDF), get filed into a new "Week 6" topic,
 * light up a new cross-course link, and resolve the Week 6 gap — leaving
 * "Week 7 is missing".
 *
 * Everything here is sample content. Nothing in this file is shown in live mode.
 */
import type {
  BrainChunk,
  BrainConcept,
  BrainCourse,
  BrainEvent,
  BrainGraph,
  BrainItem,
  BrainItemDetail,
  BrainLanguage,
  BrainOverview,
  BrainTopic,
  CaptureChannel,
  CaptureKind,
  CitedText,
  ConceptDetail,
  ConceptLink,
  CourseDetail,
  ExamPlanRequest,
  FilingAlternative,
  Flashcard,
  GapAlert,
  ItemPage,
  ItemStatus,
  LinkRelation,
  PlanDay,
  PlanNote,
  PlanTask,
  QuizAnswerResult,
  QuizOptionId,
  QuizQuestion,
  RefileRequest,
  RefileResult,
  SearchResponse,
  SequenceKind,
  SourceAnchor,
  SourceRef,
  StudyPlan,
  TelegramLinkCode,
  TelegramStatus,
  UUID,
} from './brain-types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Deterministic UUIDs so screenshots and tests are stable. */
export const mockId = (n: number): UUID => `00000000-0000-4000-8000-${n.toString().padStart(12, '0')}`

const BASE_TIME = Date.UTC(2026, 9, 21, 9, 0, 0)
const daysAgo = (days: number, hours = 0) => new Date(BASE_TIME - days * 86_400_000 - hours * 3_600_000).toISOString()
const nowIso = () => new Date().toISOString()
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T

function escapeXml(text: string) {
  return text.replace(/[<>&"']/g, (ch) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&apos;' })[ch] ?? ch)
}

/** A slide-like SVG thumbnail, so photo/page sources have something to show in mock mode. */
function slideThumb(title: string, lines: string[], blurry = false): string {
  const body = lines
    .slice(0, 4)
    .map((line, index) => `<text x="28" y="${104 + index * 30}" font-size="17" fill="#2b3a33">${escapeXml(line)}</text>`)
    .join('')
  const filter = blurry ? '<filter id="b"><feGaussianBlur stdDeviation="1.1"/></filter>' : ''
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="480" height="270" viewBox="0 0 480 270">${filter}<rect width="480" height="270" fill="#e9ece6"/><g ${blurry ? 'filter="url(#b)" transform="rotate(-2.5 240 135)"' : ''}><rect x="10" y="10" width="460" height="250" rx="4" fill="#fbfcfa" stroke="#c9d3cc"/><text x="28" y="62" font-size="24" font-weight="700" fill="#14231c">${escapeXml(title)}</text>${body}</g></svg>`
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}

const ytThumb = (id: string) => `https://i.ytimg.com/vi/${id}/hqdefault.jpg`
const ytOpen = (id: string, start = 0) => `https://www.youtube.com/watch?v=${id}${start ? `&t=${Math.floor(start)}s` : ''}`

let timeScale = 1
/** Tests can speed the choreography up (e.g. 0.01). */
export function setMockTimeScale(scale: number) { timeScale = Math.max(0, scale) }
const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms * timeScale))

// ---------------------------------------------------------------------------
// Seed definitions
// ---------------------------------------------------------------------------

interface CourseSeed { n: number; title: string; code: string; color: number; seqKind: SequenceKind; days: number }
interface TopicSeed { n: number; course: number; seq: number; title: string; days: number }
interface ConceptSeed { n: number; topic: number; name: string; summary: string; mentions: number }
interface ItemSeed {
  n: number
  topic: number | null
  course?: number
  kind: CaptureKind
  channel: CaptureChannel
  title: string
  summary: string
  days: number
  passages: Array<[SourceAnchor, string]>
  concepts: number[]
  youtube?: string
  url?: string
  duration?: number
  pages?: number
  confidence?: number
  alternatives?: FilingAlternative[]
  status?: ItemStatus
  failure?: BrainItem['failure_code']
  language?: BrainLanguage
}
interface LinkSeed { n: number; a: number; b: number; relation: LinkRelation; strength: number; rationale: string; days: number }

const COURSES: CourseSeed[] = [
  { n: 101, title: 'Econometrics', code: 'ECON 301', color: 0, seqKind: 'week', days: 48 },
  { n: 102, title: 'Probability & Statistics', code: 'MATH 251', color: 1, seqKind: 'lecture', days: 47 },
  { n: 103, title: 'Calculus II', code: 'MATH 162', color: 2, seqKind: 'week', days: 40 },
]

const TOPICS: TopicSeed[] = [
  { n: 201, course: 101, seq: 1, title: 'Simple linear regression', days: 48 },
  { n: 202, course: 101, seq: 2, title: 'OLS assumptions (Gauss–Markov)', days: 41 },
  { n: 203, course: 101, seq: 3, title: 'Multiple regression', days: 34 },
  { n: 204, course: 101, seq: 4, title: 'Hypothesis testing: t and F', days: 27 },
  { n: 205, course: 101, seq: 5, title: 'Dummy variables and interactions', days: 20 },
  { n: 208, course: 101, seq: 8, title: 'Autocorrelation', days: 2 },
  { n: 211, course: 102, seq: 1, title: 'Random variables', days: 47 },
  { n: 212, course: 102, seq: 2, title: 'Expectation and variance', days: 40 },
  { n: 213, course: 102, seq: 3, title: 'Common distributions', days: 33 },
  { n: 214, course: 102, seq: 4, title: 'Covariance and correlation', days: 26 },
  { n: 215, course: 102, seq: 5, title: 'Law of large numbers and the CLT', days: 19 },
  { n: 216, course: 102, seq: 6, title: 'Estimation and confidence intervals', days: 12 },
  { n: 221, course: 103, seq: 1, title: 'Integration by parts', days: 40 },
  { n: 222, course: 103, seq: 2, title: 'Improper integrals', days: 33 },
  { n: 223, course: 103, seq: 3, title: 'Sequences and series', days: 26 },
  { n: 224, course: 103, seq: 4, title: 'Taylor series', days: 19 },
]

const CONCEPTS: ConceptSeed[] = [
  { n: 301, topic: 201, name: 'Ordinary least squares', summary: 'OLS picks the line that minimizes the sum of squared residuals.', mentions: 9 },
  { n: 302, topic: 201, name: 'Slope = Cov(X,Y) / Var(X)', summary: 'In simple regression the OLS slope equals the sample covariance of X and Y divided by the variance of X.', mentions: 5 },
  { n: 303, topic: 201, name: 'Residuals', summary: 'A residual is the gap between an observed value and the fitted value from the regression line.', mentions: 6 },
  { n: 304, topic: 202, name: 'Gauss–Markov assumptions', summary: 'Linearity, random sampling, no perfect collinearity, zero conditional mean, and constant error variance.', mentions: 7 },
  { n: 305, topic: 202, name: 'Homoskedasticity', summary: 'The error term has the same variance for every value of the regressors: Var(u|X) = σ².', mentions: 5 },
  { n: 306, topic: 202, name: 'BLUE', summary: 'Under Gauss–Markov, OLS is the best linear unbiased estimator: lowest variance among linear unbiased estimators.', mentions: 4 },
  { n: 307, topic: 203, name: 'Omitted variable bias', summary: 'Leaving out a variable that is correlated with X and affects Y biases the OLS slope.', mentions: 5 },
  { n: 308, topic: 203, name: 'Partial effect', summary: 'A coefficient in multiple regression measures the effect of one regressor holding the others fixed.', mentions: 3 },
  { n: 309, topic: 204, name: 't-statistic', summary: 't = (estimate − hypothesized value) / standard error, compared with a t distribution.', mentions: 6 },
  { n: 310, topic: 204, name: 'F-test', summary: 'The F-test checks whether several coefficients are jointly zero by comparing restricted and unrestricted fits.', mentions: 4 },
  { n: 311, topic: 204, name: 'p-value', summary: 'The probability, under the null hypothesis, of a test statistic at least as extreme as the one observed.', mentions: 5 },
  { n: 312, topic: 205, name: 'Dummy variable trap', summary: 'Including a dummy for every category plus an intercept creates perfect collinearity.', mentions: 3 },
  { n: 313, topic: 205, name: 'Interaction term', summary: 'A product of two regressors lets the effect of one depend on the level of the other.', mentions: 3 },
  { n: 314, topic: 208, name: 'Autocorrelation', summary: 'Errors in different time periods are correlated, so usual OLS standard errors are wrong.', mentions: 4 },
  { n: 315, topic: 208, name: 'Durbin–Watson test', summary: 'A test for first-order autocorrelation in regression residuals; values near 2 suggest none.', mentions: 2 },
  { n: 321, topic: 211, name: 'Random variable', summary: 'A function that assigns a number to each outcome of a random experiment.', mentions: 5 },
  { n: 322, topic: 211, name: 'Probability mass function', summary: 'For a discrete random variable, the PMF gives P(X = x) for each value x.', mentions: 3 },
  { n: 323, topic: 212, name: 'Expected value', summary: 'The probability-weighted average of a random variable: E[X] = Σ x·P(X = x).', mentions: 8 },
  { n: 324, topic: 212, name: 'Variance', summary: 'How far a random variable spreads around its mean: Var(X) = E[(X − μ)²] = E[X²] − (E[X])².', mentions: 9 },
  { n: 325, topic: 212, name: 'Linearity of expectation', summary: 'E[aX + bY] = aE[X] + bE[Y], whether or not X and Y are independent.', mentions: 4 },
  { n: 326, topic: 213, name: 'Normal distribution', summary: 'The bell-shaped distribution fully described by its mean μ and variance σ².', mentions: 6 },
  { n: 327, topic: 213, name: 'Binomial distribution', summary: 'The number of successes in n independent trials with success probability p.', mentions: 3 },
  { n: 328, topic: 214, name: 'Covariance', summary: 'Cov(X,Y) = E[(X − μX)(Y − μY)] measures how two variables move together.', mentions: 6 },
  { n: 329, topic: 214, name: 'Correlation coefficient', summary: 'Covariance rescaled to lie between −1 and 1.', mentions: 4 },
  { n: 330, topic: 215, name: 'Law of large numbers', summary: 'The sample mean converges to the population mean as the sample grows.', mentions: 3 },
  { n: 331, topic: 215, name: 'Central limit theorem', summary: 'The standardized sample mean is approximately normal for large n, whatever the population shape.', mentions: 5 },
  { n: 332, topic: 216, name: 'Standard error', summary: 'The standard deviation of an estimator’s sampling distribution.', mentions: 5 },
  { n: 333, topic: 216, name: 'Confidence interval', summary: 'A range built so that it covers the true parameter in a stated share of repeated samples.', mentions: 4 },
  { n: 341, topic: 221, name: 'Integration by parts', summary: '∫u dv = uv − ∫v du, useful for products such as x·e^x.', mentions: 5 },
  { n: 342, topic: 222, name: 'Improper integral', summary: 'An integral over an infinite interval or with an unbounded integrand, defined as a limit.', mentions: 4 },
  { n: 343, topic: 222, name: 'Comparison test', summary: 'An improper integral converges if it is bounded by one that converges.', mentions: 2 },
  { n: 344, topic: 223, name: 'Geometric series', summary: 'Σ arⁿ converges to a/(1 − r) when |r| < 1.', mentions: 3 },
  { n: 345, topic: 223, name: 'Ratio test', summary: 'A series converges absolutely if the limit of |a(n+1)/a(n)| is below 1.', mentions: 3 },
  { n: 346, topic: 224, name: 'Taylor polynomial', summary: 'A polynomial that matches a function and its first n derivatives at a point.', mentions: 4 },
  { n: 347, topic: 224, name: 'Remainder term', summary: 'The error between a function and its Taylor polynomial, bounded by the next derivative.', mentions: 2 },
]

const ITEMS: ItemSeed[] = [
  // Econometrics
  { n: 401, topic: 201, kind: 'pdf', channel: 'web_drop', title: 'ECON301 Lecture 1 — Simple linear regression.pdf', summary: 'Lecture slides introducing the regression model, OLS, and fitted values.', days: 48, pages: 18,
    passages: [[{ kind: 'page', page: 6 }, 'The OLS estimates minimize the sum of squared residuals Σ(yᵢ − b₀ − b₁xᵢ)².'], [{ kind: 'page', page: 9 }, 'The slope estimate can be written as b₁ = Cov(x, y) / Var(x).']], concepts: [301, 302, 303] },
  { n: 402, topic: 201, kind: 'photo', channel: 'telegram', title: 'Whiteboard — deriving the OLS slope', summary: 'Photo of the board derivation of the slope from the first-order conditions.', days: 47,
    passages: [[{ kind: 'slide', slide: null }, 'Set ∂/∂b₁ Σ(yᵢ − b₀ − b₁xᵢ)² = 0 → b₁ = Σ(xᵢ − x̄)(yᵢ − ȳ) / Σ(xᵢ − x̄)².']], concepts: [302] },
  { n: 403, topic: 201, kind: 'youtube', channel: 'web_paste', title: 'Econometrics — Lecture 2: Simple Linear Regression (KeynesAcademy)', summary: 'Video walk-through of the simple regression model and interpretation of the slope.', days: 46, youtube: 'CBa8frhRKMw', duration: 887,
    passages: [[{ kind: 'timestamp', start_sec: 214, end_sec: 262 }, 'The slope tells us how much y changes on average when x goes up by one unit.'], [{ kind: 'timestamp', start_sec: 512, end_sec: 560 }, 'The residual is what is left over: the actual value minus the fitted value.']], concepts: [301, 303] },
  { n: 404, topic: 202, kind: 'pdf', channel: 'web_drop', title: 'Gauss–Markov handout.pdf', summary: 'Two-page handout listing the five Gauss–Markov assumptions.', days: 41, pages: 2,
    passages: [[{ kind: 'page', page: 1 }, 'MLR.5 Homoskedasticity: Var(u | x₁, …, xₖ) = σ². The error variance does not depend on the regressors.'], [{ kind: 'page', page: 2 }, 'Under MLR.1–MLR.5, OLS is BLUE: the best linear unbiased estimator.']], concepts: [304, 305, 306] },
  { n: 405, topic: 202, kind: 'text', channel: 'telegram', title: 'My notes: when is OLS BLUE?', summary: 'Short personal notes on which assumptions give unbiasedness versus efficiency.', days: 40,
    passages: [[{ kind: 'paragraph', paragraph: 1 }, 'Unbiased needs MLR.1–4. BLUE also needs homoskedasticity (MLR.5) — without it OLS is still unbiased but not the most efficient.']], concepts: [305, 306] },
  { n: 406, topic: 202, kind: 'youtube', channel: 'web_paste', title: 'Gauss-Markov assumptions part 1 (Ben Lambert)', summary: 'Short video explaining the first Gauss–Markov assumptions.', days: 39, youtube: 'NjTpHS5xLP8', duration: 322,
    passages: [[{ kind: 'timestamp', start_sec: 61, end_sec: 118 }, 'The first assumption is that the population process is linear in parameters.']], concepts: [304] },
  { n: 407, topic: 203, kind: 'photo', channel: 'telegram', title: 'Slide — omitted variable bias', summary: 'Photo of the slide with the omitted variable bias formula.', days: 34,
    passages: [[{ kind: 'slide', slide: 11 }, 'Bias(b̃₁) = β₂ · δ̃₁, where δ̃₁ is the slope from regressing x₂ on x₁.']], concepts: [307] },
  { n: 408, topic: 203, kind: 'pdf', channel: 'web_drop', title: 'ECON301 Lecture 3 — Multiple regression.pdf', summary: 'Slides on multiple regression, partial effects, and goodness of fit.', days: 33, pages: 22,
    passages: [[{ kind: 'page', page: 4 }, 'β₁ measures the effect of x₁ on y holding x₂ fixed — the ceteris paribus interpretation.'], [{ kind: 'page', page: 15 }, 'Omitting a relevant variable that is correlated with x₁ makes b₁ biased.']], concepts: [307, 308] },
  { n: 409, topic: 204, kind: 'youtube', channel: 'web_paste', title: 'Simple Linear Regression — t tests of parameters (Stats4Everyone)', summary: 'Video on testing whether a regression coefficient is zero.', days: 27, youtube: 'drnRNkmxn3E', duration: 813,
    passages: [[{ kind: 'timestamp', start_sec: 302, end_sec: 371 }, 'The test statistic is the estimate divided by its standard error, and we compare it to a t distribution with n − 2 degrees of freedom.']], concepts: [309, 311] },
  { n: 410, topic: 204, kind: 'pdf', channel: 'web_drop', title: 'Problem set 2.pdf', summary: 'Problem set on t-tests, F-tests, and p-values.', days: 25, pages: 5,
    passages: [[{ kind: 'page', page: 3 }, 'Q4. Test H₀: β₂ = β₃ = 0 using the F statistic from the restricted and unrestricted R².']], concepts: [310] },
  { n: 411, topic: 204, kind: 'audio', channel: 'telegram', title: 'Voice note — F-test intuition', summary: 'A 50-second voice note recapping why the F-test compares two fits.', days: 24, duration: 52,
    passages: [[{ kind: 'timestamp', start_sec: 8, end_sec: 31 }, 'So the F test asks: if I force these coefficients to zero, how much worse does the fit get?']], concepts: [310] },
  { n: 412, topic: 205, kind: 'photo', channel: 'telegram', title: 'Slide — the dummy variable trap', summary: 'Photo of the slide warning about including all category dummies.', days: 20,
    passages: [[{ kind: 'slide', slide: 6 }, 'With an intercept, include g − 1 dummies for g groups. Including all g creates perfect collinearity.']], concepts: [312] },
  { n: 413, topic: 205, kind: 'web', channel: 'web_paste', title: 'Interaction terms in regression — explained', summary: 'Article on interpreting interaction terms.', days: 19, url: 'https://en.wikipedia.org/wiki/Interaction_(statistics)',
    passages: [[{ kind: 'section', heading: 'In regression' }, 'An interaction term lets the effect of one variable on the outcome depend on the value of another variable.']], concepts: [313] },
  { n: 414, topic: 208, kind: 'pdf', channel: 'web_drop', title: 'ECON301 Lecture 8 — Time series and autocorrelation.pdf', summary: 'Slides on serial correlation and the Durbin–Watson test.', days: 2, pages: 16,
    passages: [[{ kind: 'page', page: 7 }, 'With AR(1) errors, uₜ = ρuₜ₋₁ + eₜ, OLS remains unbiased but the usual standard errors are invalid.'], [{ kind: 'page', page: 11 }, 'Durbin–Watson d ≈ 2(1 − ρ̂). Values near 2 indicate no first-order autocorrelation.']], concepts: [314, 315] },
  { n: 415, topic: 208, kind: 'youtube', channel: 'telegram', title: 'Autocorrelation — an introduction (Ben Lambert)', summary: 'Video introducing autocorrelated errors in time series.', days: 1, youtube: 'jt5nl2VEpwg', duration: 399,
    passages: [[{ kind: 'timestamp', start_sec: 95, end_sec: 152 }, 'Autocorrelation means that the error in this period is correlated with the error in the previous period.']], concepts: [314] },
  // Probability & Statistics
  { n: 416, topic: 211, kind: 'pdf', channel: 'web_drop', title: 'MATH251 Lecture 1 — Random variables.pdf', summary: 'Lecture notes defining random variables and probability mass functions.', days: 47, pages: 12,
    passages: [[{ kind: 'page', page: 2 }, 'A random variable is a function X: Ω → ℝ assigning a number to every outcome.'], [{ kind: 'page', page: 5 }, 'The PMF p(x) = P(X = x) satisfies p(x) ≥ 0 and Σ p(x) = 1.']], concepts: [321, 322] },
  { n: 417, topic: 211, kind: 'photo', channel: 'telegram', title: 'Notebook — dice example', summary: 'Photo of handwritten notes on the PMF of the sum of two dice.', days: 46,
    passages: [[{ kind: 'slide', slide: null }, 'X = sum of two dice. P(X = 7) = 6/36, the most likely value.']], concepts: [322] },
  { n: 418, topic: 212, kind: 'youtube', channel: 'web_paste', title: 'Expected Value and Variance of Discrete Random Variables (jbstatistics)', summary: 'Video deriving expectation and variance for discrete random variables.', days: 40, youtube: 'OvTEhNL96v0', duration: 477,
    passages: [[{ kind: 'timestamp', start_sec: 118, end_sec: 175 }, 'The expected value is a weighted average of the possible values, weighted by their probabilities.'], [{ kind: 'timestamp', start_sec: 262, end_sec: 330 }, 'The variance is the expected squared distance from the mean, and a shortcut is E of X squared minus the mean squared.']], concepts: [323, 324] },
  { n: 419, topic: 212, kind: 'pdf', channel: 'web_drop', title: 'MATH251 Lecture 2 — Expectation and variance.pdf', summary: 'Lecture notes on expectation, variance, and their properties.', days: 39, pages: 14,
    passages: [[{ kind: 'page', page: 3 }, 'E[aX + b] = aE[X] + b, and more generally expectation is linear.'], [{ kind: 'page', page: 8 }, 'Var(X) = E[(X − μ)²] = E[X²] − μ². Var(aX + b) = a²Var(X).']], concepts: [323, 324, 325] },
  { n: 420, topic: 212, kind: 'photo', channel: 'telegram', title: 'Whiteboard — Var(X) = E[X²] − (E[X])²', summary: 'Photo of the board proof of the variance shortcut.', days: 38,
    passages: [[{ kind: 'slide', slide: null }, 'Var(X) = E[X² − 2μX + μ²] = E[X²] − 2μ² + μ² = E[X²] − μ².']], concepts: [324] },
  { n: 421, topic: 213, kind: 'pdf', channel: 'web_drop', title: 'MATH251 Lecture 3 — Common distributions.pdf', summary: 'Notes on Bernoulli, binomial, Poisson, and normal distributions.', days: 33, pages: 20,
    passages: [[{ kind: 'page', page: 6 }, 'X ~ Bin(n, p) has E[X] = np and Var(X) = np(1 − p).'], [{ kind: 'page', page: 14 }, 'The normal density f(x) = (1/σ√(2π)) exp(−(x − μ)²/2σ²) integrates to 1 over the real line.']], concepts: [326, 327] },
  { n: 422, topic: 213, kind: 'web', channel: 'web_paste', title: 'Normal distribution — Wikipedia', summary: 'Encyclopedia article on the normal distribution.', days: 32, url: 'https://en.wikipedia.org/wiki/Normal_distribution',
    passages: [[{ kind: 'section', heading: 'Standard normal distribution' }, 'The simplest case of a normal distribution is the standard normal distribution, with mean 0 and variance 1.']], concepts: [326] },
  { n: 423, topic: 214, kind: 'pdf', channel: 'web_drop', title: 'MATH251 Lecture 4 — Covariance and correlation.pdf', summary: 'Notes on covariance, correlation, and the variance of sums.', days: 26, pages: 11,
    passages: [[{ kind: 'page', page: 2 }, 'Cov(X, Y) = E[XY] − E[X]E[Y]. Independent variables have zero covariance.'], [{ kind: 'page', page: 6 }, 'Var(X + Y) = Var(X) + Var(Y) + 2Cov(X, Y).']], concepts: [328, 329] },
  { n: 424, topic: 214, kind: 'text', channel: 'web_paste', title: 'Pasted: correlation is not causation', summary: 'Pasted paragraph from the seminar reading on correlation.', days: 25,
    passages: [[{ kind: 'paragraph', paragraph: 1 }, 'ρ = Cov(X, Y) / (σX σY) always lies in [−1, 1]; ρ = ±1 only for an exact linear relationship.']], concepts: [329] },
  { n: 425, topic: 215, kind: 'youtube', channel: 'web_paste', title: 'The Central Limit Theorem, Clearly Explained (StatQuest)', summary: 'Video showing why sample means become normal.', days: 19, youtube: 'YAlJCEDH2uY', duration: 455,
    passages: [[{ kind: 'timestamp', start_sec: 141, end_sec: 205 }, 'Even when the data come from a uniform distribution, the means of many samples are normally distributed.']], concepts: [331] },
  { n: 426, topic: 215, kind: 'audio', channel: 'telegram', title: 'Voice note — LLN vs CLT', summary: 'A voice note distinguishing the law of large numbers from the CLT.', days: 18, duration: 71,
    passages: [[{ kind: 'timestamp', start_sec: 4, end_sec: 39 }, 'LLN says the average settles down to mu. CLT says how it wiggles around mu — normally, with spread sigma over root n.']], concepts: [330, 331] },
  { n: 427, topic: 216, kind: 'pdf', channel: 'web_drop', title: 'MATH251 Lecture 6 — Estimation.pdf', summary: 'Notes on estimators, standard errors, and confidence intervals.', days: 12, pages: 15,
    passages: [[{ kind: 'page', page: 4 }, 'The standard error of the sample mean is σ/√n, estimated by s/√n.'], [{ kind: 'page', page: 9 }, 'A 95% confidence interval for μ is x̄ ± 1.96·s/√n for large n.']], concepts: [332, 333] },
  { n: 428, topic: 216, kind: 'photo', channel: 'telegram', title: 'Slide — interpreting a confidence interval', summary: 'Photo of a slide on the meaning of 95% confidence.', days: 11,
    passages: [[{ kind: 'slide', slide: 14 }, '95% of intervals built this way would contain μ — not “μ is in this interval with probability 0.95”.']], concepts: [333] },
  // Calculus II
  { n: 429, topic: 221, kind: 'photo', channel: 'telegram', title: 'Slide — integration by parts formula', summary: 'Photo of the slide stating the integration by parts formula.', days: 40,
    passages: [[{ kind: 'slide', slide: 3 }, '∫u dv = uv − ∫v du. Choose u by LIATE: logs, inverse trig, algebraic, trig, exponential.']], concepts: [341] },
  { n: 430, topic: 221, kind: 'youtube', channel: 'web_paste', title: 'Integration By Parts (The Organic Chemistry Tutor)', summary: 'Worked examples of integration by parts.', days: 39, youtube: 'sWSLLO3DS1I', duration: 1972,
    passages: [[{ kind: 'timestamp', start_sec: 95, end_sec: 160 }, 'For x times e to the x, let u be x and dv be e to the x dx.']], concepts: [341] },
  { n: 431, topic: 222, kind: 'pdf', channel: 'web_drop', title: 'MATH162 Week 2 — Improper integrals.pdf', summary: 'Notes on improper integrals and comparison tests.', days: 33, pages: 9,
    passages: [[{ kind: 'page', page: 2 }, '∫₁^∞ 1/xᵖ dx converges if and only if p > 1.'], [{ kind: 'page', page: 6 }, 'If 0 ≤ f ≤ g and ∫g converges, then ∫f converges.']], concepts: [342, 343] },
  { n: 432, topic: 223, kind: 'pdf', channel: 'web_drop', title: 'MATH162 Week 3 — Series.pdf', summary: 'Notes on geometric series and convergence tests.', days: 26, pages: 13,
    passages: [[{ kind: 'page', page: 3 }, 'Σ_{n≥0} arⁿ = a/(1 − r) for |r| < 1, and diverges otherwise.'], [{ kind: 'page', page: 9 }, 'Ratio test: L = lim |a(n+1)/a(n)|. L < 1 converges absolutely, L > 1 diverges.']], concepts: [344, 345] },
  { n: 433, topic: 223, kind: 'web', channel: 'web_paste', title: 'Ratio test — Paul’s Online Notes', summary: 'Web notes on the ratio test with examples.', days: 25, url: 'https://tutorial.math.lamar.edu/Classes/CalcII/RatioTest.aspx',
    passages: [[{ kind: 'section', heading: 'Ratio Test' }, 'If L = 1 the ratio test is inconclusive and another test is needed.']], concepts: [345] },
  { n: 434, topic: 224, kind: 'youtube', channel: 'web_paste', title: 'Taylor series | Essence of calculus (3Blue1Brown)', summary: 'Visual introduction to Taylor polynomials.', days: 19, youtube: '3d6DsjIBzJ4', duration: 1340,
    passages: [[{ kind: 'timestamp', start_sec: 380, end_sec: 455 }, 'Each new term lets the polynomial match one more derivative of the function at that point.']], concepts: [346] },
  { n: 435, topic: 224, kind: 'photo', channel: 'telegram', title: 'Whiteboard — Taylor remainder bound', summary: 'Photo of the board with the Lagrange remainder bound.', days: 18,
    passages: [[{ kind: 'slide', slide: null }, '|Rₙ(x)| ≤ M|x − a|ⁿ⁺¹ / (n + 1)!, where |f⁽ⁿ⁺¹⁾| ≤ M between a and x.']], concepts: [347] },
  // Edge states the UI must handle
  { n: 436, topic: 222, kind: 'photo', channel: 'telegram', title: 'Photo — handwritten notes', summary: 'Blurry photo of handwritten notes about limits of integrals.', days: 3,
    passages: [[{ kind: 'slide', slide: null }, 'lim b→∞ ∫₀ᵇ e^(−x) dx = 1']], concepts: [342], confidence: 0.48,
    alternatives: [
      { course_id: mockId(102), course_title: 'Probability & Statistics', topic_id: mockId(213), topic_title: 'Common distributions', confidence: 0.36 },
      { course_id: mockId(103), course_title: 'Calculus II', topic_id: mockId(221), topic_title: 'Integration by parts', confidence: 0.11 },
    ] },
  { n: 437, topic: null, kind: 'web', channel: 'web_paste', title: 'drive.google.com/file/d/…', summary: '', days: 1, url: 'https://drive.google.com/file/d/private-example', passages: [], concepts: [], status: 'failed', failure: 'fetch_failed' },
  { n: 438, topic: 216, kind: 'text', channel: 'telegram', title: 'Сообщение: доверительный интервал', summary: 'Заметка на русском о ширине доверительного интервала.', days: 0.5, language: 'ru-RU',
    passages: [[{ kind: 'paragraph', paragraph: 1 }, 'Чем больше выборка n, тем уже доверительный интервал: ширина пропорциональна 1/√n.']], concepts: [333] },
]

const LINKS: LinkSeed[] = [
  { n: 601, a: 302, b: 328, relation: 'builds_on', strength: 0.91, rationale: 'The OLS slope is the covariance of X and Y scaled by the variance of X.', days: 26 },
  { n: 602, a: 302, b: 324, relation: 'builds_on', strength: 0.84, rationale: 'The denominator of the OLS slope is the variance of X.', days: 39 },
  { n: 603, a: 309, b: 332, relation: 'builds_on', strength: 0.86, rationale: 'The t-statistic divides an estimate by its standard error.', days: 12 },
  { n: 604, a: 311, b: 326, relation: 'applies', strength: 0.72, rationale: 'Large-sample p-values come from the normal distribution.', days: 27 },
  { n: 605, a: 326, b: 342, relation: 'applies', strength: 0.77, rationale: 'The normal density integrates to 1 over an infinite interval — an improper integral.', days: 33 },
  { n: 606, a: 323, b: 341, relation: 'applies', strength: 0.7, rationale: 'Expected values of continuous variables such as the exponential are computed with integration by parts.', days: 39 },
  { n: 607, a: 331, b: 309, relation: 'builds_on', strength: 0.74, rationale: 'The CLT justifies using t and normal critical values for regression coefficients.', days: 19 },
  { n: 608, a: 305, b: 304, relation: 'builds_on', strength: 0.88, rationale: 'Homoskedasticity is the fifth Gauss–Markov assumption.', days: 41 },
  { n: 609, a: 306, b: 305, relation: 'builds_on', strength: 0.82, rationale: 'OLS is BLUE only when errors are homoskedastic.', days: 40 },
  { n: 610, a: 324, b: 323, relation: 'builds_on', strength: 0.9, rationale: 'Variance is defined as an expected value of squared deviations.', days: 40 },
  { n: 611, a: 328, b: 324, relation: 'builds_on', strength: 0.83, rationale: 'Variance is the covariance of a variable with itself.', days: 26 },
  { n: 612, a: 333, b: 332, relation: 'builds_on', strength: 0.87, rationale: 'A confidence interval is the estimate plus or minus a multiple of its standard error.', days: 12 },
  { n: 613, a: 314, b: 305, relation: 'contrasts', strength: 0.68, rationale: 'Both break the Gauss–Markov error assumptions, one across observations and one in variance.', days: 2 },
  { n: 614, a: 346, b: 331, relation: 'applies', strength: 0.66, rationale: 'Taylor expansions are used in the delta method built on the CLT.', days: 19 },
]

// ---------------------------------------------------------------------------
// Hero demo: what the three Telegram captures turn into
// ---------------------------------------------------------------------------

const HERO_TOPIC: TopicSeed = { n: 206, course: 101, seq: 6, title: 'Heteroskedasticity', days: 0 }
const HERO_CONCEPTS: ConceptSeed[] = [
  { n: 351, topic: 206, name: 'Heteroskedasticity', summary: 'The error variance changes with the regressors: Var(u|X) = σ²(X) instead of a constant σ².', mentions: 3 },
  { n: 352, topic: 206, name: 'Robust standard errors', summary: 'White (heteroskedasticity-robust) standard errors stay valid when the error variance is not constant.', mentions: 2 },
  { n: 353, topic: 206, name: 'Breusch–Pagan test', summary: 'Regress squared residuals on the regressors; a significant fit signals heteroskedasticity.', mentions: 1 },
  { n: 354, topic: 206, name: 'White test', summary: 'A test for heteroskedasticity using squares and cross-products of the regressors.', mentions: 1 },
  { n: 355, topic: 206, name: 'Weighted least squares', summary: 'Re-weights observations by the inverse of their error variance to restore efficiency.', mentions: 1 },
]
const HERO_YOUTUBE = '2xcUup_-K6c'
const HERO_ITEMS: ItemSeed[] = [
  { n: 441, topic: 206, kind: 'photo', channel: 'telegram', title: 'Slide 7 — Heteroskedasticity', summary: 'Blurry photo of the Week 6 slide defining heteroskedasticity and its consequences for OLS.', days: 0,
    passages: [[{ kind: 'slide', slide: 7 }, 'Heteroskedasticity: Var(uᵢ | xᵢ) = σᵢ². OLS is still unbiased, but the usual standard errors are wrong, so t and F tests are invalid.']], concepts: [351, 352], confidence: 0.94 },
  { n: 442, topic: 206, kind: 'youtube', channel: 'telegram', title: 'What is Heteroskedasticity? (zedstatistics)', summary: 'A 28-minute lecture on detecting and fixing heteroskedasticity.', days: 0, youtube: HERO_YOUTUBE, duration: 1680,
    passages: [
      [{ kind: 'timestamp', start_sec: 245, end_sec: 301 }, 'Heteroskedasticity just means the variance of the error term is not constant — it fans out as x gets bigger.'],
      [{ kind: 'timestamp', start_sec: 872, end_sec: 910 }, 'The coefficients themselves are still unbiased. What goes wrong is the standard errors, so your t statistics and p-values can’t be trusted.'],
      [{ kind: 'timestamp', start_sec: 1190, end_sec: 1244 }, 'For the Breusch–Pagan test, you regress the squared residuals on your x variables and look at how much they explain.'],
    ], concepts: [351, 352, 353], confidence: 0.91 },
  { n: 443, topic: 206, kind: 'pdf', channel: 'telegram', title: 'ECON301 Week 6 — Heteroskedasticity.pdf', summary: 'Six pages of notes on tests for heteroskedasticity and weighted least squares.', days: 0, pages: 6,
    passages: [
      [{ kind: 'page', page: 2 }, 'Consequence: Var(b₁) ≠ σ²/SSTₓ, so the usual OLS standard errors are biased.'],
      [{ kind: 'page', page: 4 }, 'White test: regress û² on xⱼ, xⱼ², and xⱼxₖ; compare n·R² with a χ² distribution.'],
      [{ kind: 'page', page: 5 }, 'If Var(u|x) = σ²h(x), weighted least squares with weights 1/h(x) is BLUE.'],
    ], concepts: [354, 355, 352], confidence: 0.96 },
]
const HERO_LINKS: Array<LinkSeed & { after: number }> = [
  { n: 651, a: 351, b: 324, relation: 'builds_on', strength: 0.89, rationale: 'Heteroskedasticity is about the conditional variance of the error — the same Var(·) from Lecture 2.', days: 0, after: 441 },
  { n: 652, a: 351, b: 305, relation: 'contrasts', strength: 0.93, rationale: 'Heteroskedasticity is exactly the failure of the homoskedasticity assumption.', days: 0, after: 441 },
  { n: 653, a: 352, b: 332, relation: 'builds_on', strength: 0.82, rationale: 'Robust standard errors replace the usual standard error formula when variance is not constant.', days: 0, after: 442 },
  { n: 654, a: 354, b: 353, relation: 'same_idea', strength: 0.76, rationale: 'Both tests regress squared residuals on functions of the regressors.', days: 0, after: 443 },
]

// ---------------------------------------------------------------------------
// The mock brain
// ---------------------------------------------------------------------------

type Listener = (event: BrainEvent) => void

interface ChunkRow extends BrainChunk { concept_ids: UUID[] }
interface PlanSecret { correct: QuizOptionId; explanation: CitedText; moment: SourceRef | null; reason: string }

export class MockBrain {
  courses = new Map<UUID, BrainCourse>()
  topics = new Map<UUID, BrainTopic>()
  concepts = new Map<UUID, BrainConcept>()
  items = new Map<UUID, BrainItem>()
  chunks = new Map<UUID, ChunkRow>()
  links = new Map<UUID, ConceptLink>()
  plans = new Map<UUID, StudyPlan>()
  private answers = new Map<string, PlanSecret>()
  private listeners = new Set<Listener>()
  private eventCounter = 0
  private dynamicCounter = 9000
  private heroPlayed = false
  telegram: TelegramStatus = { bot_configured: true, bot_username: 'FibonacciBrainBot', linked: false, telegram_username: null, linked_at: null }

  constructor() {
    COURSES.forEach((c) => this.addCourse(c))
    TOPICS.forEach((t) => this.addTopic(t))
    CONCEPTS.forEach((c) => this.addConcept(c))
    ITEMS.forEach((i) => this.addItem(i))
    LINKS.forEach((l) => this.addLink(l))
    this.recount()
  }

  // ---- seed builders ------------------------------------------------------

  private addCourse(seed: CourseSeed) {
    this.courses.set(mockId(seed.n), {
      id: mockId(seed.n), title: seed.title, code: seed.code, color_index: seed.color, created_by: 'auto',
      item_count: 0, topic_count: 0, concept_count: 0, created_at: daysAgo(seed.days),
    })
  }

  private addTopic(seed: TopicSeed) {
    const course = COURSES.find((c) => c.n === seed.course)
    this.topics.set(mockId(seed.n), {
      id: mockId(seed.n), course_id: mockId(seed.course), title: seed.title, sequence: seed.seq,
      sequence_kind: course?.seqKind ?? 'week', item_count: 0, concept_count: 0,
      created_at: seed.days === 0 ? nowIso() : daysAgo(seed.days),
    })
  }

  private addConcept(seed: ConceptSeed) {
    const topic = this.topics.get(mockId(seed.topic))
    if (!topic) return
    this.concepts.set(mockId(seed.n), {
      id: mockId(seed.n), course_id: topic.course_id, topic_id: topic.id, name: seed.name, summary: seed.summary,
      mention_count: seed.mentions, created_at: seed.n >= 351 ? nowIso() : topic.created_at,
    })
  }

  private addItem(seed: ItemSeed, overrides: Partial<BrainItem> = {}) {
    const topic = seed.topic ? this.topics.get(mockId(seed.topic)) : undefined
    const course = topic ? this.courses.get(topic.course_id) : seed.course ? this.courses.get(mockId(seed.course)) : undefined
    const id = mockId(seed.n)
    const lines = seed.passages.map(([, text]) => text)
    const thumb =
      seed.kind === 'youtube' && seed.youtube ? ytThumb(seed.youtube)
      : seed.kind === 'photo' ? slideThumb(seed.title.replace(/^(Slide|Whiteboard|Photo|Notebook)\s*(\d+)?\s*—\s*/, ''), lines.map((l) => l.slice(0, 46)), true)
      : seed.kind === 'pdf' ? slideThumb(seed.title.replace(/\.pdf$/, '').slice(0, 34), lines.map((l) => l.slice(0, 46)))
      : null
    const status = seed.status ?? 'filed'
    const item: BrainItem = {
      id, kind: seed.kind, channel: seed.channel, status, progress: status === 'filed' ? 1 : status === 'failed' ? 0.2 : 0,
      title: seed.title, summary: seed.summary || null, language: seed.language ?? 'en-US',
      course_id: course?.id ?? null, course_title: course?.title ?? null, topic_id: topic?.id ?? null, topic_title: topic?.title ?? null,
      confidence: status === 'filed' ? seed.confidence ?? 0.9 : null,
      needs_review: status === 'filed' && (seed.confidence ?? 0.9) < 0.6,
      alternatives: seed.alternatives ?? [],
      concept_ids: seed.concepts.map(mockId),
      source_url: seed.youtube ? ytOpen(seed.youtube) : seed.url ?? null,
      youtube_id: seed.youtube ?? null,
      thumbnail_url: thumb,
      media_url: seed.kind === 'photo' ? thumb : null, // mock: no real PDF/audio files
      duration_sec: seed.duration ?? null, page_count: seed.pages ?? null,
      failure_code: seed.failure ?? null,
      captured_at: seed.days === 0 ? nowIso() : daysAgo(seed.days),
      filed_at: status === 'filed' ? (seed.days === 0 ? nowIso() : daysAgo(seed.days, -0.01)) : null,
      timings_ms: status === 'filed' ? { extract: 1800, classify: 1400, link: 900, total: 4100 } : {},
      ...overrides,
    }
    this.items.set(id, item)
    seed.passages.forEach(([anchor, text], index) => {
      const chunkId = mockId(seed.n * 10 + index + 50_000)
      this.chunks.set(chunkId, { id: chunkId, item_id: id, ordinal: index, anchor, text, concept_ids: seed.concepts.map(mockId) })
    })
    return item
  }

  private addLink(seed: LinkSeed): ConceptLink | null {
    const a = this.concepts.get(mockId(seed.a))
    const b = this.concepts.get(mockId(seed.b))
    if (!a || !b) return null
    const link: ConceptLink = {
      id: mockId(seed.n), source_concept_id: a.id, target_concept_id: b.id, cross_course: a.course_id !== b.course_id,
      strength: seed.strength, relation: seed.relation, rationale: seed.rationale, method: 'verified',
      created_at: seed.days === 0 ? nowIso() : daysAgo(seed.days),
    }
    this.links.set(link.id, link)
    return link
  }

  private recount() {
    for (const course of this.courses.values()) {
      course.item_count = [...this.items.values()].filter((i) => i.course_id === course.id && i.status === 'filed').length
      course.topic_count = [...this.topics.values()].filter((t) => t.course_id === course.id).length
      course.concept_count = [...this.concepts.values()].filter((c) => c.course_id === course.id).length
    }
    for (const topic of this.topics.values()) {
      topic.item_count = [...this.items.values()].filter((i) => i.topic_id === topic.id && i.status === 'filed').length
      topic.concept_count = [...this.concepts.values()].filter((c) => c.topic_id === topic.id).length
    }
  }

  // ---- events -------------------------------------------------------------

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener)
    return () => { this.listeners.delete(listener) }
  }

  // Distributive omit keeps each event variant intact.
  private emit(event: BrainEvent extends infer E ? (E extends BrainEvent ? Omit<E, 'id' | 'at'> : never) : never) {
    this.eventCounter += 1
    const full = { ...event, id: String(this.eventCounter), at: nowIso() } as BrainEvent
    this.listeners.forEach((listener) => listener(clone(full)))
  }

  // ---- reads ----------------------------------------------------------------

  private sortedItems() {
    return [...this.items.values()].sort((a, b) => b.captured_at.localeCompare(a.captured_at))
  }

  sourceRef(chunkId: UUID): SourceRef | null {
    const chunk = this.chunks.get(chunkId)
    const item = chunk ? this.items.get(chunk.item_id) : undefined
    if (!chunk || !item) return null
    const start = chunk.anchor.kind === 'timestamp' ? chunk.anchor.start_sec : 0
    return {
      item_id: item.id, chunk_id: chunk.id, item_kind: item.kind, item_title: item.title, course_id: item.course_id,
      anchor: chunk.anchor, quote: chunk.text.slice(0, 280), captured_at: item.captured_at,
      thumbnail_url: item.thumbnail_url,
      open_url: item.youtube_id ? ytOpen(item.youtube_id, start) : item.kind === 'web' ? item.source_url : null,
      youtube_id: item.youtube_id, media_url: item.media_url,
    }
  }

  /** Chunk ids of an item in order. */
  private chunkIds(itemN: number): UUID[] {
    return [...this.chunks.values()].filter((c) => c.item_id === mockId(itemN)).sort((a, b) => a.ordinal - b.ordinal).map((c) => c.id)
  }

  private refs(...pairs: Array<[number, number]>): SourceRef[] {
    return pairs
      .map(([itemN, index]) => this.chunkIds(itemN)[index])
      .filter((id): id is UUID => Boolean(id))
      .map((id) => this.sourceRef(id))
      .filter((ref): ref is SourceRef => Boolean(ref))
  }

  gaps(courseId?: UUID): GapAlert[] {
    const result: GapAlert[] = []
    for (const course of this.courses.values()) {
      if (courseId && course.id !== courseId) continue
      const topics = [...this.topics.values()].filter((t) => t.course_id === course.id && t.sequence !== null && t.item_count > 0)
      const present = [...new Set(topics.map((t) => t.sequence as number))].sort((a, b) => a - b)
      if (present.length < 2) continue
      const kind = topics[0]?.sequence_kind ?? 'week'
      for (let n = present[0]; n <= present[present.length - 1]; n += 1) {
        if (!present.includes(n)) {
          result.push({ id: `${course.id}:${kind}:${n}`, course_id: course.id, course_title: course.title, sequence_kind: kind, missing: n, present })
        }
      }
    }
    return result
  }

  async overview(): Promise<BrainOverview> {
    const items = this.sortedItems()
    return clone({
      counts: {
        items: items.filter((i) => i.status === 'filed').length,
        courses: this.courses.size,
        concepts: this.concepts.size,
        cross_links: [...this.links.values()].filter((l) => l.cross_course).length,
        processing: items.filter((i) => !['filed', 'failed'].includes(i.status)).length,
      },
      recent_items: items.slice(0, 20),
      gaps: this.gaps(),
      telegram: this.telegram,
      demo_mode: true,
    })
  }

  async graph(): Promise<BrainGraph> {
    return clone({
      courses: [...this.courses.values()], topics: [...this.topics.values()], concepts: [...this.concepts.values()],
      links: [...this.links.values()], generated_at: nowIso(),
    })
  }

  async listItems(params: { status?: ItemStatus; course_id?: UUID; limit?: number; cursor?: string } = {}): Promise<ItemPage> {
    const all = this.sortedItems().filter((i) => (!params.status || i.status === params.status) && (!params.course_id || i.course_id === params.course_id))
    const offset = params.cursor ? Number(params.cursor) : 0
    const limit = params.limit ?? 25
    const page = all.slice(offset, offset + limit)
    return clone({ items: page, next_cursor: offset + limit < all.length ? String(offset + limit) : null })
  }

  async item(id: UUID): Promise<BrainItemDetail> {
    const item = this.items.get(id)
    if (!item) throw new MockNotFound()
    const chunks = [...this.chunks.values()].filter((c) => c.item_id === id).sort((a, b) => a.ordinal - b.ordinal)
      .map(({ concept_ids: _ignored, ...chunk }) => chunk)
    return clone({ item, chunks, concepts: item.concept_ids.map((c) => this.concepts.get(c)).filter(Boolean) as BrainConcept[] })
  }

  async concept(id: UUID): Promise<ConceptDetail> {
    const concept = this.concepts.get(id)
    if (!concept) throw new MockNotFound()
    const course = this.courses.get(concept.course_id) as BrainCourse
    const topic = concept.topic_id ? this.topics.get(concept.topic_id) ?? null : null
    const sources = [...this.chunks.values()].filter((c) => c.concept_ids.includes(id)).map((c) => this.sourceRef(c.id)).filter(Boolean) as SourceRef[]
    const linked = [...this.links.values()]
      .filter((l) => l.source_concept_id === id || l.target_concept_id === id)
      .map((link) => {
        const other = this.concepts.get(link.source_concept_id === id ? link.target_concept_id : link.source_concept_id) as BrainConcept
        return { link, concept: other, course: this.courses.get(other.course_id) as BrainCourse }
      })
      .sort((a, b) => Number(b.link.cross_course) - Number(a.link.cross_course) || b.link.strength - a.link.strength)
    return clone({ concept, course, topic, sources, linked })
  }

  async course(id: UUID): Promise<CourseDetail> {
    const course = this.courses.get(id)
    if (!course) throw new MockNotFound()
    const topics = [...this.topics.values()].filter((t) => t.course_id === id)
      .sort((a, b) => (a.sequence ?? 999) - (b.sequence ?? 999) || a.created_at.localeCompare(b.created_at))
      .map((topic) => ({ topic, items: this.sortedItems().filter((i) => i.topic_id === topic.id) }))
    const loose = this.sortedItems().filter((i) => i.course_id === id && !i.topic_id)
    return clone({ course, topics, loose_items: loose, gaps: this.gaps(id) })
  }

  async renameCourse(id: UUID, title: string): Promise<BrainCourse> {
    const course = this.courses.get(id)
    if (!course) throw new MockNotFound()
    course.title = title.trim().slice(0, 120)
    course.created_by = 'user'
    for (const item of this.items.values()) if (item.course_id === id) item.course_title = course.title
    return clone(course)
  }

  async search(query: string, limit = 20): Promise<SearchResponse> {
    const q = query.trim().toLowerCase()
    if (!q) return { query, hits: [] }
    const conceptHits = [...this.concepts.values()]
      .filter((c) => c.name.toLowerCase().includes(q) || c.summary.toLowerCase().includes(q))
      .map((concept) => ({ kind: 'concept' as const, score: concept.name.toLowerCase().includes(q) ? 0.95 : 0.7, concept }))
    const passageHits = [...this.chunks.values()]
      .filter((c) => c.text.toLowerCase().includes(q))
      .map((c) => ({ kind: 'passage' as const, score: 0.6, source: this.sourceRef(c.id) as SourceRef }))
    return clone({ query, hits: [...conceptHits, ...passageHits].sort((a, b) => b.score - a.score).slice(0, limit) })
  }

  // ---- writes ---------------------------------------------------------------

  async deleteItem(id: UUID): Promise<void> {
    if (!this.items.delete(id)) throw new MockNotFound()
    for (const [chunkId, chunk] of this.chunks) if (chunk.item_id === id) this.chunks.delete(chunkId)
    this.recount()
    this.emit({ type: 'item.deleted', item_id: id })
  }

  async retryItem(id: UUID): Promise<BrainItem> {
    const item = this.items.get(id)
    if (!item) throw new MockNotFound()
    item.status = 'queued'
    item.failure_code = null
    item.progress = 0
    void this.playGeneric(item, `${item.title} ${item.source_url ?? ''}`)
    return clone(item)
  }

  async refile(id: UUID, request: RefileRequest): Promise<RefileResult> {
    const item = this.items.get(id)
    if (!item) throw new MockNotFound()
    let course = request.course_id ? this.courses.get(request.course_id) : undefined
    if (!course && request.new_course_title) {
      const n = this.nextN()
      this.addCourse({ n, title: request.new_course_title.trim().slice(0, 120), code: '', color: this.courses.size % 8, seqKind: 'week', days: 0 })
      course = this.courses.get(mockId(n))
      if (course) { course.code = null; course.created_by = 'user'; course.created_at = nowIso() }
    }
    if (!course) throw new MockNotFound()
    let topic: BrainTopic | null = null
    if (request.topic_id) topic = this.topics.get(request.topic_id) ?? null
    else if (request.new_topic_title) {
      const n = this.nextN()
      this.topics.set(mockId(n), { id: mockId(n), course_id: course.id, title: request.new_topic_title.trim(), sequence: null, sequence_kind: null, item_count: 0, concept_count: 0, created_at: nowIso() })
      topic = this.topics.get(mockId(n)) ?? null
    } else if (request.topic_id === undefined) {
      topic = [...this.topics.values()].find((t) => t.course_id === course?.id) ?? null
    }
    Object.assign(item, {
      course_id: course.id, course_title: course.title, topic_id: topic?.id ?? null, topic_title: topic?.title ?? null,
      confidence: 1, needs_review: false, alternatives: [],
    })
    for (const conceptId of item.concept_ids) {
      const concept = this.concepts.get(conceptId)
      if (concept && concept.course_id !== course.id) { concept.course_id = course.id; concept.topic_id = topic?.id ?? null }
    }
    this.recount()
    this.emit({ type: 'item.refiled', item: clone(item) })
    return clone({ item, course, topic, learned: true })
  }

  async telegramStatus(): Promise<TelegramStatus> {
    return clone(this.telegram)
  }

  async telegramLinkCode(): Promise<TelegramLinkCode> {
    // Mock: the link "completes" six seconds later, as if the user pressed Start in Telegram.
    setTimeout(() => {
      this.telegram = { ...this.telegram, linked: true, telegram_username: 'aruzhan_s', linked_at: nowIso() }
      this.emit({ type: 'telegram.linked', telegram: clone(this.telegram) })
    }, 6000 * timeScale)
    return { code: '483921', deep_link: 'https://t.me/FibonacciBrainBot?start=483921', expires_at: new Date(Date.now() + 600_000).toISOString(), bot_username: 'FibonacciBrainBot' }
  }

  async telegramUnlink(): Promise<void> {
    this.telegram = { ...this.telegram, linked: false, telegram_username: null, linked_at: null }
  }

  // ---- capture ----------------------------------------------------------------

  private nextN() {
    this.dynamicCounter += 1
    return this.dynamicCounter
  }

  async captureLink(url: string, channel: CaptureChannel = 'web_paste'): Promise<BrainItem> {
    const youtube = url.match(/(?:youtu\.be\/|v=|shorts\/)([\w-]{11})/)?.[1]
    if (youtube === HERO_YOUTUBE && !this.items.has(mockId(442))) return this.playHeroItem(1, channel)
    const kind: CaptureKind = youtube ? 'youtube' : 'web'
    const item = this.newPendingItem(kind, channel, youtube ? 'YouTube video' : new URL(url).hostname, { source_url: url, youtube_id: youtube ?? null, thumbnail_url: youtube ? ytThumb(youtube) : null })
    void this.playGeneric(item, url)
    return clone(item)
  }

  async captureText(text: string, title: string | undefined, channel: CaptureChannel = 'web_paste'): Promise<BrainItem> {
    const item = this.newPendingItem('text', channel, title?.trim() || text.trim().split('\n')[0].slice(0, 80))
    void this.playGeneric(item, text)
    return clone(item)
  }

  async captureFile(file: { name: string; type: string; size: number }, channel: CaptureChannel = 'web_drop'): Promise<BrainItem> {
    const name = file.name.toLowerCase()
    const kind: CaptureKind = file.type.startsWith('image/') ? 'photo' : name.endsWith('.pdf') ? 'pdf' : file.type.startsWith('audio/') ? 'audio' : 'document'
    if (kind === 'photo' && !this.items.has(mockId(441))) return this.playHeroItem(0, channel)
    if (kind === 'pdf' && !this.items.has(mockId(443))) return this.playHeroItem(2, channel)
    const item = this.newPendingItem(kind, channel, file.name)
    void this.playGeneric(item, file.name)
    return clone(item)
  }

  /** Plays the whole hero demo as if three items were forwarded to the Telegram bot. */
  async simulateHeroDemo(): Promise<void> {
    if (this.heroPlayed) return
    this.heroPlayed = true
    void this.playHeroItem(0, 'telegram')
    await sleep(1600)
    void this.playHeroItem(1, 'telegram')
    await sleep(1600)
    void this.playHeroItem(2, 'telegram')
  }

  private newPendingItem(kind: CaptureKind, channel: CaptureChannel, title: string, extra: Partial<BrainItem> = {}): BrainItem {
    const id = mockId(this.nextN())
    const item: BrainItem = {
      id, kind, channel, status: 'queued', progress: 0.02, title, summary: null, language: null,
      course_id: null, course_title: null, topic_id: null, topic_title: null, confidence: null, needs_review: false,
      alternatives: [], concept_ids: [], source_url: null, youtube_id: null, thumbnail_url: null, media_url: null,
      duration_sec: null, page_count: null, failure_code: null, captured_at: nowIso(), filed_at: null, timings_ms: {},
      ...extra,
    }
    this.items.set(id, item)
    this.emit({ type: 'item.created', item: clone(item) })
    return item
  }

  private async stage(item: BrainItem, status: ItemStatus, progress: number, wait: number) {
    await sleep(wait)
    item.status = status
    item.progress = progress
    this.emit({ type: 'item.progress', item_id: item.id, status, progress, title: item.title })
  }

  private async playHeroItem(index: 0 | 1 | 2, channel: CaptureChannel): Promise<BrainItem> {
    const seed = HERO_ITEMS[index]
    if (this.items.has(mockId(seed.n))) return clone(this.items.get(mockId(seed.n)) as BrainItem)
    const pending: BrainItem = {
      id: mockId(seed.n), kind: seed.kind, channel, status: 'queued', progress: 0.02,
      title: seed.kind === 'photo' ? 'IMG_4182.jpg' : seed.kind === 'pdf' ? 'ECON301_W6_notes.pdf' : 'youtu.be/' + HERO_YOUTUBE,
      summary: null, language: null, course_id: null, course_title: null, topic_id: null, topic_title: null,
      confidence: null, needs_review: false, alternatives: [], concept_ids: [],
      source_url: seed.youtube ? ytOpen(seed.youtube) : null, youtube_id: seed.youtube ?? null,
      thumbnail_url: seed.youtube ? ytThumb(seed.youtube) : null, media_url: null,
      duration_sec: null, page_count: null, failure_code: null, captured_at: nowIso(), filed_at: null, timings_ms: {},
    }
    this.items.set(pending.id, pending)
    this.emit({ type: 'item.created', item: clone(pending) })
    void (async () => {
      await this.stage(pending, 'extracting', 0.2, 500)
      await this.stage(pending, 'classifying', 0.55, seed.kind === 'youtube' ? 2400 : 1700)
      await this.stage(pending, 'linking', 0.82, 1300)
      await sleep(900)
      const newTopic = !this.topics.has(mockId(HERO_TOPIC.n))
      if (newTopic) this.addTopic(HERO_TOPIC)
      const newConcepts = HERO_CONCEPTS.filter((c) => seed.concepts.includes(c.n) && !this.concepts.has(mockId(c.n)))
      newConcepts.forEach((c) => this.addConcept(c))
      const gapsBefore = this.gaps().map((g) => g.id)
      const item = this.addItem(seed, { channel, captured_at: pending.captured_at, filed_at: nowIso(), timings_ms: { extract: 2100, classify: 1500, link: 1100, total: 4700 } })
      this.recount()
      const course = this.courses.get(item.course_id as UUID) as BrainCourse
      const topic = this.topics.get(item.topic_id as UUID) ?? null
      this.emit({ type: 'item.filed', item: clone(item), course: clone(course), topic: clone(topic), new_course: false, new_topic: newTopic,
        concepts: item.concept_ids.map((id) => clone(this.concepts.get(id) as BrainConcept)) })
      const gapsAfter = this.gaps().map((g) => g.id)
      gapsBefore.filter((g) => !gapsAfter.includes(g)).forEach((gapId) => this.emit({ type: 'gap.resolved', gap_id: gapId }))
      for (const seedLink of HERO_LINKS.filter((l) => l.after === seed.n)) {
        await sleep(450)
        const link = this.addLink(seedLink)
        if (link) this.emit({ type: 'link.created', link: clone(link), source: clone(this.concepts.get(link.source_concept_id) as BrainConcept), target: clone(this.concepts.get(link.target_concept_id) as BrainConcept) })
      }
    })()
    return clone(pending)
  }

  private async playGeneric(item: BrainItem, text: string) {
    const lower = text.toLowerCase()
    const topicN = /hetero|regress|ols|econom|dummy|autocorr/.test(lower) ? 204
      : /integr|series|taylor|calculus|limit/.test(lower) ? 223
      : /probab|variance|distribution|random|expect|clt|normal|mean/.test(lower) ? 215
      : null
    await this.stage(item, 'extracting', 0.2, 500)
    if (item.kind === 'web' && /drive\.google|instagram|login/.test(lower)) {
      await sleep(900)
      item.status = 'failed'
      item.failure_code = 'fetch_failed'
      this.emit({ type: 'item.failed', item_id: item.id, failure_code: 'fetch_failed' })
      return
    }
    await this.stage(item, 'classifying', 0.55, 1500)
    await this.stage(item, 'linking', 0.82, 1000)
    await sleep(700)
    let newCourse = false
    let topic = topicN ? this.topics.get(mockId(topicN)) ?? null : null
    let course = topic ? this.courses.get(topic.course_id) : undefined
    if (!course) {
      const existing = [...this.courses.values()].find((c) => c.title === 'General notes')
      if (existing) course = existing
      else {
        const n = this.nextN()
        this.addCourse({ n, title: 'General notes', code: '', color: this.courses.size % 8, seqKind: 'week', days: 0 })
        course = this.courses.get(mockId(n)) as BrainCourse
        course.code = null
        course.created_at = nowIso()
        newCourse = true
      }
      topic = null
    }
    const conceptN = this.nextN()
    const conceptName = item.kind === 'youtube' ? 'Lecture video notes' : item.title.slice(0, 40)
    this.concepts.set(mockId(conceptN), {
      id: mockId(conceptN), course_id: course.id, topic_id: topic?.id ?? null, name: conceptName,
      summary: 'Captured in mock mode; the live API extracts real concepts from the content.', mention_count: 1, created_at: nowIso(),
    })
    const chunkId = mockId(this.nextN() + 50_000)
    this.chunks.set(chunkId, { id: chunkId, item_id: item.id, ordinal: 0, anchor: { kind: 'paragraph', paragraph: 1 }, text: text.slice(0, 400), concept_ids: [mockId(conceptN)] })
    Object.assign(item, {
      status: 'filed', progress: 1, summary: 'Mock filing for UI development.', language: 'en-US',
      course_id: course.id, course_title: course.title, topic_id: topic?.id ?? null, topic_title: topic?.title ?? null,
      confidence: topic ? 0.81 : 0.42, needs_review: !topic, concept_ids: [mockId(conceptN)], filed_at: nowIso(),
      alternatives: topic ? [] : [...this.courses.values()].filter((c) => c.id !== course?.id).slice(0, 2).map((c, i) => ({ course_id: c.id, course_title: c.title, topic_id: null, topic_title: 'New topic', confidence: 0.3 - i * 0.1 })),
      timings_ms: { extract: 1200, classify: 1300, link: 700, total: 3200 },
    } satisfies Partial<BrainItem>)
    this.recount()
    this.emit({ type: 'item.filed', item: clone(item), course: clone(course), topic: clone(topic), new_course: newCourse, new_topic: false, concepts: [clone(this.concepts.get(mockId(conceptN)) as BrainConcept)] })
  }

  // ---- exam mode ------------------------------------------------------------------

  async createExamPlan(courseId: UUID, request: ExamPlanRequest): Promise<StudyPlan> {
    const course = this.courses.get(courseId)
    if (!course) throw new MockNotFound()
    const existing = this.plans.get(request.request_id)
    if (existing) return clone(existing)
    const examDate = request.exam_date ?? new Date(Date.now() + request.days * 86_400_000).toISOString().slice(0, 10)
    const plan: StudyPlan = {
      id: request.request_id, course_id: courseId, days: request.days, exam_date: examDate, language: request.language,
      status: 'generating', failure_code: null, content: null, coverage: null, created_at: nowIso(),
    }
    this.plans.set(plan.id, plan)
    void (async () => {
      for (const stage of ['gathering', 'planning', 'citing'] as const) {
        await sleep(1100)
        this.emit({ type: 'plan.progress', plan_id: plan.id, stage })
      }
      await sleep(600)
      const content = courseId === mockId(101) ? this.econPlan(request.days, examDate) : this.genericPlan(courseId, request.days, examDate)
      const cited = new Set<string>()
      const collect = (refs: SourceRef[]) => refs.forEach((r) => cited.add(r.item_id))
      content.days.forEach((d) => d.tasks.forEach((t) => collect(t.sources)))
      content.notes.forEach((n) => n.bullets.forEach((b) => collect(b.sources)))
      content.flashcards.forEach((f) => collect(f.sources))
      content.quiz.forEach((q) => collect(q.sources))
      Object.assign(plan, {
        status: 'ready', content,
        coverage: { item_count: course.item_count, cited_item_count: [...cited].filter((id) => this.items.get(id)?.course_id === courseId).length, missing: this.gaps(courseId) },
      } satisfies Partial<StudyPlan>)
      this.emit({ type: 'plan.ready', plan: clone(plan) })
    })()
    return clone(plan)
  }

  async plan(id: UUID): Promise<StudyPlan> {
    const plan = this.plans.get(id)
    if (!plan) throw new MockNotFound()
    return clone(plan)
  }

  async coursePlans(courseId: UUID): Promise<StudyPlan[]> {
    return clone([...this.plans.values()].filter((p) => p.course_id === courseId).sort((a, b) => b.created_at.localeCompare(a.created_at)))
  }

  async answerQuiz(planId: UUID, questionId: string, optionId: QuizOptionId): Promise<QuizAnswerResult> {
    const secret = this.answers.get(`${planId}:${questionId}`)
    if (!secret) throw new MockNotFound()
    const correct = secret.correct === optionId
    return clone({
      question_id: questionId, correct, correct_option_id: secret.correct, explanation: secret.explanation,
      moment: secret.moment ? { source: secret.moment, reason: secret.reason, confidence: 0.88 } : null,
      attempt_id: mockId(this.nextN()),
    })
  }

  private dateFor(examDate: string, days: number, day: number) {
    const date = new Date(`${examDate}T00:00:00Z`)
    date.setUTCDate(date.getUTCDate() - (days - day + 1))
    return date.toISOString().slice(0, 10)
  }

  private question(planId: string, id: string, prompt: string, options: string[], correct: QuizOptionId, concepts: number[], sources: SourceRef[], explanation: CitedText, moment: SourceRef | null, reason: string): QuizQuestion {
    this.answers.set(`${planId}:${id}`, { correct, explanation, moment, reason })
    return { id, prompt, options: options.map((text, i) => ({ id: (['a', 'b', 'c', 'd'] as const)[i], text })), concept_ids: concepts.map(mockId), sources }
  }

  private econPlan(days: number, examDate: string) {
    const hero = this.items.has(mockId(441))
    const r = (...pairs: Array<[number, number]>) => this.refs(...pairs)
    const planId = [...this.plans.keys()].pop() as string
    const allDays: PlanDay[] = [
      { day: 1, date: null, focus: 'Regression foundations and the Gauss–Markov assumptions', tasks: [
        { id: 't1', kind: 'read', title: 'Re-read how the OLS slope is built from Cov and Var', minutes: 25, topic_id: mockId(201), sources: r([401, 1], [419, 1]) },
        { id: 't2', kind: 'review', title: 'List the five Gauss–Markov assumptions from memory, then check', minutes: 15, topic_id: mockId(202), sources: r([404, 0], [405, 0]) },
        { id: 't3', kind: 'flashcards', title: 'Flashcards 1–4', minutes: 10, topic_id: null, sources: r([404, 1]) },
      ] },
      { day: 2, date: null, focus: hero ? 'Heteroskedasticity: what breaks and how to fix it' : 'Inference: t and F tests', tasks: hero ? [
        { id: 't4', kind: 'watch', title: 'Watch 4:05–5:01 and 14:32–15:10 of the zedstatistics lecture', minutes: 15, topic_id: mockId(206), sources: r([442, 0], [442, 1]) },
        { id: 't5', kind: 'read', title: 'Slide 7 and Week 6 notes pages 2–5', minutes: 25, topic_id: mockId(206), sources: r([441, 0], [443, 0], [443, 2]) },
        { id: 't6', kind: 'practice', title: 'Run a White test by hand on the Week 6 example', minutes: 20, topic_id: mockId(206), sources: r([443, 1]) },
      ] : [
        { id: 't4', kind: 'watch', title: 'Watch the t-test segment', minutes: 15, topic_id: mockId(204), sources: r([409, 0]) },
        { id: 't5', kind: 'practice', title: 'Problem set 2, question 4', minutes: 30, topic_id: mockId(204), sources: r([410, 0]) },
      ] },
      { day: 3, date: null, focus: 'Mixed practice and the quiz', tasks: [
        { id: 't7', kind: 'quiz', title: 'Take the 5-question quiz; revisit every miss', minutes: 20, topic_id: null, sources: r([409, 0], [414, 0]) },
        { id: 't8', kind: 'review', title: 'Autocorrelation vs heteroskedasticity — one-line summary each', minutes: 10, topic_id: mockId(208), sources: r([414, 0], [415, 0]) },
      ] },
    ]
    const dayList = allDays.slice(0, Math.max(1, Math.min(days, 3)))
    while (dayList.length < days) {
      dayList.push({ day: dayList.length + 1, date: null, focus: 'Spaced review of weak spots', tasks: [{ id: `t${dayList.length + 9}`, kind: 'review', title: 'Redo missed quiz questions and their sources', minutes: 20, topic_id: null, sources: r([404, 0]) }] })
    }
    dayList.forEach((d, i) => { d.day = i + 1; d.date = this.dateFor(examDate, days, i + 1) })

    const notes: PlanNote[] = [
      { id: 'n1', heading: 'OLS and what it needs', topic_id: mockId(202), bullets: [
        { text: 'The OLS slope is Cov(x, y) / Var(x) — the same covariance and variance from Probability.', sources: r([401, 1], [423, 0]) },
        { text: 'Unbiasedness needs MLR.1–4; being BLUE also needs homoskedasticity (MLR.5).', sources: r([404, 1], [405, 0]) },
      ] },
      ...(hero ? [{ id: 'n2', heading: 'Heteroskedasticity', topic_id: mockId(206), bullets: [
        { text: 'Heteroskedasticity means Var(u|x) changes with x.', sources: r([441, 0], [442, 0]) },
        { text: 'OLS coefficients stay unbiased, but the usual standard errors — and so t and F tests — are invalid.', sources: r([442, 1], [443, 0]) },
        { text: 'Detect it with Breusch–Pagan or White tests; fix inference with robust standard errors or use WLS.', sources: r([442, 2], [443, 1], [443, 2]) },
      ] }] : []),
      { id: 'n3', heading: 'Testing', topic_id: mockId(204), bullets: [
        { text: 't = estimate / standard error; the standard error is the spread of the estimator’s sampling distribution.', sources: r([409, 0], [427, 0]) },
      ] },
    ]

    const flashcards: Flashcard[] = [
      { id: 'f1', front: 'OLS slope in simple regression?', back: 'b₁ = Cov(x, y) / Var(x)', sources: r([401, 1]) },
      { id: 'f2', front: 'What does homoskedasticity assume?', back: 'Var(u | x) = σ², constant for all x.', sources: r([404, 0]) },
      { id: 'f3', front: 'Var(X) shortcut?', back: 'E[X²] − (E[X])²', sources: r([420, 0], [419, 1]) },
      ...(hero ? [
        { id: 'f4', front: 'What does heteroskedasticity break?', back: 'The usual standard errors (so t/F tests), not unbiasedness.', sources: r([442, 1], [441, 0]) },
        { id: 'f5', front: 'White test statistic?', back: 'n·R² from regressing û² on x, x², and cross-products; compare with χ².', sources: r([443, 1]) },
      ] : []),
      { id: 'f6', front: 'Durbin–Watson near 2 means?', back: 'No first-order autocorrelation.', sources: r([414, 1]) },
    ]

    const quiz: QuizQuestion[] = [
      this.question(planId, 'q1', 'In simple regression, the OLS slope equals…', ['Cov(x, y) / Var(x)', 'Var(x) / Cov(x, y)', 'Corr(x, y)', 'E[y] / E[x]'], 'a', [302],
        r([401, 1]), { text: 'The slope is the covariance of x and y divided by the variance of x.', sources: r([401, 1]) }, this.refs([401, 1])[0] ?? null, 'Page 9 of Lecture 1 writes the slope in exactly this form.'),
      ...(hero ? [this.question(planId, 'q2', 'If Var(u | x) grows with x, which statement about OLS is true?',
        ['The coefficient estimates become biased', 'The coefficients stay unbiased, but the usual standard errors are wrong', 'R² must be negative', 'OLS cannot be computed'], 'b', [351, 352],
        r([442, 1], [441, 0]), { text: 'Heteroskedasticity leaves OLS unbiased but invalidates the usual standard errors, so t and F tests can mislead.', sources: r([442, 1], [443, 0]) },
        this.refs([442, 1])[0] ?? null, 'At 14:32 the lecturer explains that only the standard errors break, not the coefficients.')] : []),
      this.question(planId, 'q3', 'Which assumption is needed for OLS to be BLUE but not for it to be unbiased?', ['Random sampling', 'Zero conditional mean', 'Homoskedasticity', 'No perfect collinearity'], 'c', [305, 306],
        r([404, 1], [405, 0]), { text: 'Unbiasedness uses MLR.1–4; efficiency (BLUE) additionally needs homoskedasticity.', sources: r([405, 0]) }, this.refs([405, 0])[0] ?? null, 'Your own note from Week 2 separates exactly these two results.'),
      this.question(planId, 'q4', 'Var(X) can be computed as…', ['E[X]²', 'E[X²] − (E[X])²', 'E[X] − E[X²]', 'Cov(X, 1)'], 'b', [324],
        r([420, 0]), { text: 'Expanding E[(X − μ)²] gives E[X²] − μ².', sources: r([420, 0], [419, 1]) }, this.refs([418, 1])[0] ?? null, 'The jbstatistics video derives this shortcut at 4:22.'),
      this.question(planId, 'q5', 'A Durbin–Watson statistic close to 2 suggests…', ['Strong positive autocorrelation', 'Heteroskedasticity', 'No first-order autocorrelation', 'Perfect multicollinearity'], 'c', [315],
        r([414, 1]), { text: 'd ≈ 2(1 − ρ̂), so d ≈ 2 means ρ̂ ≈ 0.', sources: r([414, 1]) }, this.refs([414, 1])[0] ?? null, 'Page 11 of Lecture 8 gives the approximation d ≈ 2(1 − ρ̂).'),
    ]
    return { title: `Econometrics — exam in ${days} day${days === 1 ? '' : 's'}`, days: dayList, notes, flashcards, quiz }
  }

  private genericPlan(courseId: UUID, days: number, examDate: string) {
    const planId = [...this.plans.keys()].pop() as string
    const course = this.courses.get(courseId) as BrainCourse
    const topics = [...this.topics.values()].filter((t) => t.course_id === courseId).sort((a, b) => (a.sequence ?? 99) - (b.sequence ?? 99))
    const firstRef = (topicId: UUID) => {
      const item = this.sortedItems().find((i) => i.topic_id === topicId && i.status === 'filed')
      const chunk = item ? [...this.chunks.values()].find((c) => c.item_id === item.id) : undefined
      return chunk ? [this.sourceRef(chunk.id) as SourceRef] : []
    }
    const perDay = Math.max(1, Math.ceil(topics.length / days))
    const dayList: PlanDay[] = Array.from({ length: days }, (_, i) => {
      const slice = topics.slice(i * perDay, (i + 1) * perDay)
      const tasks: PlanTask[] = slice.map((topic, j): PlanTask => ({ id: `t${i}-${j}`, kind: 'review', title: `Review: ${topic.title}`, minutes: 25, topic_id: topic.id, sources: firstRef(topic.id) })).filter((t) => t.sources.length)
      return { day: i + 1, date: this.dateFor(examDate, days, i + 1), focus: slice.map((t) => t.title).join(' · ') || 'Mixed review', tasks }
    })
    const concepts = [...this.concepts.values()].filter((c) => c.course_id === courseId).slice(0, 5)
    const quiz = concepts.map((concept, index) => {
      const others = [...this.concepts.values()].filter((c) => c.id !== concept.id).slice(index, index + 3)
      const chunk = [...this.chunks.values()].find((c) => c.concept_ids.includes(concept.id))
      const ref = chunk ? this.sourceRef(chunk.id) : null
      return this.question(planId, `q${index + 1}`, `Which statement describes “${concept.name}”?`, [concept.summary, ...others.map((o) => o.summary)], 'a', [],
        ref ? [ref] : [], { text: concept.summary, sources: ref ? [ref] : [] }, ref, 'This is where the idea appears in your material.')
    })
    quiz.forEach((q) => { q.concept_ids = concepts.filter((c) => q.prompt.includes(c.name)).map((c) => c.id) })
    const notes: PlanNote[] = topics.slice(0, 4).map((topic, i) => ({ id: `n${i}`, heading: topic.title, topic_id: topic.id,
      bullets: [...this.concepts.values()].filter((c) => c.topic_id === topic.id).map((c) => ({ text: c.summary, sources: firstRef(topic.id) })).filter((b) => b.sources.length) }))
    const flashcards: Flashcard[] = concepts.map((c, i) => ({ id: `f${i}`, front: c.name, back: c.summary, sources: quiz[i]?.sources ?? [] })).filter((f) => f.sources.length)
    return { title: `${course.title} — exam in ${days} days`, days: dayList, notes, flashcards, quiz: quiz.filter((q) => q.sources.length) }
  }
}

export class MockNotFound extends Error {
  status = 404
  code = 'not_found' as const
  constructor() { super('Not found in mock brain.') }
}

let singleton: MockBrain | null = null
/** One mock brain per browser tab, so captures persist across screens. */
export function getMockBrain(): MockBrain {
  singleton ??= new MockBrain()
  return singleton
}
