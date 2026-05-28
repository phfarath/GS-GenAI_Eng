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

# ---------- estado inicial + presets ----------
DEFAULTS = dict(otype="PAYLOAD", alt=550.0, inc=53.0, ecc=0.001, bstar=0.5,
                rsize="MEDIUM", rcsm2=1.0, period=95.5, days=365)
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)

def _apply(preset):
    st.session_state.update(preset)

PRESET_HIGH = dict(otype="DEBRIS", alt=820.0, inc=98.0, ecc=0.005, bstar=0.8,
                   rsize="SMALL", rcsm2=0.5, period=101.0, days=4000)
PRESET_LOW  = dict(otype="PAYLOAD", alt=35786.0, inc=0.1, ecc=0.001, bstar=0.1,
                   rsize="LARGE", rcsm2=15.0, period=1436.0, days=2000)

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

st.info(
    "**O tipo do objeto é o fator dominante** (≈29% da importância SHAP): "
    "`PAYLOAD` é manobrável e o modelo aprendeu que payloads desviam de conjunções → tende a **LOW** "
    "em quase qualquer configuração. Risco **MEDIUM/HIGH** concentra-se em `DEBRIS` e `ROCKET_BODY` "
    "(não manobráveis), agravado por altitude congestionada e tamanho. Use os presets abaixo para ver os extremos."
)

cpre1, cpre2, _ = st.columns([1, 1, 2])
cpre1.button("Exemplo de ALTO risco", on_click=_apply, args=(PRESET_HIGH,), use_container_width=True)
cpre2.button("Exemplo de BAIXO risco", on_click=_apply, args=(PRESET_LOW,), use_container_width=True)

col1, col2 = st.columns([1, 2])

# ---------- entrada (raw) — widgets ligados ao session_state via key ----------
with col1:
    st.subheader("Atributos do objeto")
    object_type   = st.selectbox("Tipo", ["PAYLOAD", "ROCKET_BODY", "DEBRIS"], key="otype")
    altitude_km   = st.slider("Altitude (km)", 300.0, 36000.0, step=10.0, key="alt")
    inclination   = st.slider("Inclinação (graus)", 0.0, 180.0, step=0.5, key="inc")
    eccentricity  = st.slider("Excentricidade", 0.0, 0.25, step=0.001, format="%.3f", key="ecc")
    bstar         = st.slider("BSTAR (arrasto)", 0.0, 3.0, step=0.01, key="bstar")
    rcs_size      = st.selectbox("RCS (categórico)", ["SMALL", "MEDIUM", "LARGE"], key="rsize")
    rcs_value_m2  = st.slider("RCS (m²)", 0.01, 50.0, step=0.05, key="rcsm2")
    period_min    = st.number_input("Período orbital (min)", 80.0, 1500.0, step=0.5, key="period")
    days_in_orbit = st.number_input("Dias em órbita", 0, 15000, step=30, key="days")

# ---------- predição ao vivo (sem botão) + SHAP ----------
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
