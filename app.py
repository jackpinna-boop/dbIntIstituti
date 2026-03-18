import streamlit as st
import pandas as pd
from io import BytesIO

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from pandas.errors import EmptyDataError, ParserError

# -------------------------------------------------------
# CONFIGURAZIONE BASE
# -------------------------------------------------------
st.set_page_config(layout="wide", page_title="Dashboard Interventi – Prov. Sulcis Iglesiente")

st.title("📊 Dashboard Interventi Istituti Scolastici")
st.caption("Provincia del Sulcis Iglesiente – interventi e manutenzioni sugli istituti scolastici")


# -------------------------------------------------------
# LETTURA CSV CARICATO (ISTITUTI / INTERVENTI)
# -------------------------------------------------------
def load_uploaded_csv(uploaded_file, nome_log="file"):
    if uploaded_file is None:
        st.error(f"Nessun file caricato per {nome_log}.")
        return pd.DataFrame()

    # 1) UTF-8
    try:
        uploaded_file.seek(0)
        df = pd.read_csv(
            uploaded_file,
            sep=";",
            encoding="utf-8",
            engine="python",
        )
        if df.empty:
            st.error(f"{nome_log}: il file è vuoto o non contiene colonne.")
        return df
    except (EmptyDataError, ParserError) as e:
        st.error(f"{nome_log}: problema nel parsing del CSV (UTF-8): {e}")
        return pd.DataFrame()
    except UnicodeDecodeError as e:
        # 2) fallback cp1252
        st.warning(
            f"{nome_log}: errore di encoding con UTF-8, provo cp1252 in fallback. Dettagli: {e}"
        )
        try:
            uploaded_file.seek(0)
            df = pd.read_csv(
                uploaded_file,
                sep=";",
                encoding="cp1252",
                engine="python",
            )
            if df.empty:
                st.error(f"{nome_log}: il file è vuoto o non contiene colonne (cp1252).")
            return df
        except Exception as e2:
            st.error(f"{nome_log}: anche il fallback cp1252 fallisce: {e2}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"{nome_log}: errore imprevisto: {e}")
        return pd.DataFrame()


# -------------------------------------------------------
# UPLOAD FILE
# -------------------------------------------------------
st.sidebar.subheader("📂 Caricamento dati")
file_istituti = st.sidebar.file_uploader("File ISTITUTI", type="csv", key="upload_istituti")
file_interventi = st.sidebar.file_uploader("File INTERVENTI", type="csv", key="upload_interventi")

if not file_istituti or not file_interventi:
    st.info("Carica entrambi i file CSV (ISTITUTI e INTERVENTI) per visualizzare la dashboard.")
    st.stop()

istituti = load_uploaded_csv(file_istituti, "ISTITUTI")
interventi = load_uploaded_csv(file_interventi, "INTERVENTI")

if istituti.empty or interventi.empty:
    st.stop()

istituti.columns = istituti.columns.str.strip()
interventi.columns = interventi.columns.str.strip()

# -------------------------------------------------------
# RINOMINO COLONNE
# -------------------------------------------------------
rename_map_istituti = {
    "Denominazione Immobile": "nome_istituto",
    "Localizzazione immobile": "indirizzo",
    "Comune": "comune",
    "comune": "comune",
}
istituti = istituti.rename(columns=rename_map_istituti)

rename_map_interventi = {
    "Determina": "determina",
    "Manutenzioni": "manutenzioni",
    "Nome Istituto": "nome_istituto",
    "Denominazione intervento": "denominazione_intervento",
    "importo stanziato": "importo_stanziato",
    "importo stimato": "importo_stimato",
    "Tipologia di intervento": "tipologia_intervento",
}
interventi = interventi.rename(columns=rename_map_interventi)

if "tipologia_intervento" not in interventi.columns:
    interventi["tipologia_intervento"] = "Non specificata"

# -------------------------------------------------------
# CONTROLLI COLONNE
# -------------------------------------------------------
colonne_necessarie_interventi = [
    "determina",
    "manutenzioni",
    "nome_istituto",
    "denominazione_intervento",
    "tipologia_intervento",
]
mancanti_interventi = [c for c in colonne_necessarie_interventi if c not in interventi.columns]
if mancanti_interventi:
    st.error(f"Nel file INTERVENTI mancano le colonne: {mancanti_interventi}")
    st.write("Colonne INTERVENTI trovate:", list(interventi.columns))
    st.stop()

colonne_necessarie_istituti = ["nome_istituto", "comune"]
mancanti_istituti = [c for c in colonne_necessarie_istituti if c not in istituti.columns]
if mancanti_istituti:
    st.error(f"Nel file ISTITUTI mancano le colonne: {mancanti_istituti}")
    st.write("Colonne ISTITUTI trovate:", list(istituti.columns))
    st.stop()

# -------------------------------------------------------
# NORMALIZZAZIONE / IMPORTI EURO
# -------------------------------------------------------
interventi["determina_norm"] = (
    interventi["determina"].astype(str).str.strip().str.lower()
)
interventi["manut_flag"] = interventi["manutenzioni"].astype(str).str.lower().eq("vero")

for col_imp in ["importo_stanziato", "importo_stimato"]:
    if col_imp in interventi.columns:
        interventi[col_imp] = (
            interventi[col_imp]
            .astype(str)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
        )
        interventi[col_imp] = pd.to_numeric(interventi[col_imp], errors="coerce")

interventi = interventi.drop_duplicates(subset=["determina_norm", "manut_flag"])

# -------------------------------------------------------
# NAVIGAZIONE INTERNA (HOME + ISTITUTI)
# -------------------------------------------------------
lista_pagine = ["Home"]
istituti_ordinati = sorted(interventi["nome_istituto"].dropna().unique())
lista_pagine.extend(istituti_ordinati)

st.sidebar.subheader("🧭 Navigazione")
pagina = st.sidebar.radio("Vai a", lista_pagine, key="nav_radio")


# -------------------------------------------------------
# FILTRI GLOBALI (Comune, tipologia, manutenzioni)
# -------------------------------------------------------
st.sidebar.subheader("🔎 Filtri globali")

lista_tipologie = sorted(interventi["tipologia_intervento"].dropna().unique())
filtro_tipologia = st.sidebar.multiselect("Tipologia di intervento", lista_tipologie)

opzioni_manut = ["Tutti", "Solo manutenzioni", "Solo altri"]
filtro_manut = st.sidebar.selectbox("Manutenzioni", opzioni_manut)

lista_comuni = sorted(istituti["comune"].dropna().unique())
filtro_comune = st.sidebar.multiselect("Comune (Provincia del Sulcis Iglesiente)", lista_comuni)

df = interventi.copy()

if filtro_tipologia:
    df = df[df["tipologia_intervento"].isin(filtro_tipologia)]

if filtro_manut == "Solo manutenzioni":
    df = df[df["manut_flag"]]
elif filtro_manut == "Solo altri":
    df = df[~df["manut_flag"]]

if filtro_comune:
    ist_filtrati = istituti[istituti["comune"].isin(filtro_comune)]
    df = df[df["nome_istituto"].isin(ist_filtrati["nome_istituto"])]

df = df.merge(
    istituti[["nome_istituto", "comune", "indirizzo"]],
    on="nome_istituto",
    how="left",
)

if df.empty:
    st.warning("Nessun intervento corrisponde ai filtri selezionati.")
    st.stop()


# -------------------------------------------------------
# PAGINA HOME
# -------------------------------------------------------
if pagina == "Home":
    st.header("🏠 Dashboard generale – Provincia del Sulcis Iglesiente")

    st.subheader("Elenco interventi (filtrati)")
    colonne_tab = [
        "nome_istituto",
        "comune",
        "tipologia_intervento",
        "manutenzioni",
        "denominazione_intervento",
        "determina",
    ]
    if "importo_stanziato" in df.columns:
        colonne_tab.append("importo_stanziato")
    if "importo_stimato" in df.columns:
        colonne_tab.append("importo_stimato")

    column_config = {}
    if "importo_stimato" in df.columns:
        column_config["importo_stimato"] = st.column_config.NumberColumn(
            "Importo stimato",
            format="€ %,.2f",
        )
    if "importo_stanziato" in df.columns:
        column_config["importo_stanziato"] = st.column_config.NumberColumn(
            "Importo stanziato",
            format="€ %,.2f",
        )

    st.dataframe(
        df[colonne_tab],
        use_container_width=True,
        column_config=column_config if column_config else None,
    )

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.subheader("Numero interventi per istituto")
        conteggio_istituti = df.groupby("nome_istituto").size()
        st.bar_chart(conteggio_istituti)

    with col_g2:
        st.subheader("Manutenzioni vs altri interventi")
        n_manut = df[df["manut_flag"]].shape[0]
        n_altri = df.shape[0] - n_manut
        pie_df = pd.DataFrame(
            {"Tipo": ["Manutenzioni", "Altri"], "Valore": [n_manut, n_altri]}
        ).set_index("Tipo")
        st.bar_chart(pie_df)

    st.subheader("💶 Riepilogo economico (importo stimato)")

    if "importo_stimato" in df.columns:
        col_e1, col_e2 = st.columns(2)

        with col_e1:
            st.markdown("**Somma importi stimati per istituto**")
            somma_ist = (
                df.groupby("nome_istituto")["importo_stimato"]
                .sum()
                .sort_values(ascending=False)
            )
            st.dataframe(
                somma_ist.to_frame("Importo stimato (€)").style.format(
                    {"Importo stimato (€)": "€ {:,.2f}".format}
                ),
                use_container_width=True,
            )

        with col_e2:
            st.markdown("**Somma importi stimati per tipologia**")
            somma_tip = (
                df.groupby("tipologia_intervento")["importo_stimato"]
                .sum()
                .sort_values(ascending=False)
            )
            st.dataframe(
                somma_tip.to_frame("Importo stimato (€)").style.format(
                    {"Importo stimato (€)": "€ {:,.2f}".format}
                ),
                use_container_width=True,
            )
    else:
        st.info("Colonna 'importo stimato' non presente: riepilogo economico non calcolato.")

# -------------------------------------------------------
# PAGINE ISTITUTO
# -------------------------------------------------------
else:
    istituto_sel = pagina
    df_ist = df[df["nome_istituto"] == istituto_sel]

    st.header(f"🏫 {istituto_sel} – Provincia del Sulcis Iglesiente")

    row_ist = istituti[istituti["nome_istituto"] == istituto_sel].head(1)
    if not row_ist.empty:
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.markdown(f"**Comune:** {row_ist.iloc[0].get('comune', '')}")
        with col_info2:
            st.markdown(f"**Indirizzo:** {row_ist.iloc[0].get('indirizzo', '')}")

    st.subheader("📋 Interventi (tutti)")

    colonne_base = [
        "tipologia_intervento",
        "manutenzioni",
        "denominazione_intervento",
        "determina",
    ]
    if "importo_stanziato" in df_ist.columns:
        colonne_base.append("importo_stanziato")
    if "importo_stimato" in df_ist.columns:
        colonne_base.append("importo_stimato")

    column_config_ist = {}
    if "importo_stimato" in df_ist.columns:
        column_config_ist["importo_stimato"] = st.column_config.NumberColumn(
            "Importo stimato",
            format="€ %,.2f",
        )
    if "importo_stanziato" in df_ist.columns:
        column_config_ist["importo_stanziato"] = st.column_config.NumberColumn(
            "Importo stanziato",
            format="€ %,.2f",
        )

    st.dataframe(
        df_ist[colonne_base],
        use_container_width=True,
        column_config=column_config_ist if column_config_ist else None,
    )

    st.subheader("🛠️ Interventi di manutenzione")

    df_manut = df_ist[df_ist["manut_flag"]]
    if df_manut.empty:
        st.info("Nessuna manutenzione per questo istituto.")
    else:
        st.dataframe(
            df_manut[colonne_base],
            use_container_width=True,
            column_config=column_config_ist if column_config_ist else None,
        )

    st.subheader("📊 Grafici istituto")

    col_gi1, col_gi2 = st.columns(2)

    with col_gi1:
        st.markdown("**Interventi per tipologia**")
        per_tipo = df_ist.groupby("tipologia_intervento").size()
        st.bar_chart(per_tipo)

    with col_gi2:
        st.markdown("**Manutenzioni vs altri**")
        n_manut_ist = df_ist[df_ist["manut_flag"]].shape[0]
        n_altri_ist = df_ist.shape[0] - n_manut_ist
        pie_ist = pd.DataFrame(
            {"Tipo": ["Manutenzioni", "Altri"], "Valore": [n_manut_ist, n_altri_ist]}
        ).set_index("Tipo")
        st.bar_chart(pie_ist)

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
            if "importo_stimato" in row and pd.notna(row["importo_stimato"]):
                txt += f" – Importo stimato: {row['importo_stimato']:.2f} €"
            elements.append(Paragraph(txt, styles["Normal"]))
            elements.append(Spacer(1, 6))

        doc.build(elements)
        buffer.seek(0)
        return buffer

    pdf = crea_pdf(df_ist, istituto_sel)

    st.download_button(
        label="📄 Scarica report PDF istituto",
        data=pdf,
        file_name=f"report_{istituto_sel}.pdf",
        mime="application/pdf",
    )
