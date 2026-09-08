/**
 * English dictionary — the source of truth for every user-visible string.
 *
 * `Dictionary` is derived from this object, so `he.ts` must provide every
 * key with the same shape (functions included) or `tsc` fails. Keep values
 * observational: this UI must never give legal advice (PRD UPL rules).
 */

const clauses = (n: number): string => (n === 1 ? "1 clause" : `${n} clauses`);

export const en = {
  locale: "en",
  languageName: "English",

  meta: {
    siteTitle: "ClauseGuard — Understand your contracts before you sign",
    siteDescription:
      "Upload a freelance service agreement and get a plain-language, clause-by-clause risk breakdown. Educational analysis, not legal advice.",
    login: { title: "Sign in · ClauseGuard", description: "Sign in to your ClauseGuard account." },
    signup: {
      title: "Create account · ClauseGuard",
      description: "Create a ClauseGuard account to keep your contract analyses.",
    },
    upload: {
      title: "Upload a contract · ClauseGuard",
      description:
        "Upload a freelance service agreement PDF for clause extraction and risk analysis.",
    },
    contracts: {
      title: "My contracts · ClauseGuard",
      description: "Every contract you have uploaded, with its analysis status.",
    },
    contractDetail: {
      title: "Contract analysis · ClauseGuard",
      description: "Clause-by-clause risk analysis for an uploaded contract.",
    },
    dashboard: {
      title: "Evaluation dashboard · ClauseGuard",
      description:
        "Model quality, pipeline latency, and UPL compliance metrics for the ClauseGuard analysis pipeline.",
    },
  },

  common: {
    appName: "ClauseGuard",
    loading: "Loading",
    tryAgain: "Try again",
    delete: "Delete",
    deleting: "Deleting…",
    upload: "Upload",
    signIn: "Sign in",
    signOut: "Sign out",
    switchLanguage: "Switch language",
    clauses,
  },

  nav: {
    home: "Home",
    upload: "Upload",
    contracts: "Contracts",
    dashboard: "Dashboard",
    main: "Main",
  },

  footer: "ClauseGuard · Educational, pattern-based contract analysis · Not a law firm",

  disclaimer: {
    heading: "Not legal advice",
    text: "This tool provides educational, pattern-based analysis only. It is NOT legal advice. Always consult a qualified attorney.",
  },

  home: {
    eyebrow: "For freelancers",
    title: "Understand your contract before you sign it.",
    lead: "ClauseGuard reads freelance service agreements clause by clause, explains each one in plain English, and flags the terms most likely to hurt you — so you know exactly what you are agreeing to.",
    uploadCta: "Upload a contract",
    viewContracts: "View my contracts",
    howItWorks: "How it works",
    steps: [
      {
        title: "Upload your PDF",
        body: "Drop in a freelance service agreement. Text is extracted and split into individual clauses.",
      },
      {
        title: "Every clause gets classified",
        body: "Each clause is tagged — payment terms, IP assignment, termination, liability, and more.",
      },
      {
        title: "Read it in plain language",
        body: "The AI pass explains what each clause means for you, lists the specific risk factors, and scores its severity.",
      },
    ] as Array<{ title: string; body: string }>,
    riskLevelsTitle: "Risk levels at a glance",
    riskExamples: [
      { emoji: "🔴", level: "High risk", body: "Clauses that could cost you real money or rights." },
      { emoji: "🟡", level: "Medium risk", body: "Worth negotiating before you sign." },
      { emoji: "🟢", level: "Low risk", body: "Standard terms with no obvious traps." },
    ] as Array<{ emoji: string; level: string; body: string }>,
    notTitle: "What ClauseGuard is not",
    notBody:
      "ClauseGuard is an educational tool. It spots patterns that commonly cause trouble in freelance agreements, but it does not know your situation, your jurisdiction, or your negotiating position. It is not a lawyer and it does not give legal advice. For anything that matters, have a qualified attorney read the contract.",
  },

  auth: {
    login: {
      title: "Welcome back",
      subtitle: "Sign in to see your contracts and analyses.",
      submit: "Sign in",
      submitting: "Signing in…",
      switchText: "New to ClauseGuard?",
      switchLabel: "Create an account",
    },
    signup: {
      title: "Create your account",
      subtitle: "Your contracts and analyses stay private to your account.",
      submit: "Create account",
      submitting: "Creating account…",
      switchText: "Already have an account?",
      switchLabel: "Sign in",
    },
    email: "Email",
    password: "Password",
    emailPlaceholder: "you@example.com",
    passwordPlaceholderLogin: "Your password",
    passwordPlaceholderSignup: (min: number): string => `At least ${min} characters`,
    invalidEmail: "Enter a valid email address.",
    passwordTooShort: (min: number): string => `Password must be at least ${min} characters.`,
    genericError: "Something went wrong. Please try again.",
  },

  upload: {
    pageTitle: "Upload a contract",
    pageLead:
      "Your PDF is parsed into individual clauses and each one is classified. Nothing is sent to the AI model until you start the analysis on the next screen.",
    dropTitle: "Drop a contract PDF here, or choose a file",
    dropHint: (maxSize: string): string => `PDF only · up to ${maxSize}`,
    choose: "Choose PDF",
    processing: "Processing…",
    extracting: "Extracting and classifying clauses…",
    failedTitle: "Upload failed",
    startOver: "Start over",
    invalidType: "Invalid file type. Please upload a PDF.",
    tooLarge: (size: string, max: string): string =>
      `File is too large (${size}). Maximum size is ${max}.`,
    empty: "This file is empty.",
    uploadFailed: "Upload failed.",
    successTitle: "Uploaded and segmented",
    extracted: (n: number, filename: string): string => `${clauses(n)} extracted from ${filename}.`,
    analysisStarted: "Analysis started automatically — open the contract to watch it.",
    analysisSkipped: (detail: string): string => `Automatic analysis skipped: ${detail}`,
    uploadAnother: "Upload another",
    analyzeThis: "Analyze this contract →",
    parsedClauses: "Parsed clauses",
  },

  contracts: {
    pageTitle: "My contracts",
    pageLead: "Select a contract to see its clause-by-clause analysis.",
    loading: "Loading your contracts…",
    loadFailedTitle: "Could not load contracts",
    loadFailed: "Could not load your contracts.",
    emptyTitle: "No contracts yet",
    emptyBody: "Upload a freelance service agreement to get a clause-by-clause breakdown.",
    emptyCta: "Upload your first contract",
    deleteFailed: "Could not delete the contract.",
    confirmDelete: (name: string, n: number): string =>
      `Delete "${name}"?\n\nThis permanently removes the contract, its ${clauses(n)} and any analysis. This cannot be undone.`,
    notAnalyzed: "Not analyzed",
    analyzed: "Analyzed",
    partlyAnalyzed: (done: number, total: number): string => `Partly analyzed ${done}/${total}`,
    deleteAria: (name: string): string => `Delete ${name}`,
  },

  detail: {
    loading: "Loading contract…",
    loadFailedTitle: "Could not load this contract",
    loadFailed: "Could not load this contract.",
    backToAll: "← Back to all contracts",
    allContracts: "← All contracts",
    uploaded: (date: string): string => `Uploaded ${date}`,
    analyzedCount: (n: number): string => `${n} analyzed`,
    notAnalyzedYet: "not analyzed yet",
    analyze: "Analyze contract",
    rerun: "Re-run analysis",
    analyzing: "Analyzing…",
    startFailedTitle: "Could not start the analysis",
    startFailed: "Analysis failed to start.",
    deleteFailedTitle: "Could not delete the contract",
    lastRunFailedTitle: "Last analysis run failed",
    progressTitle: "Analyzing clauses…",
    progressAria: "Clauses analyzed",
    progressHint:
      "Results appear below as each clause finishes. You can leave this page — the analysis keeps running on the server.",
    executiveSummary: "Executive summary",
    noAnalysisTitle: "No analysis yet",
    noAnalysisBody:
      "Clauses have been extracted and classified. Run the analysis to get a plain-language summary and risk assessment for each one.",
    clausesTitle: "Clauses",
    filterAria: "Filter by risk level",
    filters: { all: "All", high: "🔴 High", medium: "🟡 Medium", low: "🟢 Low" },
    noMatch: "No clauses match this filter.",
    /** Shown only in non-English locales: the contract and its analysis stay in English. */
    englishNote: "",
  },

  risk: {
    overview: "Risk overview",
    total: (n: number): string => `${clauses(n)} total`,
    levels: { high: "High", medium: "Medium", low: "Low" },
    unanalyzed: "Not analyzed",
    highWarning: (n: number): string =>
      `${clauses(n)} flagged as high risk. Read ${n === 1 ? "it" : "them"} carefully and consider having an attorney review the contract before signing.`,
  },

  findings: {
    title: "Missing protections",
    gaps: (n: number): string => (n === 1 ? "1 gap detected" : `${n} gaps detected`),
    severity: { high: "high", medium: "medium" } as Record<string, string>,
    /** Keyed by pain_point; falls back to the server's English text. */
    byPainPoint: {} as Record<string, { title: string; detail: string }>,
  },

  clause: {
    showLess: "Show less",
    showFullText: "Show full text",
    notAnalyzedYet: "This clause has not been analyzed yet.",
    whatThisMeans: "What this means",
    hideDetails: "Hide details",
    showDetails: "Show details — clause text & risk factors",
    percentile: (p: number): string =>
      `Scored higher risk than ${p}% of the clauses in this contract.`,
    clauseText: "Clause text",
    riskFactors: "Risk factors",
    noFactors: "No specific risk factors identified.",
    confidenceTitle: (pct: string): string => `Classifier confidence: ${pct}`,
    unclassified: "Unclassified",
  },

  cta: {
    flagged: "This clause was flagged as high risk. Have a qualified attorney review it before you sign.",
    consult: "Consult a Lawyer",
    mailSubject: (index: number): string => `Question about clause ${index} in my contract`,
    mailBody: (text: string): string =>
      `I would like advice on the following contract clause:\n\n"${text}"\n\n(Flagged as high risk by ClauseGuard, an automated tool. This is not legal advice.)`,
  },

  clauseTypes: {
    ip_assignment: "IP Assignment",
    payment_terms: "Payment Terms",
    termination: "Termination",
    liability: "Liability",
    confidentiality: "Confidentiality",
    scope_of_work: "Scope of Work",
    governing_law: "Governing Law",
    general: "General",
  } as Record<string, string>,

  dashboard: {
    pageTitle: "Evaluation dashboard",
    pageLead:
      "Live quality and health metrics for the three-layer analysis pipeline: classifier F1 per clause type, run latency, and the UPL compliance audit trail.",
    loading: "Loading metrics…",
    loadFailedTitle: "Could not load metrics",
    loadFailed: "Could not load metrics.",
    pipeline: "Pipeline",
    classifier: "Classifier",
    trainedModel: "Trained model",
    keywordFallback: "Keyword fallback",
    llmProvider: "LLM provider",
    concurrency: "Concurrency",
    retries: "Retries per clause",
    loadIssue: "Model load issue:",
    qualityTitle: "Clause classification quality",
    trainedMeta: (artifact: string, date: string, sklearn: string): string =>
      `${artifact} · trained ${date} · sklearn ${sklearn}`,
    macroF1: "Macro F1:",
    target: "target ≥ 0.850 (PRD AC-C02)",
    noModelBody:
      "The trained model is not loaded in this environment — the keyword fallback is active and no test metrics are available.",
    runsTitle: "Analysis runs",
    total: "Total",
    completed: "Completed",
    failed: "Failed",
    p50: "p50 latency",
    p95: "p95 latency",
    runsHint: "PRD target: p95 end-to-end ≤ 60,000ms for 5–20 page contracts.",
    complianceTitle: "UPL compliance",
    disclaimerViews: "Disclaimer views logged",
  },

  errorPage: {
    title: "Something went wrong",
    fallback: "An unexpected error occurred while rendering this page.",
  },
  notFound: {
    title: "Page not found",
    body: "The page you are looking for does not exist.",
    backHome: "Back home",
  },

  /**
   * Messages by backend error code (backend/error_codes.py) plus the
   * client-side codes from lib/api.ts. Unknown codes fall back to the
   * server's English `detail`.
   */
  errors: {
    "auth.sign_in_required": "Sign in to continue.",
    "auth.session_expired": "Your session has expired. Sign in again.",
    "auth.invalid_credentials": "Incorrect email or password.",
    "auth.email_taken": "An account with this email already exists.",
    "auth.invalid_email": "Enter a valid email address.",
    "auth.password_too_short": "Password must be at least 8 characters.",
    rate_limited: "Too many attempts. Wait a minute and try again.",
    "contract.not_found": "Contract not found.",
    "contract.delete_failed": "Failed to delete the contract.",
    "run.not_found": "Analysis run not found.",
    "analysis.failed": "The analysis could not be completed.",
    "analysis.llm_not_configured":
      "AI analysis is unavailable because no language model is configured on the server.",
    "analysis.in_progress": "Analysis is already running for this contract. Wait for it to finish.",
    "analysis.no_clauses": "This contract has no parsed clauses to analyze.",
    "upload.invalid_type": "Invalid file type. PDF required.",
    "upload.empty": "Empty file.",
    "upload.too_large": "File is too large.",
    "upload.read_failed": "Failed to read the uploaded file.",
    "upload.password_protected": "This PDF is password protected and cannot be read.",
    "upload.parse_failed": "Failed to parse the PDF.",
    "upload.needs_ocr":
      "Could not extract text from the PDF. It may be a scanned image, which needs OCR.",
    "upload.no_clauses": "No clauses could be extracted from this PDF.",
    "upload.persist_failed": "Failed to save the contract.",
    validation_error: "Invalid request.",
    internal_error: "Internal server error.",
    network: "Could not reach the ClauseGuard API. Make sure the backend is running.",
    bad_response: "The backend returned a response we could not read.",
    http_error: "The request failed.",
  } as Record<string, string>,
};

export type Dictionary = typeof en;
