# pages/1_Dashboard.py
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Recruitment hub - Home", layout="wide")

st.title("Recruitment hub (mock)")

st.info('The hub (lightweight UI) could provide reporting services like this via a GRID data connection or by talking to the future Civil Service Jobs APIs.', icon="ℹ️")

# ----------------------------------
# 1. Mock data
# ----------------------------------
jobs_data = [
    {"job_id": "CSJ-0001", "job_title": "Senior Product Manager", "status": "Advertised", "views": 234},
    {"job_id": "CSJ-0002", "job_title": "Performance Analyst", "status": "Draft", "views": 0},
    {"job_id": "CSJ-0003", "job_title": "Service Designer", "status": "Advertised", "views": 178},
    {"job_id": "CSJ-0004", "job_title": "Interaction Designer", "status": "Closed", "views": 421},
    {"job_id": "CSJ-0005", "job_title": "Delivery Manager", "status": "Draft", "views": 0},
    {"job_id": "CSJ-0006", "job_title": "Technical Architect", "status": "Closed", "views": 355},
    {"job_id": "CSJ-0007", "job_title": "Recruitment Lead", "status": "Advertised", "views": 292},
]

df = pd.DataFrame(jobs_data)

# quick counts
draft_count = (df["status"] == "Draft").sum()
advertised_count = (df["status"] == "Advertised").sum()
closed_count = (df["status"] == "Closed").sum()
total_count = len(df)
published_views = df[df["status"].isin(["Advertised", "Closed"])]["views"].sum()

# ----------------------------------
# 2. Scorecards
# ----------------------------------
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Jobs in draft", draft_count)
col2.metric("Jobs advertised", advertised_count)
col3.metric("Jobs closed", closed_count)
col4.metric("Total jobs", total_count)
col5.metric("Total advert views", published_views)

st.markdown("---")

# ----------------------------------
# 3. Mini tables per status
# ----------------------------------
c1, c2, c3 = st.columns(3)

with c1:
    st.subheader("Draft")
    st.dataframe(
        df[df["status"] == "Draft"][["job_id", "job_title"]],
        use_container_width=True,
        hide_index=True
    )

with c2:
    st.subheader("Advertised")
    st.dataframe(
        df[df["status"] == "Advertised"][["job_id", "job_title", "views"]],
        use_container_width=True,
        hide_index=True
    )

with c3:
    st.subheader("Closed")
    st.dataframe(
        df[df["status"] == "Closed"][["job_id", "job_title", "views"]],
        use_container_width=True,
        hide_index=True
    )
