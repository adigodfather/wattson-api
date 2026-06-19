"use client";

// Header unificat — UN SINGUR component refolosit pe toate paginile (consistenta).
// Logo ZYNAPSE -> /home (identic peste tot), nav cu stare ACTIVA, Z-Coins, Deconectare distincta (rosu).
// Stilizare (impeccable / registru product): vocabular consistent, stari default/hover/focus/active,
// tranzitii 150ms care comunica stare, accent doar pe pagina curenta, accesibil (aria-current), reduced-motion.
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/components/auth-provider";

const NAV = [
  { href: "/home", label: "Home" },
  { href: "/projects", label: "Proiectele mele" },
  { href: "/settings", label: "Setări firmă" },
];

export default function AppHeader({ rightExtra }: { rightExtra?: React.ReactNode }) {
  const { user, profile, loading, signOut } = useAuth();
  const pathname = usePathname() || "";
  const links = profile?.is_admin === true ? [...NAV, { href: "/admin", label: "Admin" }] : NAV;
  const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/");

  return (
    <header className="zh-header">
      <style>{`
        .zh-header {
          position: sticky; top: 0; z-index: 50;
          display: flex; align-items: center; justify-content: space-between; gap: 12px;
          padding: 12px 18px;
          background: rgba(10,11,14,0.85);
          border-bottom: 1px solid rgba(255,255,255,0.06);
          backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
          font-family: 'DM Sans', system-ui, sans-serif;
        }
        .zh-left, .zh-right { display: flex; align-items: center; gap: 10px; min-width: 0; }
        .zh-logo { display: flex; align-items: center; gap: 9px; text-decoration: none; flex-shrink: 0; }
        .zh-logo span {
          font-size: 20px; font-weight: 700; letter-spacing: 1.5px; line-height: 1;
          background: linear-gradient(120deg,#378ADD 0%,#5BB8F5 35%,#CDEBFF 50%,#5BB8F5 65%,#378ADD 100%);
          -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
          filter: drop-shadow(0 0 8px rgba(91,184,245,0.4));
        }
        .zh-beta {
          display: none; font-size: 10px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase;
          padding: 3px 7px; border-radius: 6px;
          background: rgba(55,138,221,0.12); color: #5BB8F5; border: 1px solid rgba(55,138,221,0.2);
        }
        .zh-divider { width: 1px; height: 20px; background: rgba(255,255,255,0.08); flex-shrink: 0; }
        .zh-nav { display: none; align-items: center; gap: 4px; }
        .zh-link {
          font-size: 13.5px; font-weight: 500; color: #8B8FA8; text-decoration: none;
          padding: 7px 12px; border-radius: 9px; white-space: nowrap;
          transition: color .15s ease, background-color .15s ease;
        }
        .zh-link:hover { color: #E2E4E9; background: rgba(255,255,255,0.05); }
        .zh-link:focus-visible { outline: 2px solid rgba(91,184,245,0.6); outline-offset: 1px; }
        .zh-link[data-active="true"] { color: #5BB8F5; background: rgba(55,138,221,0.12); font-weight: 600; }
        .zh-cta {
          font-size: 13.5px; font-weight: 600; color: #fff; text-decoration: none; white-space: nowrap;
          padding: 8px 16px; border-radius: 9px; margin-left: 4px;
          background: linear-gradient(135deg,#378ADD,#5BB8F5); transition: filter .15s ease;
        }
        .zh-cta:hover { filter: brightness(1.08); }
        .zh-cta:focus-visible { outline: 2px solid rgba(91,184,245,0.6); outline-offset: 2px; }
        .zh-name { font-size: 13.5px; color: #8B8FA8; white-space: nowrap; overflow: hidden;
          text-overflow: ellipsis; max-width: 150px; }
        .zh-coins {
          display: inline-flex; align-items: center; gap: 6px; padding: 6px 11px; border-radius: 9px;
          font-size: 13.5px; font-weight: 600; color: #E2E4E9; white-space: nowrap; flex-shrink: 0;
          background: rgba(55,138,221,0.08); border: 1px solid rgba(55,138,221,0.2);
        }
        .zh-logout {
          font-family: inherit; font-size: 13.5px; font-weight: 600; cursor: pointer; flex-shrink: 0;
          padding: 7px 13px; border-radius: 9px;
          color: #F09595; background: rgba(226,75,74,0.10); border: 1px solid rgba(226,75,74,0.28);
          transition: background-color .15s ease, color .15s ease, border-color .15s ease;
        }
        .zh-logout:hover { background: rgba(226,75,74,0.18); color: #FFC4C4; border-color: rgba(226,75,74,0.45); }
        .zh-logout:focus-visible { outline: 2px solid rgba(226,75,74,0.6); outline-offset: 1px; }
        .zh-burger { position: relative; flex-shrink: 0; }
        .zh-burger > summary {
          list-style: none; cursor: pointer; width: 36px; height: 36px; display: flex;
          align-items: center; justify-content: center; border-radius: 9px; font-size: 16px; user-select: none;
          color: #8B8FA8; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);
        }
        .zh-burger > summary::-webkit-details-marker { display: none; }
        .zh-menu {
          position: absolute; left: 0; top: calc(100% + 8px); z-index: 60;
          display: flex; flex-direction: column; min-width: 190px; padding: 6px; border-radius: 12px;
          background: #14161C; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }
        .zh-menu a { padding: 9px 14px; font-size: 13.5px; font-weight: 500; color: #C8CAD6;
          text-decoration: none; border-radius: 7px; }
        .zh-menu a:hover { background: rgba(255,255,255,0.05); }
        .zh-menu a[data-active="true"] { color: #5BB8F5; background: rgba(55,138,221,0.12); font-weight: 600; }
        @media (min-width: 768px) {
          .zh-header { padding: 12px 28px; }
          .zh-beta { display: inline-flex; }
          .zh-nav { display: flex; }
          .zh-burger { display: none; }
        }
        @media (prefers-reduced-motion: reduce) {
          .zh-link, .zh-logout { transition: none; }
        }
      `}</style>

      <div className="zh-left">
        <Link href="/home" aria-label="Zynapse — acasă" className="zh-logo">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-icon.png" alt="" width={32} height={32}
            style={{ objectFit: "contain", filter: "brightness(2.2) drop-shadow(0 0 6px rgba(91,184,245,0.45))" }} />
          <span>ZYNAPSE</span>
        </Link>
        <span className="zh-beta">Beta</span>

        <nav className="zh-nav" aria-label="Navigare principală">
          <span className="zh-divider" />
          {links.map((l) => (
            <Link key={l.href} href={l.href} className="zh-link"
              data-active={isActive(l.href)} aria-current={isActive(l.href) ? "page" : undefined}>
              {l.label}
            </Link>
          ))}
          <Link href="/configurator" className="zh-cta">Configurator</Link>
        </nav>

        <details className="zh-burger">
          <summary aria-label="Meniu">☰</summary>
          <div className="zh-menu">
            <Link href="/configurator" data-active={isActive("/configurator")}
              aria-current={isActive("/configurator") ? "page" : undefined}>Configurator</Link>
            {links.map((l) => (
              <Link key={l.href} href={l.href} data-active={isActive(l.href)}
                aria-current={isActive(l.href) ? "page" : undefined}>
                {l.label}
              </Link>
            ))}
          </div>
        </details>
      </div>

      <div className="zh-right">
        {rightExtra}
        {user && (
          <>
            <span className="zh-name">{profile?.full_name || user.email}</span>
            <span className="zh-coins" title="Z-Coins disponibile">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/z-coin.svg" alt="" width={18} height={18} style={{ display: "block" }} />
              {loading || !profile ? "—" : (profile.credits_balance ?? 0).toLocaleString("ro-RO")}
              <span className="hidden sm:inline">&nbsp;Z-Coins</span>
            </span>
            <button onClick={signOut} className="zh-logout">Deconectare</button>
          </>
        )}
      </div>
    </header>
  );
}
