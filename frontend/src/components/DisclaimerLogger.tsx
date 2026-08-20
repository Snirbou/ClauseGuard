"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/**
 * UPL audit trail (AC-X05): records every page view that rendered the
 * disclaimer banner. Fire-and-forget — logging must never affect the UX,
 * so failures are swallowed silently.
 */
export default function DisclaimerLogger() {
  const pathname = usePathname();

  useEffect(() => {
    if (!pathname) return;
    const contractMatch = pathname.match(/^\/contracts\/([0-9a-f-]{36})$/i);
    void fetch(`${API_BASE_URL}/api/disclaimer-views`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        page: pathname,
        contract_id: contractMatch ? contractMatch[1] : null,
      }),
      keepalive: true,
    }).catch(() => {
      /* never surface logging failures to the user */
    });
  }, [pathname]);

  return null;
}
