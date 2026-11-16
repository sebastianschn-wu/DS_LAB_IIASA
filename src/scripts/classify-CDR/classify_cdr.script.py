#!/usr/bin/env python3
"""Keep the rows in each downloaded policy CSV that a local model marks as CDR-relevant.

Reads every CSV in ``data/downloads``, classifies the policy description, and
writes the CDR-relevant rows to ``data/downloads/cdr_relevant``. Climate Laws
rows are classified from ``Family Summary``. IEA rows are classified from
``title`` + ``description``.

What this script does per CSV:
  1. A broad, cheap pre-filter drops only clearly non-CDR rows (trade, prices,
     security of supply, social policy). Rows with any CDR-ish keyword are never dropped.
  2. The local model classifies the remaining rows into a CDR category (or NOT_RELEVANT).
     Results are cached, so a crash or a rerun resumes where it stopped.
  3. The original rows (all columns, untouched) of CDR-relevant policies are written to
     ``<name>_cdr_relevant.csv``; ``<name>_labels.csv`` has category + evidence for every row.

Usage:
    python src/scripts/classify-CDR/classify_cdf.script.py
    python src/scripts/classify-CDR/classify_cdf.script.py --limit 50
    python src/scripts/classify-CDR/classify_cdf.script.py --keyword-gate
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import time
from pathlib import Path

import pandas as pd
import requests

from constants import (
    CDR_DEFINITION,
    OLLAMA_CHAT_TIMEOUT,
    OLLAMA_HOST,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_NUM_PREDICT,
    OLLAMA_SEED,
    OLLAMA_TEMPERATURE,
    POLICY_DESCRIPTION_COLUMN_CLIMATE_LAWS,
    POLICY_DESCRIPTION_COLUMN_IEA,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
INPUT_DIR = REPO_ROOT / "data" / "downloads"
OUTPUT_DIR = INPUT_DIR / "cdr_relevant"

HOST = OLLAMA_HOST
MODEL = OLLAMA_MODEL
NUM_CTX = OLLAMA_NUM_CTX
TEMPERATURE = OLLAMA_TEMPERATURE
THINKING_MODELS = ("qwen3", "deepseek-r1")  # these get "think": false

CDR_RELEVANT = "CDR_RELEVANT"
NOT_CDR_RELEVANT = "NOT_CDR_RELEVANT"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Broad, cheap pre-filter
# ---------------------------------------------------------------------------

_SUBSCRIPTS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")


def clean(text) -> str:
    """Strip HTML and normalise whitespace / CO₂ subscripts (used for the model input)."""
    t = str(text).translate(_SUBSCRIPTS)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>|&nbsp;|&amp;", " ", t)).strip()


# IEA ``policyType`` values that are purely economic / trade / security-of-supply / social.
# A row is only dropped if ALL of its policy types are in this set AND it has no keyword below.
ECON_POLICY_TYPES = {
    "Preferential trade agreements", "Tariffs and duties", "Non-tariff measures",
    "Export and import ban", "Export controls and restrictions", "Import controls and restrictions",
    "Import strategy", "Market access", "Foreign direct investment (FDI)",
    "Local content requirements", "Collaboration on trade", "Intellectual property regimes",
    "Oil stockholding obligation", "Gas stockholding obligation", "Gas emergency plan",
    "Oil emergency plan", "Stockpiling mechanisms", "Energy security and resilience",
    "Cybersecurity requirements for energy operators", "Energy affordability spending programmes",
    "Universal energy access", "Energy access spending programmes", "Fixed premium",
    "Feed-in tariffs/premiums", "OPEX support", "National disaster fund",
    "Skills and training", "Training programmes spending programmes", "Decent jobs",
    "Youth in decision process", "Gender inclusion", "Social dialogue", "Social standards",
    "Socioeconomic development", "Fair distribution of benefits", "Education and training",
    "Just transition planning spending programmes", "Due diligence obligations", "Traceability",
    "Strategic mineral lists", "Resource rights", "Resource extraction provisions",
    "Oil and gas exploration ban", "Plan to phase-out unabated coal", "Biofuel blending mandate",
    "Fuel standard", "Blending",
}

# Any of these in the text means the row is NEVER dropped by the metadata rule.
KEEP_KEYWORDS = re.compile(
    r"carbon|co2|ghg|greenhouse|sink|sequest|absorption|remov|negative emission|"
    r"net[- ]?zero|climate[- ]neutral|neutrality|ndc|nationally determined|lulucf|"
    r"forest|afforest|reforest|tree|woodland|soil|peat|wetland|mangrove|land[- ]use|agroforest|"
    r"biochar|biomass|bioenerg|weathering|mineralis|mineraliz|ocean|marine|blue economy|"
    r"capture|ccs|ccus|\bdac|geolog|storage of|offset|credit|mrv|"
    r"long-term (?:low|strategy)|climate (?:law|act|strategy|plan)",
    re.I,
)


def _policy_types(value) -> list[str]:
    try:
        return [item.get("name", "") for item in json.loads(value)] if value else []
    except Exception:
        return []


def prefilter_mask(df: pd.DataFrame, text: pd.Series, keyword_gate: bool) -> pd.Series:
    """True = send the row to the model. False = clearly irrelevant, labelled NOT_CDR_RELEVANT."""
    has_keyword = text.map(lambda t: bool(KEEP_KEYWORDS.search(t)))
    send = text.str.len() > 0
    if "policyType" in df.columns:  # IEA only
        types = df["policyType"].map(_policy_types)
        econ_only = types.map(lambda l: len(l) > 0 and all(t in ECON_POLICY_TYPES for t in l))
        send &= ~(econ_only & ~has_keyword)
    if keyword_gate:  # optional, much faster, may lose recall
        send &= has_keyword
    return send


# ---------------------------------------------------------------------------
# 2. Instructions and structured output
# ---------------------------------------------------------------------------

CATEGORIES = [
    "ENGINEERED_REMOVAL",  # DAC, BECCS, biochar, weathering, marine CDR, removal credits/procurement/R&D
    "CO2_STORAGE_CCUS",    # CO2 capture/transport/geological storage + permitting, liability, EIA, finance
    "LAND_OCEAN_SINKS",    # afforestation, forest/peat/wetland/soil/blue-carbon restoration & protection
    "CARBON_MARKET_MRV",   # crediting, offsets, ETS with credits/sinks, MRV, LULUCF accounting, registries
    "CLIMATE_FRAMEWORK",   # NDC/INDC, LT-LEDS, net-zero & climate laws, carbon budgets
    "NOT_RELEVANT",
]

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "evidence": {"type": "string"},
        "category": {"type": "string", "enum": CATEGORIES},
    },
    "required": ["evidence", "category"],
}

_INSTRUCTIONS = """
You are an expert in climate policy and Carbon Dioxide Removal (CDR).
Decide whether a policy description is relevant to CDR.

Use this definition of CDR as background:

{definition}

RELEVANCE STANDARD (broad):
A policy is relevant if it directly concerns carbon removal or carbon sinks,
OR if it is part of the legal, financial, technical or market system that
enables, counts, funds, permits, credits or governs removals and sinks.
Indirect enabling roles COUNT. The words "CDR" or "removal" do not need to
appear. Judge only from the description.

CATEGORIES (pick the best one; anything except NOT_RELEVANT means relevant):

ENGINEERED_REMOVAL - direct air capture, BECCS, biochar, enhanced weathering,
  mineralisation, ocean/marine CDR; removal targets, procurement, credits,
  certification, R&D or demonstration funding for them.

CO2_STORAGE_CCUS - CO2 capture, transport, utilisation and geological storage,
  CCUS hubs and pipelines, including their funding, tax credits, licensing,
  liability, monitoring, permitting, environmental assessment and public
  participation rules (this is the storage base that BECCS/DACCS need).

LAND_OCEAN_SINKS - afforestation, reforestation, forest management, protection
  or conservation that maintains or increases carbon stocks; peatland, wetland,
  mangrove and blue-carbon restoration; soil carbon, agroforestry, rangeland
  restoration, climate-smart agriculture, long-lived wood products; grants or
  payments for these. Must be tied to carbon, sinks, climate or restoration.

CARBON_MARKET_MRV - carbon crediting, offset and ETS frameworks that involve
  credits, offsets, removals or the land sector; voluntary or compliance carbon
  market rules and registries; MRV, GHG inventory or accounting for removals,
  LULUCF, forest reference levels, soil carbon monitoring. A bare price level
  or tax rate with no credits/offsets/sinks is NOT enough.

CLIMATE_FRAMEWORK - Only economy-wide targets and legal frameworks: NDC/INDC,
 long-term low-emission strategy, net-zero or climate-neutrality law, carbon budget.
  NOT sector plans, energy or transport strategies, NECP-style plans with only renewable
  or efficiency targets, adaptation plans, fossil-fuel roadmaps, development plans,
  taxonomies, disclosure rules, or committee and ministry decrees, unless the text also
  mentions sinks, removals, storage or carbon markets.

NOT_RELEVANT - no link to any category above. Typical: renewable power,
  energy efficiency standards, electric vehicles and charging, hydrogen from
  renewables, fossil phase-out, methane leak rules, energy security or
  stockholding, prices, subsidies and tariffs, trade agreements, jobs and
  social policy, adaptation or water policy without carbon.

If a description fits a category only through an indirect enabling role listed
above, choose that category. If it fits none, choose NOT_RELEVANT.

EXAMPLES of relevant policies:
1. Forest management and conservation
The National Forest Management Strategy (2022) establishes guidelines for sustainable forest management in Victoria, prioritising the maintenance of existing forest carbon stocks and reducing emissions from logging activities.
The Native Forest Conservation Agreement (2024) establishes long-term commitments to protect 500,000 hectares of native forests in Queensland, limiting harvesting activities to preserve carbon storage capacity.

2. Afforestation and reforestation
The Green Landscapes Programme (2021) provides AUD 35 million in grants to support tree planting and reforestation projects across New South Wales, increasing national forest carbon sinks.
The National Plantation Expansion Initiative (2023) aims to establish 750 million new plantation trees by 2035 to increase domestic timber production and long-term biomass carbon stocks.

3. Carbon markets and crediting mechanisms
The National Carbon Credit Scheme (2022) establishes a framework for issuing carbon credits from afforestation, soil carbon sequestration and improved forest management projects.
The Land Carbon Trading Programme (2024) enables farmers and landowners in Western Australia to generate and trade verified carbon credits from reforestation and agricultural soil management activities.

4. Engineered carbon removal and CCUS
The Carbon Capture Innovation Fund (2023) allocates AUD 65 million to support research and demonstration projects involving direct air capture, geological storage and mineral carbonation.
The National Carbon Storage Initiative (2025) supports the development of regional CO₂ transport and geological storage infrastructure, enabling future deployment of BECCS and DACCS projects.

5. Soil carbon and regenerative agriculture
The National Soil Health Programme (2022) provides financial incentives to farmers adopting cover cropping, reduced tillage and rotational grazing practices that enhance soil organic carbon stocks.
The Agricultural Carbon Innovation Scheme (2024) funds pilot projects investigating enhanced rock weathering and biochar application to improve soil carbon sequestration.

6. Research, development and innovation
The Sustainable Carbon Research Programme (2023) provides funding for universities and research institutions developing improved measurement techniques for forest and agricultural soil carbon.
The National Forestry Innovation Institute (2021) supports research into long-lived wood products and sustainable timber processing to increase carbon storage in harvested wood products.

7. Climate legislation and national strategies
The Climate Neutrality Act (2023) establishes a legally binding target of net-zero greenhouse gas emissions by 2050, recognising the contribution of natural and technological carbon removals.
The National Carbon Removal Strategy (2025) outlines a pathway for scaling forest restoration, soil carbon sequestration and engineered carbon removal technologies by 2040.

8. Nationally Determined Contributions (NDCs)
Country X's updated NDC (2021) commits to reducing greenhouse gas emissions by 45% below 2005 levels by 2030, with forest restoration and sustainable land management contributing to the target.
Country X's Second NDC (2025) establishes a 2035 emissions reduction target of 65% below 1990 levels, highlighting the role of land-based removals and emerging engineered CDR technologies.

9. Emissions trading and compliance mechanisms
The Industrial Emissions Trading Scheme (2023) requires large industrial facilities to surrender eligible carbon credits when their annual emissions exceed established limits, including credits from approved forestry projects.
The National Carbon Compliance Mechanism (2025) allows regulated companies to offset up to 10% of their annual emissions obligations using certified carbon removal credits.

10. Nature restoration and biodiversity
The National Ecosystem Restoration Fund (2022) provides grants for wetland restoration, native forest regeneration and rehabilitation of degraded landscapes, increasing ecosystem carbon stocks.
The Biodiversity and Carbon Farming Programme (2024) rewards landowners for restoring native vegetation and protecting ecological communities while generating additional carbon sequestration benefits.

11. Carbon removal measurement, reporting and verification (MRV)
The National Soil Carbon Measurement Initiative (2023) funds the development of low-cost technologies for monitoring soil organic carbon changes across agricultural landscapes.
The Carbon Accounting and Verification Regulation (2025) establishes standardised monitoring and reporting requirements for land-based carbon removal projects, including forestry and soil carbon activities.

12. Carbon dioxide transport and geological storage
The Regional CO₂ Infrastructure Programme (2024) provides AUD 120 million in funding for pipelines and shared CO₂ storage facilities supporting industrial carbon management projects.
The Geological Carbon Storage Act (2025) establishes licensing, monitoring, environmental liability and long-term storage requirements for geological CO₂ sequestration projects.

13. Biomass, BECCS and biochar
The Sustainable Biomass Development Strategy (2022) promotes the use of agricultural residues and forestry waste as feedstocks for bioenergy production, supporting the potential deployment of BECCS.
The Biochar Demonstration Programme (2024) provides AUD 20 million in grants for pilot projects converting agricultural residues into biochar for long-term carbon storage in soils.

14. Environmental safeguards and permitting
The Environmental Assessment Regulation (2023) requires large-scale carbon capture and geological storage projects to undergo environmental impact assessments before receiving development approval.
The Carbon Removal Project Permitting Framework (2025) establishes requirements for assessing potential impacts of afforestation projects on agricultural land, biodiversity and regional water resources.

15. International cooperation and carbon removal finance
The International Carbon Technology Partnership (2023) provides co-funding for collaborative research into direct air capture, carbon mineralisation and geological storage technologies.
The Green Carbon Investment Facility (2025) establishes a financing mechanism to support international afforestation, ecosystem restoration and engineered carbon removal projects.

Anything which is not directly linked to one of the categories of CDR or does not match the formal definition of CDR is NOT_RELEVANT.

OUTPUT: return ONLY JSON with two keys, in this order:
{{"evidence": "<=25 words from or about the description showing the link, or 'none'. It must be a direct link to the policy description, not a general statement about CDR.",
  "category": "<one category>"}}
"""

SYSTEM_INSTRUCTIONS = _INSTRUCTIONS.format(definition=CDR_DEFINITION.strip())
# Cache entries are tied to the prompt + model, so changing either re-classifies everything.
PROMPT_VERSION = hashlib.sha1((MODEL + SYSTEM_INSTRUCTIONS).encode()).hexdigest()[:10]


# ---------------------------------------------------------------------------
# 3. Model call
# ---------------------------------------------------------------------------

def call_model(user_prompt: str) -> str:
    body = {
        "model": MODEL,
        "stream": False,
        "format": OUTPUT_SCHEMA,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "messages": [
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": user_prompt},
        ],
        "options": {
            "temperature": TEMPERATURE,
            "seed": OLLAMA_SEED,
            "num_ctx": NUM_CTX,
            "num_predict": OLLAMA_NUM_PREDICT,
        },
    }
    if MODEL.startswith(THINKING_MODELS):
        body["think"] = False
    response = requests.post(f"{HOST}/api/chat", json=body, timeout=OLLAMA_CHAT_TIMEOUT)
    response.raise_for_status()
    content = response.json().get("message", {}).get("content", "")
    if not content:
        raise RuntimeError("Empty model response")
    return content


def classify_policy(text: str) -> dict:
    """Return {"label", "category", "evidence"}. Raises on request or parse errors."""
    if not text.strip():
        return {"label": NOT_CDR_RELEVANT, "category": "NOT_RELEVANT", "evidence": "empty"}
    content = call_model(f"POLICY DESCRIPTION:\n\n{text.strip()}\n")
    try:
        data = json.loads(content)
        category = str(data["category"]).strip()
        if category not in CATEGORIES:
            raise ValueError(f"unexpected category {category!r}")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Could not parse model output: {content[:200]}") from exc
    label = NOT_CDR_RELEVANT if category == "NOT_RELEVANT" else CDR_RELEVANT
    return {"label": label, "category": category, "evidence": str(data.get("evidence", ""))[:300]}


# ---------------------------------------------------------------------------
# 4. CSV processing
# ---------------------------------------------------------------------------

def get_policy_description_column(df: pd.DataFrame) -> str:
    candidate_columns = [
        POLICY_DESCRIPTION_COLUMN_IEA,
        POLICY_DESCRIPTION_COLUMN_CLIMATE_LAWS,
    ]
    for column in candidate_columns:
        if column in df.columns:
            logger.info("Using policy description column: %s", column)
            return column
    raise ValueError(
        "No recognized policy description column found. "
        f"Expected one of: {candidate_columns}. "
        f"Available columns: {list(df.columns)}"
    )


def load_cache(path: Path) -> dict:
    cache: dict = {}
    if path.exists():
        for line in path.open(encoding="utf-8"):
            rec = json.loads(line)
            if rec.get("v") == PROMPT_VERSION:
                cache[rec["text"]] = rec
    return cache


def process_csv(csv_path: Path, output_dir: Path, limit: int | None, keyword_gate: bool) -> None:
    logger.info("Processing file: %s", csv_path.name)
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)  # keep rows exactly as they are
    if limit is not None:
        df = df.head(limit)
    if df.empty:
        logger.warning("Skipping empty CSV: %s", csv_path.name)
        return

    description_column = get_policy_description_column(df)
    text = df[description_column].map(clean)
    if "title" in df.columns:  # IEA: titles often carry the signal
        text = (df["title"].map(clean) + ". " + text).str.strip(". ")

    send = prefilter_mask(df, text, keyword_gate)
    unique = list(dict.fromkeys(text[send]))
    logger.info(
        "%s: %s rows | %s sent to model (%s unique texts) | %s dropped by pre-filter",
        csv_path.name, len(df), send.sum(), len(unique), (~send).sum(),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    cache_path = output_dir / f"{csv_path.stem}_cache.jsonl"
    cache = load_cache(cache_path)
    todo = [t for t in unique if t not in cache]
    logger.info("%s: %s cached, %s to classify", csv_path.name, len(unique) - len(todo), len(todo))

    errors: set[str] = set()
    started = time.time()
    with cache_path.open("a", encoding="utf-8") as cache_file:
        for i, t in enumerate(todo, start=1):
            try:
                result = classify_policy(t)
            except requests.RequestException:
                logger.exception("Model request failed; progress is saved, rerun to resume")
                raise
            except Exception:
                logger.exception("Classification failed for text %s", i)
                errors.add(t)  # not cached, retried on the next run
                continue
            cache[t] = {"text": t, "v": PROMPT_VERSION, **result}
            cache_file.write(json.dumps(cache[t], ensure_ascii=False) + "\n")
            cache_file.flush()
            if i % 50 == 0 or i == len(todo):
                per_text = (time.time() - started) / i
                logger.info(
                    "%s: %s/%s | %.1fs per text | ~%.0f min left",
                    csv_path.name, i, len(todo), per_text, per_text * (len(todo) - i) / 60,
                )

    records = []
    for t, sent in zip(text, send):
        if not sent:
            records.append(("prefilter", NOT_CDR_RELEVANT, "NOT_RELEVANT", ""))
        elif t in cache:
            c = cache[t]
            records.append(("model", c["label"], c["category"], c["evidence"]))
        else:
            records.append(("error", "ERROR", "", ""))
    labels = pd.DataFrame(records, columns=["stage", "label", "category", "evidence"], index=df.index)

    labels_out = pd.concat([df[[description_column]].rename(columns={description_column: "source_text"}), labels], axis=1)
    labels_out.insert(0, "row_index", df.index)
    labels_out.to_csv(output_dir / f"{csv_path.stem}_labels.csv", index=False, encoding="utf-8")

    cdr_df = df.loc[labels["label"] == CDR_RELEVANT].copy()
    output_path = output_dir / f"{csv_path.stem}_cdr_relevant.csv"
    cdr_df.to_csv(output_path, index=False, encoding="utf-8")
    logger.info(
        "Finished %s | Total: %s | Pre-filtered out: %s | CDR relevant: %s | Errors: %s | Saved: %s",
        csv_path.name, len(df), (~send).sum(), len(cdr_df), (labels["label"] == "ERROR").sum(), output_path,
    )
    logger.info("Categories chosen by the model:\n%s", labels.loc[labels["stage"] == "model", "category"].value_counts().to_string())


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify downloaded policies for CDR relevance.")
    parser.add_argument("--limit", type=int, default=None, help="Classify only the first N rows of each CSV.")
    parser.add_argument("--input-dir", type=Path, default=INPUT_DIR, help=f"Default: {INPUT_DIR}")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR, help=f"Default: {OUTPUT_DIR}")
    parser.add_argument(
        "--keyword-gate",
        action="store_true",
        help="Also require a broad CDR-ish keyword before calling the model (faster, may lose recall).",
    )
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be at least 1")

    if not args.input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {args.input_dir}")

    csv_files = sorted(path for path in args.input_dir.glob("*.csv") if path.is_file())
    if not csv_files:
        logger.warning("No CSV files found in %s", args.input_dir)
        return

    logger.info("Found %s CSV files.", len(csv_files))
    for csv_path in csv_files:
        try:
            process_csv(csv_path, args.output_dir, args.limit, args.keyword_gate)
        except Exception:
            logger.exception("Failed to process file: %s", csv_path.name)
    logger.info("All CSV files processed.")


if __name__ == "__main__":
    main()