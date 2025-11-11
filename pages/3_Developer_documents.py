from password_gate import require_password
require_password()
import streamlit as st


st.set_page_config(page_title="Recruitment hub - Developer documents", page_icon="🧩")

st.title("Developer documents (mock)")

st.info('The hub could centrally house documents that enable clusters to integrate.', icon="ℹ️")

st.write(
	"This page collects developer-facing resources for integrating with the Civil Service Jobs API "
	"hosted at https://cab-mark.github.io/. Use the links and examples below to locate the OpenAPI spec and make API calls."
)

st.markdown("---")

st.header("OpenAPI / API documentation")
st.markdown(
	"The canonical API docs (OpenAPI/Swagger or Redoc) are published on GitHub Pages. "
	"Open the hosted site and look for the OpenAPI/Swagger UI to explore endpoints, schemas and authentication details."
)

st.markdown("- Hosted docs: [https://cab-mark.github.io/](https://cab-mark.github.io/)")

st.subheader("Quick developer tips")
st.markdown(
	"- Common locations for the raw OpenAPI spec are `openapi.json`, `openapi.yaml`, or `swagger.json` at the site root.\n"
	"- If you cannot find the spec, open the hosted docs and look for a link labelled `OpenAPI`, `Swagger`, `API spec`, or similar."
)

st.subheader("Try it from a terminal")
st.code(
	"""# Try to fetch an OpenAPI document (json or yaml)
curl -sS https://cab-mark.github.io/openapi.json -o openapi.json || \
  curl -sS https://cab-mark.github.io/openapi.yaml -o openapi.yaml

# If you find the spec URL you can use the public Swagger UI to inspect it:
# https://petstore.swagger.io/?url=https://cab-mark.github.io/openapi.json
""",
	language="bash",
)

st.subheader("Programmatic example (Python)")
st.code(
	"""import requests

spec_url = 'https://cab-mark.github.io/openapi.json'  # replace if different
r = requests.get(spec_url, timeout=10)
r.raise_for_status()
spec = r.json()
print('Paths in spec:')
for p in sorted(spec.get('paths', {}).keys()):
	print(p)
""",
	language="python",
)

st.subheader("Example API call")
st.code(
	"""# Example: call a jobs endpoint (replace BASE_URL and auth as required)
import requests

BASE_URL = 'https://cab-mark.github.io'  # replace with actual API base URL
API_KEY = '<your_api_key>'
resp = requests.get(f"{BASE_URL}/jobs?limit=10", headers={
	'Authorization': f"Bearer {API_KEY}",
	'Accept': 'application/json'
})
print(resp.status_code)
print(resp.json())
""",
	language="python",
)

st.markdown("---")

st.info(
	"If you share the exact OpenAPI spec URL I can add a small generated client and a smoke test to this repo (or embed an interactive Swagger/Redoc iframe on this page)."
)

