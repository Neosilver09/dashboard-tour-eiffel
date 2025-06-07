from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import pandas as pd
import streamlit as st
import os

# 🔐 Auth via OAuth
gauth = GoogleAuth()
gauth.LocalWebserverAuth()
drive = GoogleDrive(gauth)

# 🆔 ID du fichier Google Sheets (trouvé dans l’URL)
FILE_ID = "FbeHZLdT9KntpWfbzQduLV08jKEGvQBkCb"

# 📥 Télécharger le fichier Excel
file = drive.CreateFile({'id': FILE_ID})
file.GetContentFile("tfl_temp.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# 📄 Lire avec pandas
xls = pd.ExcelFile("tfl_temp.xlsx")
st.write("🗂️ Feuilles disponibles :", xls.sheet_names)

df = xls.parse("JUIN")
st.dataframe(df.head())