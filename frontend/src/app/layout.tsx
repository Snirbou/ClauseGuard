import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Header from "@/components/Header";
import DisclaimerBanner from "@/components/DisclaimerBanner";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ClauseGuard — Understand your contracts before you sign",
  description:
    "Upload a freelance service agreement and get a plain-language, clause-by-clause risk breakdown. Educational analysis, not legal advice.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-zinc-50 text-zinc-900 dark:bg-black dark:text-zinc-50">
        {/* Non-dismissable by design — see DisclaimerBanner. */}
        <DisclaimerBanner />
        <Header />
        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6">
          {children}
        </main>
        <footer className="border-t border-zinc-200 px-4 py-6 text-center text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
          ClauseGuard · Educational, pattern-based contract analysis · Not a law firm
        </footer>
      </body>
    </html>
  );
}
