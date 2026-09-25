"use client";
// Bariera de eroare a APLICATIEI. Pana acum nu exista niciuna: orice exceptie la randare, oriunde,
// scotea pagina alba a lui Next cu „Application error: a client-side exception has occurred" — un
// text care nu-i spune inginerului nici ce s-a intamplat, nici, mai important, ca proiectul lui e
// intact. Datele sunt in baza; ce cade e desenul.
//
// `PanzaBariera` din plan-editor prinde ce cade IN plan si pastreaza restul ecranului. Asta o prinde
// pe cealalta: orice altceva. Deci nicio exceptie nu mai duce la ecranul gol.
import { useEffect } from "react";

export default function Eroare({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => { console.error("[zynapse] eroare de randare:", error); }, [error]);
  return (
    <div style={{ minHeight: "60vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <div style={{ maxWidth: 560, border: "1px solid #F5A524", borderRadius: 10, background: "#FFFBEB",
                    color: "#7A4F01", padding: 24, fontSize: 15, lineHeight: 1.65 }}>
        <div style={{ fontSize: 17, fontWeight: 700, marginBottom: 8 }}>Ceva nu s-a putut afișa</div>
        <p style={{ margin: "0 0 12px" }}>
          Proiectele și tot ce ai lucrat sunt neatinse — nu s-a pierdut nimic. Reîncarcă pagina;
          dacă se repetă, trimite-ne textul de mai jos.
        </p>
        <button onClick={reset}
                style={{ padding: "8px 16px", borderRadius: 6, border: "1px solid #7A4F01",
                         background: "#7A4F01", color: "#fff", cursor: "pointer", fontSize: 14 }}>
          Încearcă din nou
        </button>
        <code style={{ display: "block", marginTop: 14, fontSize: 12, opacity: 0.85, wordBreak: "break-word" }}>
          {error.message}{error.digest ? ` · ${error.digest}` : ""}
        </code>
      </div>
    </div>
  );
}
