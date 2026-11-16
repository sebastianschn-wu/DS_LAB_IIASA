"""Column names, the CDR definition, and local model settings."""

# Column names for policy descriptions
POLICY_DESCRIPTION_COLUMN_IEA = "description"
POLICY_DESCRIPTION_COLUMN_CLIMATE_LAWS = "Family Summary"

# Same local model the first coding loop uses.
OLLAMA_HOST = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen2.5"
OLLAMA_KEEP_ALIVE = "30m"
OLLAMA_SEED = 1
OLLAMA_NUM_PREDICT = 200
OLLAMA_CHAT_TIMEOUT = 900
OLLAMA_NUM_CTX = 4096
OLLAMA_TEMPERATURE = 0.0

# Definitions retrieved from the Intergovernmental Panel on Climate Change (IPCC) AR6 WGIII Factsheet on CDR: https://www.ipcc.ch/report/ar6/wg3/downloads/outreach/IPCC_AR6_WGIII_Factsheet_CDR.pdf
CDR_DEFINITION = """
CARBON DIOXIDE REMOVAL (CDR) refers to technologies, practices, and approaches that remove and durably store carbon dioxide (CO2) from the atmosphere. CDR is required to achieve global and
national targets of net zero CO2 and greenhouse gas (GHG) emissions. CDR cannot substitute for immediate and deep emissions reductions, but it is part of all modelled scenarios that limit global
warming to 2°or lower by 2100. Implementation will require decisions regarding CDR methods, scale and timing of deployment, and how sustainability and feasibility constraints are managed.

What is Carbon Dioxide Removal?

CDR refers to deliberate technologies, practices, and approaches
that remove carbon dioxide (CO2) from the atmosphere.

CDR also involves durably storing carbon
after it has been extracted from the
atmosphere, either in reservoirs such as
vegetation, soils, geological formations, or
the ocean, or in manufactured products.

CDR only refers to human activities
that intentionally remove CO2 from
the atmosphere. It does not include
natural CO2 removal (such as through
growth of natural forests).

There are many
different CDR methods
and associated
implementation
options, with different
timescales and risk
factors. Depending on scale and deployment
scenario, CDR methods could have co-
benefits or adverse side effects, which should
be managed through appropriate CDR
governance and policies.

CDR methods differ in terms of removal process, timescale of carbon storage, technological maturity, mitigation potential, cost, co-benefits, adverse side-effects, and governance requirements.
Implementation strategies need to take into account these differences and potential trade-offs.
"""
