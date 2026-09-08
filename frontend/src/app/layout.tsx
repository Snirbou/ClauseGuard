import type { Metadata } from "next";
import { Geist, Geist_Mono, Heebo } from "next/font/google";
import "./globals.css";
import Header from "@/components/Header";
import DisclaimerBanner from "@/components/DisclaimerBanner";
import Providers from "@/components/Providers";
import { getServerI18n } from "@/i18n/server";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// Hebrew-capable face for the RTL locale; Geist has no Hebrew subset.
const heebo = Heebo({
  variable: "--font-heebo",
  subsets: ["hebrew", "latin"],
});

export async function generateMetadata(): Promise<Metadata> {
  const { dict } = await getServerI18n();
  return { title: dict.meta.siteTitle, description: dict.meta.siteDescription };
}

/**
 * The locale is resolved here once per request (cookie → Accept-Language →
 * English) and flows down as `<html lang dir>` plus the I18n context. Reading
 * cookies makes every route dynamic, which is fine for a Node-hosted app.
 */
export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const { locale, dict, rtl } = await getServerI18n();

  return (
    <html
      lang={locale}
      dir={rtl ? "rtl" : "ltr"}
      className={`${geistSans.variable} ${geistMono.variable} ${heebo.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-zinc-50 text-zinc-900 dark:bg-black dark:text-zinc-50">
        <Providers locale={locale}>
          {/* Non-dismissable by design — see DisclaimerBanner. */}
          <DisclaimerBanner />
          <Header />
          <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6">
            {children}
          </main>
        </Providers>
        <footer className="border-t border-zinc-200 px-4 py-6 text-center text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
          {dict.footer}
        </footer>
      </body>
    </html>
  );
}
