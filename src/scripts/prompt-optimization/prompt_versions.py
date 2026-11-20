"""Prompt versions for the coding runs.

v1  The first-loop prompt exactly as it is (codebook definitions + general rules).
v2  v1 plus targeted coding clarifications for the four systematic errors that
    the zero-shot benchmark and Elina's feedback point to:

    1. Policy_scope        frameworks coded as instruments
    2. Value_chain_focus   cross-cutting policies coded as demand
    3. Instrument_broad    strategies and plans coded as regulatory instruments
    4. Instrument_type     instruments that are only mentioned are listed

    The clarifications were written from the error analysis on the TRAIN split
    only (see ``error-analysis.script.py``), so the test split stays an
    independent check. They spell out how the expert coding applies the codebook;
    they should be confirmed with IIASA before the final report.

    v2 also replaces the user-prompt header "Code this instrument" with
    "Code this policy", because calling every document an "instrument" pushes the
    model towards Policy_scope = Instrument.
"""

from __future__ import annotations

PROMPT_V1 = "v1"
PROMPT_V2 = "v2"
PROMPT_VERSIONS = [PROMPT_V1, PROMPT_V2]

V2_HEADING = "Coding clarifications (follow these when the definitions above leave room):"

V2_RULES = [
    # 1 Policy_scope
    "Policy_scope: code Framework when the document sets overall direction for climate or CDR policy: "
    "Nationally Determined Contributions (NDCs), long-term strategies, climate laws and acts that set "
    "national targets, national plans, roadmaps, action plans, visions and strategies, and programmes "
    "that bundle several measures. This holds even when the document lists specific measures. Code "
    "Instrument only when the document itself "
    "creates one concrete tool: a grant or subsidy programme, a tax credit, a crediting scheme, an "
    "emissions trading system, a procurement programme, or a specific permit rule or technical standard.",
    # 2 Value_chain_focus
    "Value_chain_focus: an economy-wide, sectoral or net-zero emissions target does not by itself make a "
    "policy Demand. NDCs and climate laws are usually Cross-cutting; strategies and plans are usually "
    "Cross-cutting, or Supply when they mainly expand removal activities such as forests. Use Demand only "
    "when the policy itself creates buyers or payment for removal units: rules for removal units in a "
    "compliance market or emissions trading system, carbon crediting or offset schemes, carbon taxes that "
    "accept credits, or government purchase, procurement or contracts for difference. Use Supply when the "
    "policy lowers the cost or risk of producing removals (grants, subsidies, R&D funding, loans, forestry "
    "or restoration programmes). The only allowed values are Cross-cutting, Supply and Demand; never put "
    "an instrument category here.",
    # 3 Instrument_broad
    "Instrument_broad: Regulatory instrument is for legally binding acts (laws, acts, regulations, "
    "decrees, directives) and for NDCs submitted under the Paris Agreement. Strategies, plans, roadmaps, "
    "white papers, visions, programmes and communications that do not themselves set binding rules are "
    "Other, or Information instrument when their main purpose is guidance or information. Being an "
    "official government document does not make a policy a Regulatory instrument.",
    # 4 Instrument_type
    "Instrument_type: list only the instrument types that this policy itself establishes, funds or "
    "legally sets up. Do not list measures that the document only mentions, plans for later, describes as "
    "options, or that belong to other policies. Most policies have one instrument type and rarely more "
    "than two or three. For frameworks and strategies use target when the document sets a quantified "
    "target, otherwise Other.",
]

V2_USER_PROMPT_HEADER = (
    "Inventory context, already assigned. Code this policy rather than restating these fields:"
)


def instructions_for(version: str, base_instructions: str) -> str:
    """Model instructions for a prompt version, built on the first-loop instructions."""
    if version == PROMPT_V1:
        return base_instructions
    if version == PROMPT_V2:
        rules = "\n".join(f"- {rule}" for rule in V2_RULES)
        return f"{base_instructions}\n\n{V2_HEADING}\n{rules}"
    raise ValueError(f"unknown prompt version: {version}")


def user_prompt_header(version: str, base_header: str) -> str:
    if version == PROMPT_V1:
        return base_header
    if version == PROMPT_V2:
        return V2_USER_PROMPT_HEADER
    raise ValueError(f"unknown prompt version: {version}")
