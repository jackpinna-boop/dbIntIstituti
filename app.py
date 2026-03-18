import streamlit as st
import pandas as pd
from io import BytesIO

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from pandas.errors import EmptyDataError, ParserError

st.set_page_config(layout="wide")

st.title("📊 Dashboard Istituti Scolastici")

# ---------------- FUNZIONE LETTURA CSV ----------------
def load_csv(uploaded_file, nome_log="file"):
    if uploaded_file is None:
        st.error(f"Nessun file caricato per {nome_log}.")
        return pd.DataFrame()

    try:
        uploaded_file.seek(0)
        # CSV da Excel/Windows: ; + cp1252
        df = pd.read_csv(uploaded_file, sep=";", encoding="cp1252", engine="python")
        if df.empty:
            st.error(f"{nome_log}: il file è vuoto o non contiene colonne.")
        return df
    except (EmptyDataError, ParserError) as e:
        st.error(f"{nome_log}: problema nel parsing del CSV: {e}")
        return pd.DataFrame()
    except UnicodeDecodeError as e:
        st.error(
            f"{nome_log}: problema di encoding (prova a salvare il CSV in UTF-8 da Excel). "
            f"Dettagli: {e}"
        )
        return pd.DataFrame()
    except Exception as e:
        st.error(f"{nome_log}: errore imprevisto: {e}")
        return pd.DataFrame()


# ---------------- UPLOAD ----------------
file_istituti = st.file_uploader("Carica file ISTITUTI", type="csv")
file_complessi = st.file_uploader("Carica file INTERVENTI", type="csv")

if file_istituti and file_complessi:

    istituti = load_csv(file_istituti, "ISTITUTI")
    complessi = load_csv(file_complessi, "INTERVENTI")

    if istituti.empty or complessi.empty:
        st.stop()

    # ---------------- NORMALIZZO NOMI COLONNE ----------------
    # Mantengo una copia originale e creo anche una versione "pulita" per lavorare
    complessi.columns = complessi.columns.str.strip()
    istituti.columns = istituti.columns.str.strip()

    # Rinomino le colonne chiave dei complessi in nomi "semplici"
    rename_map_complessi = {
        "Determina": "determina",
        "Manutenzioni": "manutenzioni",
        "Nome Istituto": "nome_istituto",
        "Denominazione intervento": "denominazione_intervento",
    }
    complessi = complessi.rename(columns=rename_map_complessi)

    # Per gli istituti assumo che esistano almeno:
    # - Nome Istituto
    # - Comune  (se il CSV ISTITUTI ha nome diverso, adattiamo)
    rename_map_istituti = {
        "Nome Istituto": "nome_istituto",
        "comune": "comune",   # se la colonna si chiama già 'comune' non cambia nulla
        "Comune": "comune",
    }
    istituti = istituti.rename(columns=rename_map_istituti)

    # ---------------- CONTROLLI COLONNE ----------------
    colonne_necessarie_complessi = [
        "determina",
        "manutenzioni",
        "nome_istituto",
        "denominazione_intervento",
    ]
    mancanti_complessi = [c for c in colonne_necessarie_complessi if c not in complessi.columns]
    if mancanti_complessi:
        st.error(f"Nel file INTERVENTI mancano le colonne: {mancanti_complessi}")
        st.write("Colonne INTERVENTI trovate:", list(complessi.columns))
        st.stop()

    colonne_necessarie_istituti = ["nome_istituto", "comune"]
    mancanti_istituti = [c for c in colonne_necessarie_istituti if c not in istituti.columns]
    if mancanti_istituti:
        st.error(f"Nel file ISTITUTI mancano le colonne: {mancanti_istituti}")
        st.write("Colonne ISTITUTI trovate:", list(istituti.columns))
        st.stop()

    # ---------------- NORMALIZZAZIONE ----------------
    complessi["determina_norm"] = complessi["determina"].astype(str).str.strip().str.lower()
    complessi["manut_flag"] = complessi["manutenzioni"].astype(str).str.lower().eq("vero")

    # ---------------- DEDUPLICAZIONE ----------------
    complessi = complessi.drop_duplicates(subset=["determina_norm", "manut_flag"])

    # ---------------- FILTRI ----------------
    st.sidebar.header("🔎 Filtri")

    comuni = sorted(istituti["comune"].dropna().unique())
    filtro_comune = st.sidebar.multiselect("Comune", comuni)

    filtro_manut = st.sidebar.selectbox(
        "Tipo intervento",
        ["Tutti", "Solo manutenzioni", "Solo altri"]
    )

    df = complessi.copy()

    if filtro_comune:
        istituti_filtrati = istituti[istituti["comune"].isin(filtro_comune)]
        df = df[df["nome_istituto"].isin(istituti_filtrati["nome_istituto"])]

    if filtro_manut == "Solo manutenzioni":
        df = df[df["manut_flag"]]
    elif filtro_manut == "Solo altri":
        df = df[~df["manut_flag"]]

    if df.empty:
        st.warning("Nessun intervento corrisponde ai filtri selezionati.")
        st.stop()

    # ---------------- MAPPA ----------------
    st.header("🌍 Mappa istituti")

    mappa_df = istituti.copy()
    # Placeholder coordinate
    mappa_df["lat"] = 41.9
    mappa_df["lon"] = 12.5

    st.map(mappa_df[["lat", "lon"]])

    # ---------------- STATISTICHE GLOBALI ----------------
    st.header("📊 Statistiche globali")

    interventi = df.groupby("nome_istituto").size()

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

    # ---------------- DETTAGLIO ISTITUTO ----------------
    st.header("🏫 Dettaglio istituto")

    istituti_unici = df["nome_istituto"].dropna().unique()
    if len(istituti_unici) == 0:
        st.warning("Nessun istituto disponibile per il dettaglio.")
        st.stop()

    istituto_sel = st.selectbox(
        "Seleziona istituto",
        sorted(istituti_unici)
    )

    if istituto_sel:
        df_sel = df[df["nome_istituto"] == istituto_sel]

        st.subheader(f"📍 {istituto_sel}")

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

        # ---------------- ELENCO INTERVENTI ----------------
        st.subheader("📋 Elenco interventi")

        for _, row in df_sel.iterrows():
            testo = str(row["denominazione_intervento"])
            if row["manut_flag"]:
                testo += " 🟢 Manutenzione"
            st.write(testo)

        # ---------------- PDF ----------------
        def crea_pdf(data, nome):
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer)
            styles = getSampleStyleSheet()

            elements = []
            elements.append(Paragraph(f"Report Istituto: {nome}", styles["Title"]))
            elements.append(Spacer(1, 12))

            for _, row in data.iterrows():
                txt = str(row["denominazione_intervento"])
                if row["manut_flag"]:
                    txt += " (Manutenzione)"
                elements.append(Paragraph(txt, styles["Normal"]))
                elements.append(Spacer(1, 6))

            doc.build(elements)
            buffer.seek(0)
            return buffer

        pdf = crea_pdf(df_sel, istituto_sel)

        st.download_button(
            label="📄 Scarica report PDF",
            data=pdf,
            file_name=f"report_{istituto_sel}.pdf",
            mime="application/pdf"
        )
else:
    st.info("Carica entrambi i file CSV per continuare.")
