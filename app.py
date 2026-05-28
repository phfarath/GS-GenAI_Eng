"""
GAIE — Streamlit demo do classificador de risco de colisão orbital.

Deploy (Streamlit Community Cloud — gratuito):
  1. Suba este arquivo + gaie_risk_model.joblib + gaie_meta.json + requirements.txt num repo público no GitHub.
  2. Vá em https://share.streamlit.io, faça login com GitHub, "New app", aponte para o repo.
  3. Em ~3 minutos sai uma URL pública.

Localmente:
  streamlit run app.py
"""
import json, joblib, numpy as np, pandas as pd
import streamlit as st
import shap
import matplotlib.pyplot as plt

st.set_page_config(page_title="Risco Orbital — GAIE", layout="wide")

# ---------- carga do modelo ----------
@st.cache_resource
def load_model():
    model = joblib.load("gaie_risk_model.joblib")
    meta  = json.load(open("gaie_meta.json"))
    return model, meta

model, META = load_model()
CLASSES = META["classes"]

# ---------- UI ----------
st.title("Previsão de Risco de Colisão Orbital")
st.caption("Classificador HIGH / MEDIUM / LOW com explicação SHAP — Global Solution 2026/1 · Indústria Espacial")

with st.expander("Sobre", expanded=False):
    st.write(f"""
**Modelo:** {META['best']} (acurácia no teste = {META['test_acc']:.3f})  
**Treino:** 1.100 objetos orbitais sintéticos seguindo o `data_contract.md` do projeto.  
**Output:** classe de risco + probabilidade + decomposição SHAP da decisão.  
**Limitação:** dataset sintético — prova de metodologia, não classificador validado contra TLEs reais.
    """)

col1, col2 = st.columns([1, 2])

# ---------- entrada (raw) ----------
with col1:
    st.subheader("Atributos do objeto")
    object_type   = st.selectbox("Tipo", ["PAYLOAD", "ROCKET_BODY", "DEBRIS"], index=0)
    altitude_km   = st.slider("Altitude (km)", 300.0, 36000.0, 550.0, step=10.0)
    inclination   = st.slider("Inclinação (graus)", 0.0, 180.0, 53.0, step=0.5)
    eccentricity  = st.slider("Excentricidade", 0.0, 0.25, 0.001, step=0.001, format="%.3f")
    bstar         = st.slider("BSTAR (arrasto)", 0.0, 3.0, 0.5, step=0.01)
    rcs_size      = st.selectbox("RCS (categórico)", ["SMALL", "MEDIUM", "LARGE"], index=1)
    rcs_value_m2  = st.slider("RCS (m²)", 0.01, 50.0, 1.0, step=0.05)
    period_min    = st.number_input("Período orbital (min)", 80.0, 1500.0, 95.5, step=0.5)
    days_in_orbit = st.number_input("Dias em órbita", 0, 15000, 365, step=30)
    btn = st.button("Calcular risco", type="primary", use_container_width=True)

# ---------- predição + SHAP ----------
if btn:
    log_rcs        = float(np.log1p(rcs_value_m2))
    altitude_band  = "LEO" if altitude_km < 2000 else ("MEO" if altitude_km < 30000 else "GEO")

    row = pd.DataFrame([{
        "object_type": object_type, "rcs_size": rcs_size, "altitude_band": altitude_band,
        "altitude_km": altitude_km, "inclination_deg": inclination,
        "eccentricity": eccentricity, "bstar": bstar,
        "rcs_value_m2": rcs_value_m2, "log_rcs": log_rcs,
        "period_min": period_min, "days_in_orbit": days_in_orbit,
    }])
    row = row[META["features"]]   # ordem exata do treino

    pred  = model.predict(row)[0]
    proba = model.predict_proba(row)[0]

    with col2:
        color = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}[pred]
        st.subheader(f"Predição: {color} {pred}")
        st.bar_chart({c: float(p) for c, p in zip(model.classes_, proba)})

        # SHAP local: opera no espaço pré-processado
        pre = model.named_steps["pre"]
        clf = model.named_steps["clf"]
        x_pre = pre.transform(row)
        feat_names = ["rcs_size", "object_type", "altitude_band"] + META["num_cols"]

        explainer = shap.TreeExplainer(clf)
        sv = explainer(x_pre)
        ci = list(clf.classes_).index(pred)

        # API moderna: shape (1, n_features, n_classes)
        exp = shap.Explanation(
            values        = sv.values[0, :, ci],
            base_values   = sv.base_values[0, ci],
            data          = x_pre[0],
            feature_names = feat_names,
        )

        st.markdown(f"**Por que o modelo previu `{pred}`** (decomposição SHAP):")
        fig = plt.figure(figsize=(9, 5))
        shap.plots.waterfall(exp, show=False, max_display=10)
        st.pyplot(fig, clear_figure=True)

        st.caption("Vermelho empurra a predição PARA esta classe; azul empurra PARA FORA. "
                   "Use para auditar a decisão antes de acionar resposta (RPA/PBML).")
else:
    with col2:
        st.info("Ajuste os atributos à esquerda e clique em **Calcular risco**.")
        st.markdown("**Exemplo de objeto de alto risco para testar:**")
        st.code("Tipo=DEBRIS, Altitude=850, Inclinação=98, RCS=MEDIUM, RCS_m2=2.0", language=None)
        st.markdown("**Exemplo de baixo risco:**")
        st.code("Tipo=PAYLOAD, Altitude=35786 (GEO), Inclinação=0.1, RCS=LARGE, RCS_m2=15", language=None)
