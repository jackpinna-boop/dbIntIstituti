import streamlit as st
import pandas as pd
from io import BytesIO

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

st.set_page_config(layout="wide")

st.title("📊 Dashboard Istituti Scolastici")

# Upload
file_istituti = st.file_uploader("Carica file ISTITUTI", type="csv")
file_complessi = st.file_uploader("Carica file INTERVENTI", type="csv")

if file_istituti and file_complessi:
    def load_csv(file):
        try:
            return pd.read_csv(file, sep=';', encoding='utf-8')
        except:
            try:
                return pd.read_csv(file, sep=';', encoding='latin1')
            except:
                return pd.read_csv(file, sep=',', encoding='latin1')

istituti = load_csv(file_istituti)
complessi = load_csv(file_complessi)

    # Normalizzazione
    complessi["determina_norm"] = complessi["determina"].astype(str).str.strip().str.lower()
    complessi["manut_flag"] = complessi["manutenzioni"] == "vero"

    # Deduplicazione
    complessi = complessi.drop_duplicates(subset=["determina_norm", "manut_flag"])

    # ---------------- FILTRI ----------------
    st.sidebar.header("🔎 Filtri")

    comuni = sorted(istituti.get("comune", pd.Series()).dropna().unique())
    filtro_comune = st.sidebar.multiselect("Comune", comuni)

    filtro_manut = st.sidebar.selectbox(
        "Tipo intervento",
        ["Tutti", "Solo manutenzioni", "Solo altri"]
    )

    df = complessi.copy()

    if filtro_comune:
        istituti_filtrati = istituti[istituti["comune"].isin(filtro_comune)]
        df = df[df["nome istituto"].isin(istituti_filtrati["nome istituto"])]

    if filtro_manut == "Solo manutenzioni":
        df = df[df["manut_flag"]]
    elif filtro_manut == "Solo altri":
        df = df[~df["manut_flag"]]

    # ---------------- MAPPA ----------------
    st.header("🌍 Mappa istituti")

    mappa_df = istituti.copy()
    mappa_df["lat"] = 41.9
    mappa_df["lon"] = 12.5

    st.map(mappa_df[["lat", "lon"]])

    # ---------------- GLOBALI ----------------
    st.header("📊 Statistiche globali")

    interventi = df.groupby("nome istituto").size()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Interventi per istituto")
        st.bar_chart(interventi)

    with col2:
        manut = df[df["manut_flag"]].shape[0]
        altri = df.shape[0] - manut

        pie = pd.DataFrame({
            "Tipo": ["Manutenzioni", "Altri"],
            "Valore": [manut, altri]
        }).set_index("Tipo")

        st.subheader("Distribuzione")
        st.bar_chart(pie)

    # ---------------- DETTAGLIO ----------------
    st.header("🏫 Dettaglio istituto")

    istituto_sel = st.selectbox(
        "Seleziona istituto",
        sorted(df["nome istituto"].dropna().unique())
    )

    if istituto_sel:
        df_sel = df[df["nome istituto"] == istituto_sel]

        st.subheader(istituto_sel)

        col1, col2 = st.columns(2)

        with col1:
            st.metric("Numero interventi", len(df_sel))

        with col2:
            manut = df_sel[df_sel["manut_flag"]].shape[0]
            altri = len(df_sel) - manut

            pie = pd.DataFrame({
                "Tipo": ["Manutenzioni", "Altri"],
                "Valore": [manut, altri]
            }).set_index("Tipo")

            st.bar_chart(pie)

        st.subheader("Interventi")

        for _, r in df_sel.iterrows():
            st.write(
                f"{r['denominazione intervento']} "
                + ("🟢 Manutenzione" if r["manut_flag"] else "")
            )

        # PDF
        def crea_pdf(data, nome):
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer)
            styles = getSampleStyleSheet()

            elements = []
            elements.append(Paragraph(f"Report: {nome}", styles['Title']))
            elements.append(Spacer(1, 12))

            for _, row in data.iterrows():
                txt = row["denominazione intervento"]
                if row["manut_flag"]:
                    txt += " (Manutenzione)"
                elements.append(Paragraph(txt, styles['Normal']))
                elements.append(Spacer(1, 6))

            doc.build(elements)
            buffer.seek(0)
            return buffer

        pdf = crea_pdf(df_sel, istituto_sel)

        st.download_button(
            "📄 Scarica PDF",
            pdf,
            file_name=f"report_{istituto_sel}.pdf",
            mime="application/pdf"
        )
