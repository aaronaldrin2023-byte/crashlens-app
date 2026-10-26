import streamlit as st
import pandas as pd

df = pd.read_csv("data/ct_crashes_sample.csv")
st.dataframe(df.head())
