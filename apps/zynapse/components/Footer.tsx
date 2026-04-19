export default function Footer() {
  return (
    <footer className="py-10 px-4" style={{ borderTop: "1px solid var(--border)" }}>
      <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2 font-bold text-sm">
          <span style={{ color: "var(--accent)" }}>⚡</span>
          <span style={{ color: "var(--text)" }}>ZYNAPSE</span>
        </div>
        <p className="text-xs" style={{ color: "var(--muted2)" }}>
          Automatizare proiectare electrică rezidențială · România
        </p>
        <div className="flex gap-4 text-xs" style={{ color: "var(--muted2)" }}>
          <a href="#" className="hover:text-white transition">Termeni</a>
          <a href="#" className="hover:text-white transition">Confidențialitate</a>
          <a href="mailto:contact@zynapse.ro" className="hover:text-white transition">Contact</a>
        </div>
      </div>
    </footer>
  );
}
