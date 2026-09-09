/**
 * Hebrew dictionary (Layer 1: Hebrew interface for English contracts).
 *
 * Typed as `Dictionary`, so a missing or mistyped key is a compile error.
 * Tone: observational, never prescriptive — no "כדאי לך", no "אנו ממליצים"
 * about the contract itself (PRD UPL rules, AC-P02). The only "advice" this
 * UI ever gives is to consult a qualified attorney, which the PRD requires.
 */

import type { Dictionary } from "./en";

const clauses = (n: number): string => {
  if (n === 1) return "סעיף אחד";
  if (n === 2) return "שני סעיפים";
  return `${n} סעיפים`;
};

export const he: Dictionary = {
  locale: "he",
  languageName: "עברית",

  meta: {
    siteTitle: "ClauseGuard — להבין את החוזה לפני שחותמים",
    siteDescription:
      "מעלים הסכם שירותים לפרילנסרים ומקבלים פירוט סיכונים סעיף-אחר-סעיף בשפה פשוטה. ניתוח חינוכי, לא ייעוץ משפטי.",
    login: { title: "כניסה · ClauseGuard", description: "כניסה לחשבון ClauseGuard שלך." },
    signup: {
      title: "פתיחת חשבון · ClauseGuard",
      description: "פתיחת חשבון ClauseGuard כדי לשמור את ניתוחי החוזים שלך.",
    },
    upload: {
      title: "העלאת חוזה · ClauseGuard",
      description: "העלאת קובץ PDF של הסכם שירותים לפרילנסרים לחילוץ סעיפים וניתוח סיכונים.",
    },
    contracts: {
      title: "החוזים שלי · ClauseGuard",
      description: "כל חוזה שהעלית, עם מצב הניתוח שלו.",
    },
    contractDetail: {
      title: "ניתוח חוזה · ClauseGuard",
      description: "ניתוח סיכונים סעיף-אחר-סעיף לחוזה שהועלה.",
    },
    dashboard: {
      title: "לוח הערכה · ClauseGuard",
      description: "מדדי איכות מודל, זמני עיבוד ותאימות UPL של צינור הניתוח של ClauseGuard.",
    },
  },

  common: {
    appName: "ClauseGuard",
    loading: "טוען",
    tryAgain: "לנסות שוב",
    delete: "מחיקה",
    deleting: "מוחק…",
    upload: "העלאה",
    signIn: "כניסה",
    signOut: "יציאה",
    switchLanguage: "החלפת שפה",
    clauses,
  },

  nav: {
    home: "בית",
    upload: "העלאה",
    contracts: "חוזים",
    dashboard: "לוח הערכה",
    main: "ראשי",
  },

  footer: "ClauseGuard · ניתוח חוזים חינוכי מבוסס-דפוסים · לא משרד עורכי דין",

  disclaimer: {
    heading: "לא ייעוץ משפטי",
    text: "כלי זה מספק ניתוח חינוכי מבוסס-דפוסים, למטרות מידע בלבד. הוא אינו ייעוץ משפטי. יש להתייעץ תמיד עם עורך דין מוסמך.",
  },

  home: {
    eyebrow: "לפרילנסרים",
    title: "להבין את החוזה לפני שחותמים עליו.",
    lead: "ClauseGuard קורא הסכמי שירותים לפרילנסרים סעיף אחר סעיף, מסביר כל אחד מהם בשפה פשוטה, ומסמן את התנאים שסביר שיפגעו בכם — כך שתדעו בדיוק על מה אתם מסכימים.",
    uploadCta: "העלאת חוזה",
    viewContracts: "לחוזים שלי",
    howItWorks: "איך זה עובד",
    steps: [
      {
        title: "מעלים PDF",
        body: "גוררים הסכם שירותים לפרילנסרים. הטקסט מחולץ ומפוצל לסעיפים נפרדים.",
      },
      {
        title: "כל סעיף מסווג",
        body: "כל סעיף מקבל תגית — תנאי תשלום, קניין רוחני, סיום התקשרות, אחריות ועוד.",
      },
      {
        title: "קוראים בשפה פשוטה",
        body: "שלב ה-AI מסביר מה כל סעיף אומר עבורך, מפרט את גורמי הסיכון הספציפיים ומדרג את חומרתו.",
      },
    ],
    riskLevelsTitle: "רמות הסיכון במבט אחד",
    riskExamples: [
      { emoji: "🔴", level: "סיכון גבוה", body: "סעיפים שעלולים לעלות לך בכסף אמיתי או בזכויות." },
      { emoji: "🟡", level: "סיכון בינוני", body: "נושאים שנהוג לדון בהם לפני החתימה." },
      { emoji: "🟢", level: "סיכון נמוך", body: "תנאים סטנדרטיים ללא מלכודות בולטות." },
    ],
    notTitle: "מה ClauseGuard אינו",
    notBody:
      "ClauseGuard הוא כלי חינוכי. הוא מזהה דפוסים שמרבים לגרום לבעיות בהסכמי פרילנס, אבל הוא לא מכיר את המצב שלך, את תחום השיפוט או את עמדת המיקוח שלך. הוא לא עורך דין ולא נותן ייעוץ משפטי. בכל עניין בעל משמעות, כדאי שעורך דין מוסמך יקרא את החוזה.",
  },

  auth: {
    login: {
      title: "ברוכים השבים",
      subtitle: "היכנסו כדי לראות את החוזים והניתוחים שלכם.",
      submit: "כניסה",
      submitting: "מתבצעת כניסה…",
      switchText: "חדשים ב-ClauseGuard?",
      switchLabel: "פתיחת חשבון",
    },
    signup: {
      title: "פתיחת חשבון",
      subtitle: "החוזים והניתוחים שלכם נשארים פרטיים לחשבון שלכם.",
      submit: "פתיחת חשבון",
      submitting: "החשבון נפתח…",
      switchText: "כבר יש לכם חשבון?",
      switchLabel: "כניסה",
    },
    email: "אימייל",
    password: "סיסמה",
    emailPlaceholder: "you@example.com",
    passwordPlaceholderLogin: "הסיסמה שלך",
    passwordPlaceholderSignup: (min: number): string => `לפחות ${min} תווים`,
    invalidEmail: "יש להזין כתובת אימייל תקינה.",
    passwordTooShort: (min: number): string => `הסיסמה חייבת להכיל לפחות ${min} תווים.`,
    genericError: "משהו השתבש. נסו שוב.",
  },

  upload: {
    pageTitle: "העלאת חוזה",
    pageLead:
      "קובץ ה-PDF מפורק לסעיפים נפרדים וכל אחד מהם מסווג. שום דבר לא נשלח למודל ה-AI עד שמפעילים את הניתוח במסך הבא.",
    dropTitle: "גררו לכאן PDF של חוזה, או בחרו קובץ",
    dropHint: (maxSize: string): string => `PDF בלבד · עד ${maxSize}`,
    choose: "בחירת PDF",
    processing: "מעבד…",
    extracting: "מחלץ ומסווג סעיפים…",
    failedTitle: "ההעלאה נכשלה",
    startOver: "להתחיל מחדש",
    invalidType: "סוג קובץ לא נתמך. יש להעלות PDF.",
    tooLarge: (size: string, max: string): string =>
      `הקובץ גדול מדי (${size}). הגודל המרבי הוא ${max}.`,
    empty: "הקובץ ריק.",
    uploadFailed: "ההעלאה נכשלה.",
    successTitle: "הועלה ופוצל לסעיפים",
    extracted: (n: number, filename: string): string =>
      n === 1 ? `סעיף אחד חולץ מתוך ${filename}.` : `${clauses(n)} חולצו מתוך ${filename}.`,
    analysisStarted: "הניתוח התחיל אוטומטית — פתחו את החוזה כדי לעקוב.",
    analysisSkipped: (detail: string): string => `הניתוח האוטומטי לא הופעל: ${detail}`,
    uploadAnother: "להעלות חוזה נוסף",
    analyzeThis: "לניתוח החוזה ←",
    parsedClauses: "סעיפים שחולצו",
  },

  contracts: {
    pageTitle: "החוזים שלי",
    pageLead: "בחרו חוזה כדי לראות את הניתוח שלו סעיף-אחר-סעיף.",
    loading: "טוען את החוזים שלך…",
    loadFailedTitle: "לא ניתן לטעון את החוזים",
    loadFailed: "לא ניתן היה לטעון את החוזים שלך.",
    emptyTitle: "עדיין אין חוזים",
    emptyBody: "העלו הסכם שירותים לפרילנסרים כדי לקבל פירוט סעיף-אחר-סעיף.",
    emptyCta: "העלאת החוזה הראשון",
    deleteFailed: "לא ניתן היה למחוק את החוזה.",
    // \u2068…\u2069 (first-strong isolate) keeps a filename that starts with
    // digits or Latin from being reordered by the dialog's bidi algorithm.
    confirmDelete: (name: string, n: number): string => {
      const its = n === 1 ? "הסעיף שבו" : n === 2 ? "שני הסעיפים שבו" : `${n} הסעיפים שבו`;
      return `למחוק את "\u2068${name}\u2069"?\n\nהפעולה מוחקת לצמיתות את החוזה, את ${its} וכל ניתוח שלו. אי אפשר לבטל אותה.`;
    },
    notAnalyzed: "לא נותח",
    analyzed: "נותח",
    partlyAnalyzed: (done: number, total: number): string => `נותח חלקית ${done}/${total}`,
    deleteAria: (name: string): string => `מחיקת ${name}`,
  },

  detail: {
    loading: "טוען חוזה…",
    loadFailedTitle: "לא ניתן לטעון את החוזה",
    loadFailed: "לא ניתן היה לטעון את החוזה הזה.",
    backToAll: "→ חזרה לכל החוזים",
    allContracts: "→ כל החוזים",
    uploaded: (date: string): string => `הועלה ${date}`,
    analyzedCount: (n: number): string => (n === 1 ? "1 נותח" : `${n} נותחו`),
    notAnalyzedYet: "טרם נותח",
    analyze: "ניתוח החוזה",
    rerun: "הרצת ניתוח מחדש",
    analyzing: "מנתח…",
    startFailedTitle: "לא ניתן היה להתחיל את הניתוח",
    startFailed: "לא ניתן היה להתחיל את הניתוח.",
    deleteFailedTitle: "לא ניתן היה למחוק את החוזה",
    lastRunFailedTitle: "ריצת הניתוח האחרונה נכשלה",
    progressTitle: "מנתח סעיפים…",
    progressAria: "סעיפים שנותחו",
    progressHint:
      "התוצאות מופיעות למטה עם סיום כל סעיף. אפשר לעזוב את הדף — הניתוח ממשיך לרוץ בשרת.",
    executiveSummary: "תקציר מנהלים",
    noAnalysisTitle: "עדיין אין ניתוח",
    noAnalysisBody:
      "הסעיפים חולצו וסווגו. הפעילו את הניתוח כדי לקבל סיכום בשפה פשוטה והערכת סיכון לכל אחד מהם.",
    clausesTitle: "סעיפים",
    filterAria: "סינון לפי רמת סיכון",
    filters: { all: "הכול", high: "🔴 גבוה", medium: "🟡 בינוני", low: "🟢 נמוך" },
    noMatch: "אין סעיפים שמתאימים לסינון הזה.",
    englishNote: "טקסט החוזה והניתוח מוצגים באנגלית, שפת החוזה.",
  },

  risk: {
    overview: "סקירת סיכונים",
    total: (n: number): string => `${clauses(n)} בסך הכול`,
    levels: { high: "גבוה", medium: "בינוני", low: "נמוך" },
    unanalyzed: "לא נותח",
    highWarning: (n: number): string =>
      n === 1
        ? "סעיף אחד סומן כסיכון גבוה. נהוג לקרוא אותו בעיון ולשקול בדיקה על ידי עורך דין לפני החתימה."
        : `${clauses(n)} סומנו כסיכון גבוה. נהוג לקרוא אותם בעיון ולשקול בדיקה על ידי עורך דין לפני החתימה.`,
  },

  findings: {
    title: "הגנות חסרות",
    gaps: (n: number): string => (n === 1 ? "זוהה פער אחד" : `זוהו ${n} פערים`),
    severity: { high: "גבוה", medium: "בינוני" },
    byPainPoint: {
      payment_traps: {
        title: "לא זוהו תנאי תשלום",
        detail:
          "לא זוהה בחוזה סעיף תנאי תשלום. הסכמי שירותים לפרילנסרים נוהגים לציין את התמורה, מועדי החיוב וחלון התשלום — תנאים שקשה הרבה יותר לאכוף כשאינם כתובים. היעדרם נקשר לעיתים קרובות לתשלום מאוחר או שנוי במחלוקת.",
      },
      scope_creep: {
        title: "לא זוהה היקף עבודה",
        detail:
          "לא זוהה סעיף היקף עבודה. הסכמים ללא היקף כתוב משאירים לרוב את התוצרים, סבבי התיקונים וקריטריוני הקבלה לא מוגדרים — הדפוס שמזוהה ביותר עם זחילת היקף ועבודה נוספת ללא תשלום.",
      },
      ip_assignment: {
        title: "לא זוהה סעיף קניין רוחני",
        detail:
          "לא זוהה סעיף שעוסק בבעלות על קניין רוחני. כשחוזה שותק בעניין קניין רוחני, הבעלות על תוצרי העבודה — ועל כלים קיימים שנעשה בהם שימוש — נקבעת לפי ברירת המחדל של הדין, שמשתנה בין תחומי שיפוט ולעיתים קרובות מפתיעה את שני הצדדים.",
      },
      termination_asymmetry: {
        title: "לא זוהה סעיף סיום התקשרות",
        detail:
          "לא זוהה סעיף סיום התקשרות. בלעדיו, תקופת ההודעה המוקדמת, חובות הסיום והתשלום על עבודה בתהליך אינם מוגדרים אם אחד הצדדים מסיים את ההתקשרות מוקדם.",
      },
      liability_gaps: {
        title: "לא זוהה סעיף אחריות",
        detail:
          "לא זוהה סעיף אחריות או שיפוי. חוזים ששותקים בעניין אחריות משאירים את החשיפה ללא תקרה כברירת מחדל; סעיפי אחריות נוהגים לעסוק בתקרות, בהחרגת נזקים עקיפים ובחובות שיפוי.",
      },
    },
  },

  clause: {
    showLess: "להציג פחות",
    showFullText: "להציג את הטקסט המלא",
    notAnalyzedYet: "הסעיף הזה עדיין לא נותח.",
    whatThisMeans: "מה זה אומר",
    hideDetails: "הסתרת פרטים",
    showDetails: "הצגת פרטים — טקסט הסעיף וגורמי הסיכון",
    percentile: (p: number): string => `דורג כמסוכן יותר מ-${p}% מהסעיפים בחוזה הזה.`,
    clauseText: "טקסט הסעיף",
    riskFactors: "גורמי סיכון",
    noFactors: "לא זוהו גורמי סיכון ספציפיים.",
    confidenceTitle: (pct: string): string => `רמת הביטחון של המסווג: ${pct}`,
    unclassified: "לא מסווג",
  },

  cta: {
    flagged: "הסעיף הזה סומן כסיכון גבוה. כדאי שעורך דין מוסמך יבדוק אותו לפני החתימה.",
    consult: "להתייעץ עם עורך דין",
    mailSubject: (index: number): string => `שאלה לגבי סעיף ${index} בחוזה שלי`,
    mailBody: (text: string): string =>
      `אשמח לייעוץ לגבי הסעיף הבא בחוזה:\n\n"${text}"\n\n(סומן כסיכון גבוה על ידי ClauseGuard, כלי אוטומטי. אין זה ייעוץ משפטי.)`,
  },

  clauseTypes: {
    ip_assignment: "קניין רוחני",
    payment_terms: "תנאי תשלום",
    termination: "סיום התקשרות",
    liability: "אחריות",
    confidentiality: "סודיות",
    scope_of_work: "היקף העבודה",
    governing_law: "דין חל",
    general: "כללי",
  },

  dashboard: {
    pageTitle: "לוח הערכה",
    pageLead:
      "מדדי איכות ותקינות בזמן אמת של צינור הניתוח התלת-שכבתי: F1 של המסווג לפי סוג סעיף, זמני ריצה ומסלול הביקורת של העמידה בכללי UPL.",
    loading: "טוען מדדים…",
    loadFailedTitle: "לא ניתן לטעון את המדדים",
    loadFailed: "לא ניתן היה לטעון את המדדים.",
    pipeline: "צינור העיבוד",
    classifier: "מסווג",
    trainedModel: "מודל מאומן",
    keywordFallback: "גיבוי מבוסס מילות מפתח",
    llmProvider: "ספק LLM",
    concurrency: "מקביליות",
    retries: "ניסיונות חוזרים לסעיף",
    loadIssue: "בעיה בטעינת המודל:",
    qualityTitle: "איכות סיווג הסעיפים",
    trainedMeta: (artifact: string, date: string, sklearn: string): string =>
      `${artifact} · אומן ב-${date} · sklearn ${sklearn}`,
    macroF1: "Macro F1:",
    target: "יעד ≥ 0.850 (PRD AC-C02)",
    noModelBody:
      "המודל המאומן לא נטען בסביבה הזו — הגיבוי מבוסס מילות המפתח פעיל ואין מדדי בדיקה זמינים.",
    runsTitle: "ריצות ניתוח",
    total: "סה״כ",
    completed: "הושלמו",
    failed: "נכשלו",
    p50: "זמן עיבוד p50",
    p95: "זמן עיבוד p95",
    p99: "זמן עיבוד p99",
    runsHint: "יעד PRD: p95 מקצה לקצה ≤ 60,000ms לחוזים של 5–20 עמודים.",
    complianceTitle: "עמידה בכללי UPL",
    disclaimerViews: "הצגות ההבהרה המשפטית שנרשמו",

    // --- גרסאות המודלים (AC §4) ---
    versionsTitle: "גרסאות המודלים",
    versionsHint: "קובץ המודל ותוכנית ה-DSPy שמשרתות בפועל את הבקשות ברגע זה.",
    classifierArtifact: "קובץ המסווג",
    spacyTrained: "spaCy באימון",
    spacyRuntime: "spaCy בריצה",
    dspyVersion: "גרסת DSPy",
    pipelineVersion: "גרסת הצינור",
    dspyProgram: "תוכנית DSPy",
    programOptimized: "מותאמת",
    programUnoptimized: "חתימה לא מותאמת",

    // --- הערכה על מדגם מוחזק ---
    holdoutNote: "ה-F1 לפי מחלקה שלמעלה הוא מדגם ההחזקה מזמן האימון, כפי שנשמר בקובץ המודל.",
    evalTitle: "הערכה על מדגם מוחזק",
    evalMeta: (dataset: string, split: string, n: number, spacyModel: string): string =>
      `${dataset} · ${split} · n=${n} · ${spacyModel}`,
    evalGenerated: (date: string): string => `נוצר ב-${date}`,
    evalMacroF1: "Macro F1",
    evalServedMacroF1: "Macro F1 בפועל",
    evalThreshold: "סף ביטחון",
    evalSampleSize: "סעיפים שהוערכו",
    colClass: "מחלקה",
    colPrecision: "דיוק",
    colRecall: "היזכרות",
    colF1: "F1",
    colSupport: "מופעים",
    confusionTitle: "מטריצת בלבול",
    confusionCorner: "אמת ╲ חיזוי",
    confusionCaption:
      "כל שורה היא התווית האמיתית וכל עמודה היא התווית שהמסווג חזה; הצללת התא היא חלקו מתוך השורה, ולכן האלכסון מציג את ההיזכרות של אותה מחלקה.",
    confusionCellTitle: (
      trueLabel: string,
      predictedLabel: string,
      count: number,
      share: string,
    ): string => `אמת ${trueLabel}, חיזוי ${predictedLabel}: ${count} (${share} מהשורה)`,

    // --- קריאות התקצירים (AC-P04) ---
    readabilityTitle: "קריאות התקצירים",
    readabilityAvg: "רמת קריאה ממוצעת",
    readabilityMedian: "חציון",
    readabilityShare: "בתוך היעד",
    readabilitySample: "תקצירים שנמדדו",
    readabilityTarget: (grade: number): string =>
      `יעד PRD: רמת Flesch-Kincaid ממוצעת ≤ ${grade} (AC-P04)`,
    readabilityEmpty: "עדיין אין תקצירים מנותחים — טקסט הדגמה אינו נכלל במדידה הזו.",

    // --- זיהוי סיכון גבוה (AC-R05) ---
    riskTitle: "זיהוי סיכון גבוה",
    riskTargets: (precision: string, recall: string): string =>
      `יעדי PRD: דיוק ≥ ${precision}, היזכרות ≥ ${recall} (AC-R05)`,
    riskPrecision: "דיוק",
    riskRecall: "היזכרות",
    riskF1: "F1",
    riskSample: "סעיפים מתויגים",
    riskThreshold: "סף לסיכון גבוה",
    riskNotMeasured: "טרם נמדד — נדרש מפתח LLM (שלב 4).",
    riskReason: "סיבה:",
    riskError: "שגיאה בהערכה:",
    riskCaveats: "הסתייגויות",
    riskGenerated: (date: string): string => `נמדד ב-${date}`,

    // --- היסטוריית האופטימייזר של DSPy (AC §4) ---
    optimizerTitle: "היסטוריית האופטימייזר של DSPy",
    optimizerEmpty: "עדיין לא נרשמה ריצת אופטימייזר.",
    optimizerPath: "קובץ ההיסטוריה:",
    colStarted: "התחילה",
    colOptimizer: "אופטימייזר",
    colAuto: "מצב",
    colTrainVal: "אימון / ולידציה",
    colBaseline: "בסיס",
    colBest: "הטוב ביותר",
    colArtifact: "קובץ",
    colTrialCount: "ניסיונות",
    trialsTitle: "הריצה האחרונה — ניסיונות",
    colTrial: "#",
    colScore: "ציון",
    colInstruction: "תצוגה מקדימה של ההנחיה",
  },

  errorPage: {
    title: "משהו השתבש",
    fallback: "אירעה שגיאה לא צפויה בעת הצגת הדף.",
  },
  notFound: {
    title: "הדף לא נמצא",
    body: "הדף שחיפשתם אינו קיים.",
    backHome: "חזרה לדף הבית",
  },

  errors: {
    "auth.sign_in_required": "יש להיכנס כדי להמשיך.",
    "auth.session_expired": "פג תוקף ההתחברות. היכנסו שוב.",
    "auth.invalid_credentials": "אימייל או סיסמה שגויים.",
    "auth.email_taken": "כבר קיים חשבון עם האימייל הזה.",
    "auth.invalid_email": "יש להזין כתובת אימייל תקינה.",
    "auth.password_too_short": "הסיסמה חייבת להכיל לפחות 8 תווים.",
    rate_limited: "יותר מדי ניסיונות. המתינו דקה ונסו שוב.",
    "contract.not_found": "החוזה לא נמצא.",
    "contract.delete_failed": "מחיקת החוזה נכשלה.",
    "run.not_found": "ריצת הניתוח לא נמצאה.",
    "analysis.failed": "לא ניתן היה להשלים את הניתוח.",
    "analysis.llm_not_configured": "ניתוח ה-AI אינו זמין כי לא הוגדר מודל שפה בשרת.",
    "analysis.in_progress": "ניתוח כבר רץ עבור החוזה הזה. המתינו לסיומו.",
    "analysis.no_clauses": "בחוזה הזה אין סעיפים לניתוח.",
    "upload.invalid_type": "סוג קובץ לא נתמך. נדרש PDF.",
    "upload.empty": "הקובץ ריק.",
    "upload.too_large": "הקובץ גדול מדי.",
    "upload.read_failed": "קריאת הקובץ שהועלה נכשלה.",
    "upload.password_protected": "קובץ ה-PDF מוגן בסיסמה ולא ניתן לקרוא אותו.",
    "upload.parse_failed": "פענוח קובץ ה-PDF נכשל.",
    "upload.needs_ocr": "לא ניתן היה לחלץ טקסט מה-PDF. ייתכן שזו תמונה סרוקה, שדורשת OCR.",
    "upload.no_clauses": "לא ניתן היה לחלץ סעיפים מקובץ ה-PDF הזה.",
    "upload.persist_failed": "שמירת החוזה נכשלה.",
    validation_error: "בקשה לא תקינה.",
    internal_error: "שגיאת שרת פנימית.",
    network: "לא ניתן להגיע ל-API של ClauseGuard. ודאו שהשרת פועל.",
    bad_response: "השרת החזיר תשובה שלא ניתן לקרוא.",
    http_error: "הבקשה נכשלה.",
  },
};
