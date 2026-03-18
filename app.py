import streamlit as st
import pandas as pd
import re
from io import BytesIO

import requests
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from pandas.errors import EmptyDataError, ParserError

# -------------------------------------------------------
# CONFIGURAZIONE BASE, COLORI E LOGO
# -------------------------------------------------------
st.set_page_config(layout="wide", page_title="Dashboard Interventi – Prov. Sulcis Iglesiente")

LOGO_URL = "https://provincia-sulcis-iglesiente-api.cloud.municipiumapp.it/s3/150x150/s3/20243/sito/stemma.jpg"

PRIMARY_HEX = "#6BE600"
PRIMARY_LIGHT = "#A8FF66"
PRIMARY_EXTRA_LIGHT = "#E8FFE0"

st.markdown(
    f"""
    <style>
    [data-testid="stAppViewContainer"] {{
        background: linear-gradient(135deg, {PRIMARY_EXTRA_LIGHT} 0%, #FFFFFF 40%, {PRIMARY_EXTRA_LIGHT} 100%);
    }}

    .sulcis-main-header {{
        display:flex;
        align-items:center;
        gap:1rem;
        background: linear-gradient(90deg, {PRIMARY_HEX} 0%, {PRIMARY_LIGHT} 50%, {PRIMARY_EXTRA_LIGHT} 100%);
        padding: 0.9rem 1.3rem;
        border-radius: 0.75rem;
        margin-bottom: 1.2rem;
        color: #1E2A10;
        font-weight: 600;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }}
    .sulcis-main-header-text small {{
        display:block;
        font-weight:400;
        opacity:0.9;
        margin-top:0.2rem;
    }}

    .sulcis-card {{
        background: linear-gradient(135deg, #FFFFFF 0%, {PRIMARY_EXTRA_LIGHT} 100%);
        border-radius: 0.75rem;
        padding: 0.9rem 1.1rem;
        margin-bottom: 1rem;
        border: 1px solid rgba(107,230,0,0.25);
    }}

    .sulcis-section-title {{
        font-weight: 600;
        color: #1E2A10;
        margin-bottom: 0.3rem;
    }}

    h1, h2, h3 {{
        margin-top: 0.4rem;
        margin-bottom: 0.4rem;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# Header con logo + testo
col_logo, col_title = st.columns([1, 6])
with col_logo:
    st.image(LOGO_URL, width=70)
with col_title:
    st.markdown(
        """
        <div class="sulcis-main-header">
            <div class="sulcis-main-header-text">
                Dashboard Interventi Istituti Scolastici<br/>
                <small>Provincia del Sulcis Iglesiente – interventi e manutenzioni sugli istituti scolastici</small>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# -------------------------------------------------------
# LETTURA CSV CARICATO (ISTITUTI / INTERVENTI)
# -------------------------------------------------------
def load_uploaded_csv(uploaded_file, nome_log="file"):
    if uploaded_file is None:
        st.error(f"Nessun file caricato per {nome_log}.")
        return pd.DataFrame()

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
file_istituti = st.sidebar.file_uploader("File ISTITUTI (SCU_Istituti-ELE_ISTITUTI-2.csv)", type="csv")
file_interventi = st.sidebar.file_uploader("File INTERVENTI (SCU_Istituti-ELE_CMPLSS.csv)", type="csv")

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
# RINOMINO COLONNE (USANDO 'codice' COME CHIAVE)
# -------------------------------------------------------
rename_map_istituti = {
    "codice": "codice",
    "Denominazione Immobile": "nome_istituto",
    "Localizzazione immobile": "indirizzo",
    "Comune": "comune",
    "comune": "comune",
}
istituti = istituti.rename(columns=rename_map_istituti)

rename_map_interventi = {
    "codice": "codice",
    "Nome Istituto": "nome_istituto_descr",
    "Denominazione intervento": "denominazione_intervento",
    "Determina": "determina",
    "Manutenzioni": "manutenzioni",
    "Tipologia di intervento": "tipologia_intervento",
    "RUP": "rup",
    "importo stanziato": "importo_stanziato",
}
interventi = interventi.rename(columns=rename_map_interventi)

if "tipologia_intervento" not in interventi.columns:
    interventi["tipologia_intervento"] = "Non specificata"

# -------------------------------------------------------
# CONTROLLI COLONNE
# -------------------------------------------------------
colonne_necessarie_ist = ["codice", "nome_istituto", "comune"]
manc_ist = [c for c in colonne_necessarie_ist if c not in istituti.columns]
if manc_ist:
    st.error(f"Nel file ISTITUTI mancano le colonne: {manc_ist}")
    st.write("Colonne ISTITUTI trovate:", list(istituti.columns))
    st.stop()

colonne_necessarie_int = [
    "codice",
    "denominazione_intervento",
    "determina",
    "manutenzioni",
    "tipologia_intervento",
]
manc_int = [c for c in colonne_necessarie_int if c not in interventi.columns]
if manc_int:
    st.error(f"Nel file INTERVENTI mancano le colonne: {manc_int}")
    st.write("Colonne INTERVENTI trovate:", list(interventi.columns))
    st.stop()

# -------------------------------------------------------
# JOIN SU 'codice'
# -------------------------------------------------------
istituti["codice"] = istituti["codice"].astype(str).str.strip()
interventi["codice"] = interventi["codice"].astype(str).str.strip()

df = interventi.merge(
    istituti[["codice", "nome_istituto", "comune", "indirizzo"]],
    on="codice",
    how="left",
)

# -------------------------------------------------------
# NORMALIZZAZIONE FLAG MANUTENZIONI
# -------------------------------------------------------
df["determina_norm"] = df["determina"].astype(str).str.strip().str.lower()
df["manut_flag"] = df["manutenzioni"].astype(str).str.lower().eq("vero")
df["tipologia_intervento"] = df["tipologia_intervento"].astype(str).str.strip()

# NON tocchiamo df qui per i duplicati: la logica specializzata è solo nel riepilogo per tipologia.

# -------------------------------------------------------
# PULIZIA IMPORTI STANZIATI "€ 17.928,80"
# -------------------------------------------------------
def pulisci_importo(val):
    if pd.isna(val):
        return None
    s = str(val)
    s = s.replace("€", "").replace("EUR", "").strip()
    s = re.sub(r"[^\d,.\-]", "", s)
    s = s.replace(".", "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None

if "importo_stanziato" in df.columns:
    df["importo_stanziato"] = df["importo_stanziato"].apply(pulisci_importo)

# -------------------------------------------------------
# NAVIGAZIONE INTERNA
# -------------------------------------------------------
lista_pagine = ["Home"]
istituti_ordinati = sorted(df["nome_istituto"].dropna().unique())
lista_pagine.extend(istituti_ordinati)

st.sidebar.subheader("🧭 Navigazione")
pagina = st.sidebar.radio("Vai a", lista_pagine, key="nav_radio")

# -------------------------------------------------------
# FILTRI GLOBALI
# -------------------------------------------------------
st.sidebar.subheader("🔎 Filtri globali")

lista_tipologie = sorted(df["tipologia_intervento"].dropna().unique())
filtro_tipologia = st.sidebar.multiselect("Tipologia di intervento", lista_tipologie)

opzioni_manut = ["Tutti", "Solo manutenzioni", "Solo altri"]
filtro_manut = st.sidebar.selectbox("Manutenzioni", opzioni_manut)

lista_comuni = sorted(df["comune"].dropna().unique())
filtro_comune = st.sidebar.multiselect("Comune (Provincia del Sulcis Iglesiente)", lista_comuni)

df_filt = df.copy()

if filtro_tipologia:
    df_filt = df_filt[df_filt["tipologia_intervento"].isin(filtro_tipologia)]

if filtro_manut == "Solo manutenzioni":
    df_filt = df_filt[df_filt["manut_flag"]]
elif filtro_manut == "Solo altri":
    df_filt = df_filt[~df_filt["manut_flag"]]

if filtro_comune:
    df_filt = df_filt[df_filt["comune"].isin(filtro_comune)]

if df_filt.empty:
    st.warning("Nessun intervento corrisponde ai filtri selezionati.")
    st.stop()

# -------------------------------------------------------
# PAGINA HOME
# -------------------------------------------------------
if pagina == "Home":
    st.markdown('<div class="sulcis-card">', unsafe_allow_html=True)
    st.markdown('<div class="sulcis-section-title">🏠 Dashboard generale – Provincia del Sulcis Iglesiente</div>', unsafe_allow_html=True)

    st.subheader("Elenco interventi (filtrati)")

    colonne_tab = [
        "nome_istituto",
        "codice",
        "comune",
        "tipologia_intervento",
        "manutenzioni",
        "rup",
        "denominazione_intervento",
        "determina",
    ]
    if "importo_stanziato" in df_filt.columns:
        colonne_tab.append("importo_stanziato")

    column_config = {}
    if "importo_stanziato" in df_filt.columns:
        column_config["importo_stanziato"] = st.column_config.NumberColumn(
            "Importo stanziato",
            format="€ %,.2f",
        )

    st.dataframe(
        df_filt[colonne_tab],
        use_container_width=True,
        column_config=column_config if column_config else None,
    )

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.subheader("Numero interventi per istituto")
        conteggio_istituti = df_filt.groupby("nome_istituto").size()
        st.bar_chart(conteggio_istituti)

    with col_g2:
        st.subheader("Manutenzioni vs altri interventi")
        n_manut = df_filt[df_filt["manut_flag"]].shape[0]
        n_altri = df_filt.shape[0] - n_manut
        pie_df = pd.DataFrame(
            {"Tipo": ["Manutenzioni", "Altri"], "Valore": [n_manut, n_altri]}
        ).set_index("Tipo")
        st.bar_chart(pie_df)

    st.subheader("💶 Riepilogo economico (importo stanziato)")

    if "importo_stanziato" in df_filt.columns:
        col_e1, col_e2 = st.columns(2)

        with col_e1:
            st.markdown("**Somma importi stanziati per istituto**")
            somma_ist = (
                df_filt.groupby("nome_istituto")["importo_stanziato"]
                .sum()
                .sort_values(ascending=False)
                .reset_index()
            )
            somma_ist["Importo stanziato (€)"] = somma_ist["importo_stanziato"].map(
                lambda x: f"€ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            st.dataframe(
                somma_ist[["nome_istituto", "Importo stanziato (€)"]],
                use_container_width=True,
            )

        with col_e2:
            st.markdown("**Somma importi stanziati per tipologia**")

            df_tmp = df_filt.copy()
            df_tmp["tipologia_intervento"] = df_tmp["tipologia_intervento"].astype(str).str.strip()
            df_tmp["determina_norm"] = df_tmp["determina"].astype(str).str.strip().str.lower()

            # Tipologie diverse da Accordo/Servizio: somma normale
            mask_other = ~df_tmp["tipologia_intervento"].str.lower().eq("accordo/servizio")
            somma_other = (
                df_tmp[mask_other]
                .groupby("tipologia_intervento")["importo_stanziato"]
                .sum()
                .reset_index()
            )

            # Accordo/Servizio: somma per determina (una volta per determina) e poi per tipologia
            mask_acc = df_tmp["tipologia_intervento"].str.lower().eq("accordo/servizio")
            df_acc = df_tmp[mask_acc].copy()

            if not df_acc.empty:
                acc_per_det = (
                    df_acc.groupby(["determina_norm", "tipologia_intervento"])["importo_stanziato"]
                    .sum()
                    .reset_index()
                )
                somma_acc = (
                    acc_per_det.groupby("tipologia_intervento")["importo_stanziato"]
                    .sum()
                    .reset_index()
                )
                somma_tip = pd.concat([somma_other, somma_acc], ignore_index=True)
            else:
                somma_tip = somma_other

            somma_tip = somma_tip.sort_values("importo_stanziato", ascending=False).reset_index(drop=True)

            somma_tip["Importo stanziato (€)"] = somma_tip["importo_stanziato"].map(
                lambda x: f"€ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )

            st.dataframe(
                somma_tip[["tipologia_intervento", "Importo stanziato (€)"]],
                use_container_width=True,
            )

        st.markdown("**Somma importi stanziati per manutenzione (VERO/FALSO)**")
        somma_manut = (
            df_filt.groupby("manut_flag")["importo_stanziato"]
            .sum()
            .reset_index()
        )
        somma_manut["manutenzione"] = somma_manut["manut_flag"].map(
            {True: "VERO (manutenzioni)", False: "FALSO (altri interventi)"}
        )
        somma_manut["Importo stanziato (€)"] = somma_manut["importo_stanziato"].map(
            lambda x: f"€ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )
        st.dataframe(
            somma_manut[["manutenzione", "Importo stanziato (€)"]],
            use_container_width=True,
        )
    else:
        st.info("Colonna 'importo stanziato' non presente: riepilogo economico non calcolato.")

    st.markdown('</div>', unsafe_allow_html=True)

# -------------------------------------------------------
# PAGINE ISTITUTO
# -------------------------------------------------------
else:
    istituto_sel = pagina
    df_ist = df_filt[df_filt["nome_istituto"] == istituto_sel]

    st.markdown('<div class="sulcis-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="sulcis-section-title">🏫 {istituto_sel} – Provincia del Sulcis Iglesiente</div>', unsafe_allow_html=True)

    row_ist = istituti[istituti["nome_istituto"] == istituto_sel].head(1)
    if not row_ist.empty:
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.markdown(f"**Comune:** {row_ist.iloc[0].get('comune', '')}")
        with col_info2:
            st.markdown(f"**Indirizzo:** {row_ist.iloc[0].get('indirizzo', '')}")

    # 1) INTERVENTI (TUTTI)
    st.subheader("📋 Interventi (tutti)")

    colonne_base = [
        "tipologia_intervento",
        "manutenzioni",
        "rup",
        "denominazione_intervento",
        "determina",
    ]
    if "importo_stanziato" in df_ist.columns:
        colonne_base.append("importo_stanziato")

    column_config_ist = {}
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

    # 2) INTERVENTI DI MANUTENZIONE (VERO)
    st.subheader("🛠️ Interventi di manutenzione (VERO)")

    df_manut = df_ist[df_ist["manut_flag"]]
    if df_manut.empty:
        st.info("Nessuna manutenzione per questo istituto.")
    else:
        st.dataframe(
            df_manut[colonne_base],
            use_container_width=True,
            column_config=column_config_ist if column_config_ist else None,
        )

    # 3) INTERVENTI NON DI MANUTENZIONE (FALSO / altro)
    st.subheader("📋 Interventi diversi dalle manutenzioni (FALSO)")

    df_non_manut = df_ist[~df_ist["manut_flag"]]
    if df_non_manut.empty:
        st.info("Nessun intervento non di manutenzione per questo istituto.")
    else:
        st.dataframe(
            df_non_manut[colonne_base],
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

    # ---------------------------------------------------
    # PDF COMPLETO PER ISTITUTO (importo stanziato + RUP + LOGO)
    # ---------------------------------------------------
    def crea_pdf(data, nome):
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()

        elements = []

        # Logo dal URL
        try:
            resp = requests.get(LOGO_URL, timeout=5)
            if resp.status_code == 200:
                logo_buf = BytesIO(resp.content)
                logo = RLImage(logo_buf, width=40, height=40)
                elements.append(logo)
                elements.append(Spacer(1, 6))
        except Exception:
            pass

        elements.append(Paragraph(f"Report Istituto: {nome}", styles["Title"]))
        elements.append(Paragraph("Provincia del Sulcis Iglesiente", styles["Normal"]))
        elements.append(Spacer(1, 12))

        n_tot = len(data)
        n_manut = data[data["manut_flag"]].shape[0]
        n_altri = n_tot - n_manut
        elements.append(
            Paragraph(
                f"Interventi totali: {n_tot} – Manutenzioni: {n_manut} – Altri interventi: {n_altri}",
                styles["Normal"],
            )
        )
        elements.append(Spacer(1, 12))

        if "importo_stanziato" in data.columns:
            somma_manut = data[data["manut_flag"]]["importo_stanziato"].sum()
            somma_altri = data[~data["manut_flag"]]["importo_stanziato"].sum()
            somma_tot = data["importo_stanziato"].sum()
            txt_econ = (
                f"Importo stanziato totale: € {somma_tot:,.2f} "
                f"(Manutenzioni: € {somma_manut:,.2f} – Altri: € {somma_altri:,.2f})"
            )
            txt_econ = txt_econ.replace(",", "X").replace(".", ",").replace("X", ".")
            elements.append(Paragraph(txt_econ, styles["Normal"]))
            elements.append(Spacer(1, 12))

        header_style = styles["Heading5"]
        cell_style = styles["Normal"]
        cell_style.fontSize = 8

        headers = [
            Paragraph("Tipologia", header_style),
            Paragraph("Manut.", header_style),
            Paragraph("RUP", header_style),
            Paragraph("Intervento", header_style),
            Paragraph("Determina", header_style),
            Paragraph("Importo stanziato", header_style),
        ]
        table_data = [headers]

        for _, row in data.iterrows():
            tip = Paragraph(str(row["tipologia_intervento"]), cell_style)
            manut = Paragraph("Sì" if row["manut_flag"] else "No", cell_style)
            rup = Paragraph(str(row.get("rup", "")), cell_style)
            descr = Paragraph(str(row["denominazione_intervento"]), cell_style)
            det = Paragraph(str(row["determina"]), cell_style)
            if "importo_stanziato" in row and pd.notna(row["importo_stanziato"]):
                imp = row["importo_stanziato"]
                imp_txt = f"€ {imp:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            else:
                imp_txt = "-"
            imp_par = Paragraph(imp_txt, cell_style)
            table_data.append([tip, manut, rup, descr, det, imp_par])

        t = Table(
            table_data,
            repeatRows=1,
            colWidths=[65, 30, 60, 200, 90, 80],
        )
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("ALIGN", (1, 1), (1, -1), "CENTER"),
                    ("ALIGN", (2, 1), (2, -1), "LEFT"),
                    ("ALIGN", (5, 1), (5, -1), "RIGHT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ]
            )
        )

        elements.append(t)

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

    st.markdown('</div>', unsafe_allow_html=True)
