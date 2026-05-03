"use client";

import {
  Document, Page, Text, View, StyleSheet, pdf,
} from "@react-pdf/renderer";
import type { ProjectResult, Circuit } from "@/lib/constants";

const BLUE = "#378ADD";
const DARK = "#1A1C23";
const GRAY = "#6B7280";
const LIGHT = "#F5F6FA";

const s = StyleSheet.create({
  page: {
    fontFamily: "Helvetica",
    fontSize: 10,
    color: DARK,
    paddingTop: 40,
    paddingBottom: 64,
    paddingLeft: 50,
    paddingRight: 50,
  },

  // ── Header ──────────────────────────────────────────────────────────────
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 20,
    paddingBottom: 12,
    borderBottomWidth: 2,
    borderBottomColor: BLUE,
    borderBottomStyle: "solid",
  },
  headerBrand: { flexDirection: "row", alignItems: "center" },
  logoBox: {
    width: 28, height: 28,
    backgroundColor: BLUE, borderRadius: 4,
    justifyContent: "center", alignItems: "center",
  },
  logoChar: { color: "#fff", fontSize: 16, fontFamily: "Helvetica-Bold" },
  brandName: { fontSize: 14, fontFamily: "Helvetica-Bold", color: BLUE, marginLeft: 8 },
  docTitle: { fontSize: 11, fontFamily: "Helvetica-Bold", color: DARK, textAlign: "right" },
  docDate:  { fontSize: 8, color: GRAY, marginTop: 3, textAlign: "right" },

  // ── Section heading ──────────────────────────────────────────────────────
  heading: {
    fontSize: 10,
    fontFamily: "Helvetica-Bold",
    color: "#fff",
    backgroundColor: BLUE,
    paddingVertical: 5,
    paddingHorizontal: 8,
    marginTop: 16,
    marginBottom: 6,
  },

  // ── Key-value rows ───────────────────────────────────────────────────────
  kv: {
    flexDirection: "row",
    paddingVertical: 3,
    borderBottomWidth: 1,
    borderBottomColor: "#E8EAEF",
    borderBottomStyle: "solid",
  },
  kvLabel: { width: 180, color: GRAY },
  kvValue: { flex: 1, fontFamily: "Helvetica-Bold" },

  // ── Memoriu text ─────────────────────────────────────────────────────────
  memBox: {
    backgroundColor: LIGHT,
    borderRadius: 3,
    padding: 10,
    marginTop: 4,
  },
  memText: {
    fontFamily: "Courier",
    fontSize: 8,
    color: "#3A4050",
    lineHeight: 1.55,
  },

  // ── Table ────────────────────────────────────────────────────────────────
  tHeader: { flexDirection: "row", backgroundColor: BLUE, paddingVertical: 5 },
  tRow: {
    flexDirection: "row",
    paddingVertical: 4,
    borderBottomWidth: 1,
    borderBottomColor: "#E8EAEF",
    borderBottomStyle: "solid",
  },
  tAlt: { backgroundColor: LIGHT },
  th:     { fontSize: 9, fontFamily: "Helvetica-Bold", color: "#fff", paddingHorizontal: 6 },
  td:     { fontSize: 9, paddingHorizontal: 6 },
  tdMono: { fontFamily: "Courier", fontSize: 8, color: GRAY, paddingHorizontal: 6 },

  // ── BOM sub-label ────────────────────────────────────────────────────────
  bomLabel: { fontSize: 10, fontFamily: "Helvetica-Bold", marginTop: 14, marginBottom: 4 },

  // ── Footer (fixed — repeats every page) ─────────────────────────────────
  footer: {
    position: "absolute",
    bottom: 24, left: 50, right: 50,
    flexDirection: "row",
    justifyContent: "space-between",
    borderTopWidth: 1,
    borderTopColor: "#E0E3EF",
    borderTopStyle: "solid",
    paddingTop: 6,
  },
  footerText: { fontSize: 8, color: GRAY },
});

const COL = { id: 70, usage: 210, mcb: 55 };

function CircuitTablePDF({ circuits }: { circuits: Circuit[] }) {
  return (
    <View style={{ marginTop: 4 }}>
      <View style={s.tHeader}>
        <Text style={[s.th, { width: COL.id }]}>ID Circuit</Text>
        <Text style={[s.th, { width: COL.usage }]}>Utilizare</Text>
        <Text style={[s.th, { width: COL.mcb }]}>Protecție</Text>
        <Text style={[s.th, { flex: 1 }]}>Cablu</Text>
      </View>
      {circuits.map((c, i) => (
        <View key={i} style={[s.tRow, i % 2 === 1 ? s.tAlt : {}]}>
          <Text style={[s.tdMono, { width: COL.id }]}>{c.id}</Text>
          <Text style={[s.td,     { width: COL.usage }]}>{c.usage}</Text>
          <Text style={[s.td,     { width: COL.mcb }]}>{c.breaker_a}A</Text>
          <Text style={[s.tdMono, { flex: 1 }]}>{c.cable}</Text>
        </View>
      ))}
    </View>
  );
}

function buildBOM(circuits: Circuit[]) {
  const cables: Record<string, number> = {};
  const breakers: Record<string, number> = {};
  for (const c of circuits) {
    if (c.cable && c.cable !== "—") cables[c.cable] = (cables[c.cable] ?? 0) + 1;
    if (c.breaker_a) {
      const k = `MCB ${c.breaker_a}A`;
      breakers[k] = (breakers[k] ?? 0) + 1;
    }
  }
  return { cables, breakers };
}

function Footer() {
  return (
    <View style={s.footer} fixed>
      <Text style={s.footerText}>
        Generat automat de Zynapse.org — verificat de inginer proiectant
      </Text>
      <Text style={s.footerText} render={({ pageNumber, totalPages }) =>
        `Pagina ${pageNumber} / ${totalPages}`
      } />
    </View>
  );
}

function ProjectPDF({ result }: { result: ProjectResult }) {
  const date = new Date().toLocaleDateString("ro-RO", {
    year: "numeric", month: "long", day: "numeric",
  });
  const allCircuits = [
    ...(result.circuits_te_ct ?? []),
    ...(result.circuits_teg ?? []),
  ];
  const { cables, breakers } = buildBOM(allCircuits);

  const generalRows: [string, string][] = [
    ["Proiect", result.project_id],
    ["Zona climatică", `${result.climate_zone || "II"} conform C107/2005`],
    ...(result.levels_string ? [["Regim înălțime", result.levels_string] as [string, string]] : []),
    ["Circuite totale", String(result.circuits_all?.length ?? 0)],
    ["Camere identificate", String(result.rooms?.length ?? 0)],
    ...(result.heating_circuits?.pdc ? ([
      ["Putere termică PDC",  `${result.heating_circuits.pdc.power_kw_thermal} kW`],
      ["Putere electrică PDC", `${result.heating_circuits.pdc.power_kw_electric} kW`],
      ["Protecție PDC", `MCB ${result.heating_circuits.pdc.breaker_a}A — ${result.heating_circuits.pdc.cable}`],
    ] as [string, string][]) : []),
  ];

  return (
    <Document title={`Memoriu tehnic — ${result.project_id}`} author="Zynapse">
      <Page size="A4" style={s.page}>
        <Footer />

        {/* Header */}
        <View style={s.header}>
          <View style={s.headerBrand}>
            <View style={s.logoBox}><Text style={s.logoChar}>Z</Text></View>
            <Text style={s.brandName}>Zynapse</Text>
          </View>
          <View>
            <Text style={s.docTitle}>MEMORIU TEHNIC — INSTALAȚIE ELECTRICĂ</Text>
            <Text style={s.docDate}>Generat: {date}</Text>
          </View>
        </View>

        {/* 1. Date generale */}
        <Text style={s.heading}>1. DATE GENERALE</Text>
        <View>
          {generalRows.map(([label, value], i) => (
            <View key={i} style={s.kv}>
              <Text style={s.kvLabel}>{label}</Text>
              <Text style={s.kvValue}>{value}</Text>
            </View>
          ))}
        </View>

        {/* 2. Memoriu tehnic */}
        <Text style={s.heading}>2. MEMORIU TEHNIC</Text>
        <View style={s.memBox}>
          <Text style={s.memText}>{result.memoriu_tehnic}</Text>
        </View>

        {/* Force page break before tables */}
        <View break />

        {/* 3. TE-CT */}
        {(result.circuits_te_ct?.length ?? 0) > 0 && (
          <View>
            <Text style={s.heading}>3. CIRCUITE TE-CT — CAMERĂ TEHNICĂ</Text>
            <CircuitTablePDF circuits={result.circuits_te_ct} />
          </View>
        )}

        {/* 4. TEG */}
        {(result.circuits_teg?.length ?? 0) > 0 && (
          <View>
            <Text style={s.heading}>4. CIRCUITE TEG — TABLOU GENERAL</Text>
            <CircuitTablePDF circuits={result.circuits_teg} />
          </View>
        )}

        {/* 5. BOM */}
        <Text style={s.heading}>5. LISTA DE CANTITĂȚI (BOM)</Text>

        {Object.keys(cables).length > 0 && (
          <View>
            <Text style={s.bomLabel}>Cabluri și conductori</Text>
            <View style={{ marginTop: 4 }}>
              <View style={s.tHeader}>
                <Text style={[s.th, { flex: 1 }]}>Tip cablu</Text>
                <Text style={[s.th, { width: 80 }]}>Nr. circuite</Text>
              </View>
              {Object.entries(cables).map(([cable, count], i) => (
                <View key={i} style={[s.tRow, i % 2 === 1 ? s.tAlt : {}]}>
                  <Text style={[s.tdMono, { flex: 1 }]}>{cable}</Text>
                  <Text style={[s.td, { width: 80 }]}>{count}</Text>
                </View>
              ))}
            </View>
          </View>
        )}

        {Object.keys(breakers).length > 0 && (
          <View>
            <Text style={s.bomLabel}>Aparataj de protecție</Text>
            <View style={{ marginTop: 4 }}>
              <View style={s.tHeader}>
                <Text style={[s.th, { flex: 1 }]}>Tip protecție</Text>
                <Text style={[s.th, { width: 80 }]}>Cantitate</Text>
              </View>
              {Object.entries(breakers).map(([breaker, count], i) => (
                <View key={i} style={[s.tRow, i % 2 === 1 ? s.tAlt : {}]}>
                  <Text style={[s.td, { flex: 1 }]}>{breaker}</Text>
                  <Text style={[s.td, { width: 80 }]}>{count}</Text>
                </View>
              ))}
            </View>
          </View>
        )}
      </Page>
    </Document>
  );
}

export async function downloadProjectPDF(result: ProjectResult): Promise<void> {
  const blob = await pdf(<ProjectPDF result={result} />).toBlob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${result.project_id || "proiect"}_memoriu.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}
