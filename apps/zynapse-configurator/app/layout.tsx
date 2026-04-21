import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Zynapse — Proiectare Electrică Automată",
  description: "Configurator automat de proiecte electrice rezidențiale. Upload planșe, completează formularul, primești proiectul electric complet.",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ro">
      <body>{children}</body>
    </html>
  );
}
