from datetime import datetime
import streamlit as st
import pandas as pd
import numpy as np
import locale
import os
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Locale FR
try:
    locale.setlocale(locale.LC_TIME, "fr_FR.UTF-8")
except:
    pass

st.set_page_config(page_title="Dashboard Tour Eiffel", layout="wide")
st.title("📊 Dashboard CA - Boutique Tour Eiffel")

# Authentification Google
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
creds = None
if os.path.exists('token.json'):
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
        creds = flow.run_local_server(port=0)
    with open('token.json', 'w') as token:
        token.write(creds.to_json())

service = build('sheets', 'v4', credentials=creds)

spreadsheet_id = "1dFbeHZLdT9KntpWfbzQduLV08jKEGvQBkCbg5DCphqo"

# Lecture dynamique des feuilles depuis le Google Sheet
spreadsheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
noms_onglets = [s['properties']['title'].upper() for s in spreadsheet_metadata['sheets']]

# Liste des mois dans l'ordre
mois_valides = [
    "JANVIER", "FEVRIER", "MARS", "AVRIL", "MAI", "JUIN",
    "JUILLET", "AOUT", "SEPTEMBRE", "OCTOBRE", "NOVEMBRE", "DECEMBRE"
]

# On filtre les mois présents dans le Google Sheet
mois_disponibles = [m for m in mois_valides if m in noms_onglets]

# Mois actuel
mois_actuel = datetime.now().strftime("%B").upper()

# Déterminer l’index par défaut
index_defaut = mois_disponibles.index(mois_actuel) if mois_actuel in mois_disponibles else len(mois_disponibles) - 1

# Sélecteur Streamlit avec le mois courant sélectionné par défaut
mois = st.sidebar.selectbox("🗓️ Sélectionne un mois", mois_disponibles, index=index_defaut)


range_name = f"{mois}!A1:AH"

try:
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueRenderOption='FORMATTED_VALUE'
    ).execute()

    rows = result.get('values', [])
    raw_headers = rows[0]
    headers = ["PORTRAIT"] + raw_headers[1:]
    data = rows[2:]
    nb_colonnes = len(headers)

    donnees_nettoyees = [
        row + [""] * (nb_colonnes - len(row)) if len(row) < nb_colonnes else row[:nb_colonnes]
        for row in data
    ]

    df = pd.DataFrame(donnees_nettoyees, columns=headers)

    def nettoyer_valeurs(val):
        if isinstance(val, str):
            val = val.replace("€", "").replace(" ", "").replace(",", ".").strip()
        return val

    def nettoyer_pourcentage(val):
        if isinstance(val, str):
            if "#DIV" in val or val.strip() == "":
                return np.nan
            val = val.replace("%", "").replace(",", ".").strip()
        try:
            f = float(val)
            return f if f > 1 else f * 100
        except:
            return np.nan

    jour_cols = [col for col in df.columns if col != "PORTRAIT"]
    for idx, row in df.iterrows():
        portrait = row["PORTRAIT"].strip().upper()
        if portrait == "% VENTE 3D + SOCLES":
            for col in jour_cols:
                df.at[idx, col] = nettoyer_pourcentage(df.at[idx, col])
        elif portrait not in ["TOTAL CAISSE"]:
            for col in jour_cols:
                df.at[idx, col] = nettoyer_valeurs(df.at[idx, col])

    #Categorie de produit
    # Étape 1 – Ajout de la colonne CATEGORIE par lignes fixes (sur df, pas df_montant)
    df["CATEGORIE"] = "AUTRE"

    # Attribution manuelle selon les lignes du df original (basées sur ce que tu vois dans Données brutes)
    categorie_map = {
        "BLOCS + SOCLES": list(range(24, 46)) + list(range(83, 87)),
        "BIJOUX": list(range(92, 99)),
        "EASY": list(range(100, 111))
    }

    for cat, lignes in categorie_map.items():
        df.loc[lignes, "CATEGORIE"] = cat

    # Étape 2 – Nettoyage des valeurs CA
    df_temp = df.copy()
    for col in jour_cols:
        df_temp[col] = pd.to_numeric(df_temp[col], errors="coerce")

    df_temp["total"] = df_temp[jour_cols].sum(axis=1)

    # Étape 3 – On garde les lignes avec un vrai montant
    df_montant = df_temp[df_temp["total"] > 0].drop(columns=["total"])

    # 🏅 Produits les + vendus par catégorie
    df_totaux = df_montant.copy()
    df_totaux["TOTAL"] = df_totaux[jour_cols].sum(axis=1)

    # 🏅 Produits les + vendus par catégorie
    df_totaux = df_montant.copy()
    df_totaux["TOTAL"] = df_totaux[jour_cols].sum(axis=1)

    # Conversion de liste vers dict
    tops = {}
    for cat in ["BLOCS + SOCLES", "BIJOUX", "EASY"]:
        top = df_totaux[df_totaux["CATEGORIE"] == cat].sort_values("TOTAL", ascending=False).head(1)
        if not top.empty:
            produit = top["PORTRAIT"].values[0]
            montant = top["TOTAL"].values[0]
            tops[cat] = (produit, montant)

    # Calcul des totaux
    caisse_mask = df["PORTRAIT"].fillna("").str.strip().str.upper() == "TOTAL CAISSE"
    caisse_row = df[caisse_mask][jour_cols]
    caisse_nettoyees = caisse_row.applymap(lambda v: nettoyer_valeurs(v))
    caisse_nettoyees = caisse_nettoyees.apply(pd.to_numeric, errors="coerce")
    total_caisse = caisse_nettoyees.values.flatten().sum()

    df_no_caisse = df[~caisse_mask].copy()
    for col in jour_cols:
        df_no_caisse[col] = pd.to_numeric(df_no_caisse[col], errors="coerce")
    df.update(df_no_caisse)

    total_ttc_cells = df[df["PORTRAIT"].str.contains("TOTAL TTC", case=False, na=False)][jour_cols]
    total_global = pd.to_numeric(total_ttc_cells.values.flatten(), errors="coerce").sum()

    bijoux_mask = df["PORTRAIT"].fillna("").str.strip().str.upper() == "BIJOUX"
    total_bijoux_cells = df[bijoux_mask][jour_cols]
    total_bijoux_values = pd.to_numeric(total_bijoux_cells.values.flatten(), errors="coerce")
    total_bijoux_series = pd.Series(total_bijoux_values).fillna(0)
    total_bijoux = total_bijoux_series.sum()
    pourcentage_bijoux = (total_bijoux / total_global * 100) if total_global else 0

    easy_mask = df["CATEGORIE"] == "EASY"
    total_easy_values = pd.to_numeric(df[easy_mask][jour_cols].values.flatten(), errors="coerce")
    total_easy = pd.Series(total_easy_values).fillna(0).sum()
    pourcentage_easy = (total_easy / total_global * 100) if total_global else 0

    ca_row = df[df["PORTRAIT"].fillna("").str.strip().str.upper() == "TOTAL TTC"][jour_cols]
    percent_row = df[df["PORTRAIT"].fillna("").str.strip().str.upper() == "% VENTE 3D + SOCLES"][jour_cols]
    if not ca_row.empty and not percent_row.empty:
        ca_values = pd.to_numeric(ca_row.iloc[0], errors="coerce")
        percent_values = pd.to_numeric(percent_row.iloc[0], errors="coerce")
        estimation_jour = ca_values * percent_values / 100
        montant_3d_estime = estimation_jour.sum()
    else:
        montant_3d_estime = 0

    df_ttc = df[df["PORTRAIT"].fillna("").str.strip().str.upper() == "TOTAL TTC"]
    df_long = df_ttc.melt(id_vars=["PORTRAIT"], value_vars=jour_cols, var_name="Jour", value_name="CA")
    df_long["Jour"] = pd.to_datetime(df_long["Jour"], format="%d/%m/%Y", errors="coerce")
    df_long["CA"] = pd.to_numeric(df_long["CA"], errors="coerce")
    df_long = df_long.dropna(subset=["Jour", "CA"])

    # CA quotidien
    st.subheader(f"📈 CA quotidien – {mois}")
    ca_par_jour = df_long.groupby("Jour")["CA"].sum().reset_index()
    ca_par_jour["CA"] = ca_par_jour["CA"].round(0)
    st.line_chart(data=ca_par_jour.set_index("Jour"))

    # Moyenne sur les jours avec CA
    jours_effectifs = df_long[df_long["CA"] > 0]["Jour"].nunique()
    ca_moyen_jours_effectifs = total_global / jours_effectifs if jours_effectifs else 0

    # Bloc CA total, CA moyen, et part bijoux
    top1, top2, top3 = st.columns(3)

    top1.markdown(f"""
        <div style='
            background-color:#e8f5e9;
            border:2px solid #a5d6a7;
            color:#1b5e20;
            padding:18px;
            border-radius:10px;
            text-align:center;
            font-size:20px;
            font-weight:600;
            margin-bottom:25px;
            box-shadow:0 1px 3px rgba(0,0,0,0.05);
        '>
            💰 Total CA<br>{int(total_global):,} €
        </div>
    """, unsafe_allow_html=True)

    top2.markdown(f"""
        <div style='
            background-color:#e3f2fd;
            border:2px solid #90caf9;
            color:#1565c0;
            padding:18px;
            border-radius:10px;
            text-align:center;
            font-size:20px;
            font-weight:600;
            margin-bottom:25px;
            box-shadow:0 1px 3px rgba(0,0,0,0.05);
        '>
            📆 CA moyen (jours avec CA)<br>{int(ca_moyen_jours_effectifs):,} €
        </div>
    """, unsafe_allow_html=True)

    top3.markdown(f"""
        <div style='
            background-color:#fff3e0;
            border:2px solid #ffcc80;
            color:#e65100;
            padding:18px;
            border-radius:10px;
            text-align:center;
            font-size:20px;
            font-weight:600;
            margin-bottom:25px;
            box-shadow:0 1px 3px rgba(0,0,0,0.05);
        '>
            💎 Part BIJOUX<br>{pourcentage_bijoux:.1f}%
        </div>
    """, unsafe_allow_html=True)

    # Bloc de 3 colonnes pour les sous-totaux
    col1, col2, col3 = st.columns(3)

    def bloc_metric_simple(titre, valeur, emoji, cat):
        couleur = "#2e7d32" if cat == meilleur_cat else "#444"
        return f"""
            <div style='
                background-color:#f7f7f7;
                border-radius:10px;
                padding:18px;
                text-align:center;
                box-shadow:0 1px 3px rgba(0,0,0,0.08);
            '>
                <div style='font-size:18px;'>{emoji} <b>{titre}</b></div>
                <div style='font-size:22px; color:{couleur}; margin-top:10px'>{valeur}</div>
            </div>
        """
    
    # Déterminer la catégorie avec le plus grand total
    totaux = {
        "BIJOUX": total_bijoux,
        "EASY": total_easy,
        "BLOCS + SOCLES": montant_3d_estime
    }
    meilleur_cat = max(totaux, key=totaux.get)

    col1.markdown(bloc_metric_simple("Total BIJOUX", f"{int(total_bijoux):,} €".replace(",", " "), "💎", "BIJOUX"), unsafe_allow_html=True)
    col2.markdown(bloc_metric_simple("Total EASY", f"{int(total_easy):,} €".replace(",", " "), "🎁", "EASY"), unsafe_allow_html=True)
    col3.markdown(bloc_metric_simple("SOCLES + 3D", f"{int(montant_3d_estime):,} €".replace(",", " "), "🧱", "BLOCS + SOCLES"), unsafe_allow_html=True)

    st.markdown("---")

    st.subheader("🏅 Produits les + vendus par catégorie")
    bloc_col, bijoux_col, easy_col = st.columns(3)

    for cat, col, emoji in zip(
        ["BLOCS + SOCLES", "BIJOUX", "EASY"],   
        [bloc_col, bijoux_col, easy_col],
        ["🧱", "💎", "🎁"]
    ):
        produit, montant = tops.get(cat, ("Aucun", 0))
        col.markdown(f"""
            <div style='padding:10px; background-color:#f7f7f7; border-radius:10px; text-align:center'>
                <div style='font-size:16px'>{emoji} <b>{cat}</b></div>
                <div style='font-size:14px; margin-top:8px'><b>{produit}</b></div>
                <div style='font-size:18px; color:#2e7d32; margin-top:5px'>{montant:,.0f} €</div>
            </div>
        """, unsafe_allow_html=True)
        
    #st.subheader("🧪 Données brutes")
    #st.dataframe(df)

    st.markdown("---")

        # Top/Pires jours
    jours_valides = ca_par_jour[ca_par_jour["CA"] > 0].copy()
    top_jours = jours_valides.sort_values(by="CA", ascending=False).head(5).copy()
    pire_jours = jours_valides.sort_values(by="CA").head(5).copy()

    top_jours["Jour"] = top_jours["Jour"].dt.strftime("%d/%m/%Y")
    pire_jours["Jour"] = pire_jours["Jour"].dt.strftime("%d/%m/%Y")

    top_jours["CA"] = top_jours["CA"].apply(lambda x: f"{x:,.0f} €".replace(",", " "))
    pire_jours["CA"] = pire_jours["CA"].apply(lambda x: f"{x:,.0f} €".replace(",", " "))

    st.subheader("🔝 Top 5 jours")
    st.table(top_jours)

    st.subheader("🔻 Pires 5 jours")
    st.table(pire_jours)

    st.download_button("📥 Télécharger les données (CSV)", data=df_long.to_csv(index=False), file_name="CA_TourEiffel.csv", mime="text/csv")

except Exception as e:
    st.error("❌ Erreur lors du chargement ou du traitement des données.")
    st.exception(e)