# What RAG sends to the model

For each long document: where the ~6000 tokens come from, and which fields changed compared with the keyword excerpt (v2).
## Overall

Long documents: 38

Share of the context by source: question: scope 15%, question: methods 15%, question: storage 14%, question: instrument 12%, question: demand 11%, question: targets 11%, question: funding 10%, beginning 7%, own summary 2%, introduction 2%

Fields RAG fixed vs. keyword excerpt: Target_type 9, Target_binding 6, Instrument_broad 3, Instrument_type 3, Specific_method 2, Value_chain_focus 1, Broad_method 1, Policy_scope 1

Fields RAG broke vs. keyword excerpt: Target_type 7, Instrument_broad 7, Broad_method 4, Target_binding 4, Specific_method 3, Policy_scope 2, Value_chain_focus 2, Instrument_type 2


## Row 5: Carbon Credits (Carbon Farming Initiative) Act 2011

- Document 130,713 tokens in 417 chunks; 18 chunks sent (rag+intro)
- Context by source: question: scope 16%, question: methods 16%, question: storage 16%, question: instrument 11%, question: demand 11%, question: funding 11%, question: targets 11%, beginning 5%, introduction 3%
- Target_type: **broken** (expert '', excerpt '', RAG 'CDR')
- Passage (question: targets): "Climate Change Conventio n and Kyoto Protocol etc. (2) The first object of this Act is to remove greenhouse gases from the atmosphere, and avoid emissions of greenhouse gases, in order to meet Australia’s obligations under any or …"
- Passage (question: targets): "(b) in any other case —the greenhouse gas emissions reduction targets included in: (i) Australia’s current nationally determined contribution communicated in accordance with Article 4 of the Paris Agreemen t; or (ii) if that natio…"
- Passage (question: instrument): "(d) giving a notice (including an electronic notice); or (e) making a submission; or (f) making a request; or (g) giving informati on in connection with a request; to the Regulator , where the application, information, notice, sub…"

## Row 37: EU ETS Directive (Directive 2003/87/EC, amended by Directive (EU) 2023/959)

- Document 76,643 tokens in 263 chunks; 20 chunks sent (rag)
- Context by source: question: storage 16%, question: instrument 16%, question: scope 15%, question: methods 14%, question: funding 11%, question: demand 10%, beginning 10%, question: targets 9%
- Policy_scope: **broken** (expert 'Instrument', excerpt 'Instrument', RAG 'Framework')
- Broad_method: **broken** (expert 'Multiple', excerpt 'Multiple', RAG 'Enabling infrastructure; Multiple')
- Target_type: **broken** (expert '', excerpt '', RAG 'CDR; Emissions')
- Target_binding: **broken** (expert '', excerpt '', RAG 'Yes')
- Passage (question: methods): "measures to avoid deforestation and support the protection and restoration of peatland, forests and other land-based ecosystems or marine-based ecosystems, including measures that contribute to the protection, restoration and bett…"
- Passage (question: methods): "to invest in and accelerate the shift to forms of transport which contribute significantly to the decarbonisation of the sector, including the development of climate-friendly passenger and freight rail transport and bus services a…"
- Passage (question: scope): "measures intended to improve energy efficiency, district heating systems and insulation, to support efficient and renewable heating and cooling systems, or to support the deep and staged deep renovation of buildings in accordance …"

## Row 45: TEN-E Regulation (Regulation 2022/869)

- Document 59,671 tokens in 214 chunks; 22 chunks sent (rag)
- Context by source: question: storage 15%, question: scope 15%, question: methods 14%, question: targets 13%, question: demand 12%, question: instrument 12%, beginning 10%, question: funding 9%
- Specific_method: **broken** (expert 'CO₂ transport; CO₂ geological storage', excerpt 'CO₂ geological storage; CO₂ transport', RAG 'CO₂ geological storage')
- Passage (question: targets): "(2) The current binding Union level target for renewable energy for 2030 of at least 32 % of final energy consumption and a headline Union level target for energy efficiency of at least 32,5 % will be revised as part of the Union’…"
- Passage (question: targets): ", the European Parliament called for a revision of Regulation (EU) No 347/2013, taking into account, in particular, the Union’s 2030 targets for energy and climate and its 2050 climate neutrality objectives and the energy efficien…"
- Passage (question: methods): "Moreover, a new infrastructure category should be created for smart gas grids to support investments which integrate a plurality of low-carbon and particularly renewable gases such as biogas, biomethane, and hydrogen, in the gas n…"

## Row 53: Net-Zero Industry Act (Regulation (EU) 2024/1735)

- Document 67,090 tokens in 241 chunks; 22 chunks sent (rag)
- Context by source: question: demand 16%, question: methods 16%, question: storage 15%, question: targets 13%, question: scope 13%, question: funding 11%, beginning 10%, question: instrument 8%
- Target_binding: fixed (expert 'Yes', excerpt 'No', RAG 'Yes')
- Passage (question: targets): "The Union has committed to the accelerated decarbonisation of its economy and the ambitious deployment of renewable energy sources, in order to achieve climate neutrality, namely net-zero emissions or emissions after the deduction…"
- Passage (question: instrument): ", to preserve the Union’s edge on critical and emerging technologies relevant to the green and digital transitions. The third pillar relates to developing the skills needed to make the transition happen and to increase the number …"
- Passage (question: instrument): "2 emissions stemming from the production activities. Supporting those sectors in a targeted manner under this Regulation contributes to ensuring access to a sustainable supply of net-zero technologies in the internal market, incre…"

## Row 54: SEA Directive (2001/42/EC)

- Document 8,946 tokens in 32 chunks; 20 chunks sent (rag)
- Context by source: question: scope 16%, question: storage 16%, question: instrument 14%, question: methods 14%, question: funding 11%, question: targets 10%, beginning 10%, question: demand 8%
- Specific_method: **broken** (expert 'Multiple', excerpt 'Multiple', RAG 'CO₂ geological storage; CO₂ transport')
- Target_type: fixed (expert '', excerpt 'Emissions', RAG '')
- Passage (question: scope): "(1) Article 174 of the Treaty provides that Community policy on the environment is to contribute to, inter alia, the preservation, protection and improvement of the quality of the environment, the protection of human health and th…"
- Passage (question: instrument): "(4) Environmental assessment is an important tool for integrating environmental considerations into the preparation and adoption of certain plans and programmes which are likely to have significant effects on the environment in th…"
- Passage (question: methods): "(8) Action is therefore required at Community level to lay down a minimum environmental assessment framework, which would set out the broad principles of the environmental assessment system and leave the details to the Member Stat…"

## Row 56: EU Bioeconomy Strategy

- Document 10,691 tokens in 36 chunks; 18 chunks sent (rag+intro)
- Context by source: question: methods 16%, question: scope 16%, question: instrument 11%, question: demand 10%, question: targets 10%, question: storage 10%, question: funding 10%, beginning 10%, introduction 7%
- no coded field changed
- Passage (question: methods): "by 2030. For example, in the livestock sector innovations increasingly allow to safely turning certain food waste into feed for animals, provided the applicable rules and legal requirements are observed. 14 It is estimated that th…"
- Passage (question: targets): "17 Furthermore a sustainable bioeconomy will contribute to the Sustainable Development Goals target of achieving land degradation neutrality by 2030 and to the ambition of restoring at least 15% of degraded ecosystems by 2020. 18 …"
- Passage (question: scope): "However, it is necessary to move beyond research and innovation and have a strategic and systemic approach to the deployment of innovations to fully reap the economic, social and environmental benefits of the bioeconomy. Such an a…"

## Row 57: European Green Deal (COM(2019) 640)

- Document 22,224 tokens in 77 chunks; 20 chunks sent (rag)
- Context by source: question: methods 16%, question: storage 15%, question: instrument 15%, question: scope 15%, question: funding 11%, question: targets 10%, beginning 10%, question: demand 8%
- no coded field changed
- Passage (question: targets): "he Commission will work with the Member States to step up the EU’s efforts to ensure that current legislation and policies relevant to the Green Deal are enforced and effectively implemented. 2.1.1. Increasing the EU’s climate amb…"
- Passage (question: storage): "ensure that the price of imports reflect more accurately their carbon content. This measure will be designed to comply with World Trade Organization rules and other international obligations of the EU. It would be an alternative t…"
- Passage (question: methods): "islation by June 2021. When Member States begin updating their national energy and climate plans in 2023, they should reflect the new climate ambition. The Commission will continue to ensure that all relevant legislation is rigoro…"

## Row 61: EU Nationally Determined Contribution 2035

- Document 27,151 tokens in 85 chunks; 18 chunks sent (rag)
- Context by source: question: scope 17%, question: methods 17%, question: storage 16%, question: funding 11%, question: targets 11%, question: demand 11%, question: instrument 11%, beginning 5%
- Broad_method: **broken** (expert 'Multiple', excerpt 'Multiple', RAG 'Enabling infrastructure')
- Target_type: fixed (expert 'Emissions', excerpt 'CDR', RAG 'Emissions')
- Passage (question: methods): "16 https://transport.ec.europa.eu/transport- modes/maritime/decarbonising -maritime -transport- fueleu -maritime_en . 17 EUROSTAT . 18 EUROSTAT . 9 41. Natural gas demand declined by 18% in the period August 2022 and December 2024…"
- Passage (question: storage): "reversing biodiversity loss. 66. In addition to the FF55, several other European Green Deal initiatives aim to maintain and increase carbon sinks and stocks as well as the resilience of the LULUCF sector while contributing to prot…"
- Passage (question: scope): "targets set out in Union law. The Union certification framework will result in an unambiguous positive climate impact. 68. The European Common Agricultural Policy, implemented in European Member States in different ways through Na…"

## Row 71: National Action Plan on Forests and Climate Change (PANByCC)

- Document 43,064 tokens in 137 chunks; 18 chunks sent (rag+summary)
- Context by source: question: methods 16%, question: scope 16%, question: demand 11%, question: funding 11%, question: targets 10%, question: instrument 10%, beginning 10%, question: storage 10%, own summary 6%
- Broad_method: **broken** (expert 'Conventional CDR', excerpt 'Conventional CDR', RAG 'Conventional CDR; Enabling infrastructure')
- Passage (question: demand): "los organismos responsables de su ejecución, las barreras y los instrumentos regulatorios y econó- micos que posibilitan actual o potencialmente la implementación. Además, se menciona el finan-ciamiento existente y necesario para …"
- Passage (question: methods): "como consecuencia de la disminución de la de- forestación en los últimos años, las emisiones del sector se han reducido considerablemente. Por otra parte, el 7 % de las emisiones del sector pro- vienen de los cambios en la biomasa…"
- Passage (question: targets): "mentación del Plan de Acción Sectorial. Por su parte, cada eje operativo define acciones específicas y está asociado a una medida de mitigación concreta que ha sido considerada para la Contribución Nacional. • Ejes estratégicos es…"

## Row 76: Long-Term Emissions Reduction Plan (Australia's Long-Term Strategy)

- Document 79,507 tokens in 250 chunks; 16 chunks sent (rag+summary)
- Context by source: question: scope 16%, own summary 14%, question: targets 11%, question: demand 11%, question: funding 11%, question: methods 11%, question: storage 11%, question: instrument 10%, beginning 6%
- Target_binding: fixed (expert 'No', excerpt 'Yes', RAG 'No')
- Passage (question: instrument): "priority technologies by driving down costs: • Clean hydrogen • Ultra low-cost solar • Energy storage • Low emissions steel and aluminium • Carbon capture and storage • Soil carbon Emerging technologies, such as livestock feed to …"
- Passage (question: scope): "domestically and with our trading partners, 3. Drive down the cost of a range of new energy technologies – bringing a portfolio of technologies to parity is the objective of Australia’s Technology Investment Roadmap, 4. Keep energ…"
- Passage (question: targets): "on our long standing commitment to make a significant contribution to the global effort to tackle climate change, as well as our strong record of achievement. It takes a practical, responsible approach that will take advantage of …"

## Row 84: National Policy and Plan for Recovery of Native Vegetation (Planaveg)

- Document 6,446 tokens in 22 chunks; 20 chunks sent (rag)
- Context by source: question: methods 16%, question: scope 16%, question: storage 15%, question: instrument 12%, question: funding 10%, question: demand 10%, question: targets 10%, beginning 10%
- Value_chain_focus: **broken** (expert 'Supply', excerpt 'Supply', RAG 'Cross-cutting')
- Passage (question: demand): "Novo Acordo do Rio Doce COP30 COP15 5ª Conferência Nacional do Meio Ambiente Documentos COP31 UNFCCC Acesso à Informação 1. Institucional 1.1. Estrutura Organizacional (organograma) 1.2. Competências 1.3. Base Jurídica da Estrutur…"
- Passage (question: demand): "5.1 Repasses e Transparências de Recursos Financeiros 6. Receitas e Despesas 6.1 Receita Pública 6.2 Quadro de Execução de Despesas por Unidade Orçamentária 6.3 Despesas com Diárias e Passagens 6.4 Notas Fiscais Eletrônicas 7. Lic…"
- Passage (question: instrument): "14. Ferramentas e Aspectos Tecnológicos dos Sites Institucionais 14.1. Ferramenta de Pesquisa 14.2 Transparência Proativa 14.3 Tecnologia da Informação Oportunidades de Estágio Oportunidades de estágio 2026 Informações Ambientais …"

## Row 98: Brazil's Nationally Determined Contribution – First NDC

- Document 7,291 tokens in 17 chunks; 13 chunks sent (rag)
- Context by source: question: demand 17%, question: storage 16%, question: methods 16%, question: instrument 14%, question: scope 13%, question: targets 9%, beginning 8%, question: funding 6%
- Value_chain_focus: fixed (expert 'Cross-cutting', excerpt 'Demand', RAG 'Cross-cutting')
- Target_type: fixed (expert 'Emissions', excerpt 'CDR', RAG 'Emissions')
- Passage (question: targets): "Annex Information to facilitate clarity, transparency and understanding of Brazil’s NDC 1. Quantifiable information on the reference point (including, as appropriate, a base year): (a) Reference year(s), base year(s), reference pe…"
- Passage (question: demand): "National Inventory of Anthropogenic Emissions by Sources and Removals by Sinks of Greenhouse Gases not controlled by the Montreal Protocol. (f) Information on the circumstances under which the Party may update the values of the re…"
- Passage (question: scope): "elaboration of a new Climate Change Plan, composed of a National Mitigation Strategy, with eight sectoral mitigation plans and National Adaptation Strategy, as well as fourteen sectoral/thematic adaptation plans. The new Climate C…"

## Row 115: Canada's Nationally Determined Contribution – First NDC (2021 Enhanced)

- Document 27,132 tokens in 85 chunks; 18 chunks sent (rag+intro)
- Context by source: question: storage 16%, question: methods 16%, question: scope 16%, question: instrument 11%, question: funding 11%, question: targets 11%, question: demand 11%, beginning 5%, introduction 3%
- Instrument_broad: **broken** (expert 'Regulatory instrument', excerpt 'Regulatory instrument', RAG 'Other')
- Passage (question: funding): "Canada’s 2021 Budget, $6 billion in the Canada Infrastructure Bank’s Growth Plan and an additional $14.9 billion for public transit and active transportation projects over the next eight years, which includes permanent funding of …"
- Passage (question: demand): "mineral supply chains to support a clean energy transition, and launching a Small Modular Reactor Action Plan. 5 Continuing to Ensure Pollution isn’t Free and Households Get More Money Back: Pricing carbon pollution is the most ef…"
- Passage (question: instrument): "2030, with the continued provision of rising rebates in jurisdictions where the backstop applies. A Clean Fuel Standard, a regulation that will reduce the GHG emissions from producing and using liquid fossil fuels in Canada, as we…"

## Row 116: Canada's Nationally Determined Contribution – Enhanced First NDC (2021)

- Document 27,132 tokens in 85 chunks; 18 chunks sent (rag+intro)
- Context by source: question: storage 16%, question: methods 16%, question: scope 16%, question: instrument 11%, question: funding 11%, question: targets 11%, question: demand 11%, beginning 5%, introduction 3%
- Instrument_broad: **broken** (expert 'Regulatory instrument', excerpt 'Regulatory instrument', RAG 'Other')
- Passage (question: funding): "Canada’s 2021 Budget, $6 billion in the Canada Infrastructure Bank’s Growth Plan and an additional $14.9 billion for public transit and active transportation projects over the next eight years, which includes permanent funding of …"
- Passage (question: demand): "mineral supply chains to support a clean energy transition, and launching a Small Modular Reactor Action Plan. 5 Continuing to Ensure Pollution isn’t Free and Households Get More Money Back: Pricing carbon pollution is the most ef…"
- Passage (question: instrument): "2030, with the continued provision of rising rebates in jurisdictions where the backstop applies. A Clean Fuel Standard, a regulation that will reduce the GHG emissions from producing and using liquid fossil fuels in Canada, as we…"

## Row 133: EU Nationally Determined Contribution 2035 [France]

- Document 27,151 tokens in 85 chunks; 18 chunks sent (rag)
- Context by source: question: scope 17%, question: methods 17%, question: storage 16%, question: funding 11%, question: targets 11%, question: demand 11%, question: instrument 11%, beginning 5%
- Target_type: fixed (expert 'Emissions', excerpt 'CDR', RAG 'Emissions')
- Passage (question: methods): "16 https://transport.ec.europa.eu/transport- modes/maritime/decarbonising -maritime -transport- fueleu -maritime_en . 17 EUROSTAT . 18 EUROSTAT . 9 41. Natural gas demand declined by 18% in the period August 2022 and December 2024…"
- Passage (question: storage): "reversing biodiversity loss. 66. In addition to the FF55, several other European Green Deal initiatives aim to maintain and increase carbon sinks and stocks as well as the resilience of the LULUCF sector while contributing to prot…"
- Passage (question: scope): "targets set out in Union law. The Union certification framework will result in an unambiguous positive climate impact. 68. The European Common Agricultural Policy, implemented in European Member States in different ways through Na…"

## Row 137: India's Long-Term Low-Carbon Development Strategy (LT-LEDS)

- Document 70,085 tokens in 220 chunks; 16 chunks sent (rag+summary)
- Context by source: question: scope 16%, own summary 12%, question: instrument 12%, question: targets 11%, question: storage 11%, question: methods 11%, question: demand 11%, question: funding 11%, beginning 5%
- Target_binding: fixed (expert 'No', excerpt 'Yes', RAG 'No')
- Passage (question: storage): "2.1 Low Carbon Development of Electricity Systems 25 2.1.1 Current Policies and Programme 26 2.1.2 Elements of a Long-Term Low-Carbon Development Strategy 28 2.1.3 Potential Benefits and Challenges 31 2.2 Develop an Integrated, Ef…"
- Passage (question: storage): "• Focusing on demand-side management • Rational utilization of fossil fuel resources, with due regard to energy security • Assessing enablers for low carbon development • Determining green taxonomy and optimum energy mix (compleme…"
- Passage (question: scope): "• Promote resource efficiency within urban planning guidelines, policies, and bylaws • Promote climate responsive and resilient building design, construction, and operation in existing and future buildings and in urban systems • P…"

## Row 142: REDD+ National Strategy 2021–2030

- Document 21,131 tokens in 67 chunks; 17 chunks sent (rag+intro)
- Context by source: question: methods 16%, question: scope 16%, question: instrument 11%, question: funding 11%, question: targets 11%, question: storage 10%, question: demand 10%, introduction 10%, beginning 5%
- Specific_method: fixed (expert 'Afforestation, reforestation, forest management; Peatland and coastal wetland restoration', excerpt 'Afforestation, reforestation, forest management; Peatland and coastal wetland restoration; Soil carbon sequestration in croplands & grasslands', RAG 'Afforestation, reforestation, forest management; Peatland and coastal wetland restoration')
- Passage (question: funding): "1.1. Background ................................ ................................ ................................ . 1 1.2. Process ................................ ................................ ................................…"
- Passage (question: methods): "The ambitious target has been set up particularly on rehabilitation of degraded forest and land (12 million ha) and peatland restoration (2 million ha), along with protect ion of the remaining natural forest through REDD+ and sust…"
- Passage (question: demand): "carbon stocks Methods for calculation of emission reduction Carbon stock difference with gross emissions for reduced deforestation Carbon stock difference with net emissions for reduced deforestation and net removals for enhanced …"

## Row 145: Indonesia's FOLU Net Sink 2030 – Operational Plan (MoEF Decree SK.168/MENLHK/PKTL/PLA.1/2/2022)

- Document 137,483 tokens in 435 chunks; 11 chunks sent (rag+summary)
- Context by source: own summary 41%, question: storage 11%, question: scope 11%, question: methods 11%, question: funding 6%, question: instrument 6%, question: targets 5%, beginning 5%, question: demand 4%
- Instrument_broad: fixed (expert 'Other', excerpt 'Regulatory instrument', RAG 'Other')
- Passage (question: funding): "forest development activities ................................ ................................ ................................ ..... 114 Figure 17. The process of using templates in determining the location for land rehabilitati…"
- Passage (question: methods): "Eighth, prevention of biodiversity loss through area conservation efforts and protection of biodiversity inside and outside protected areas, through habitat fragmentation management and species enrichment; Ninth, management of com…"
- Passage (question: targets): "of GHG emissions and sinks ori ginating from the dynamics of changes in land cover and land use, which is expected to provide the largest contribution to achieving the target of reducing greenhouse gas emissions in Indonesia, as s…"

## Row 167: EU Nationally Determined Contribution 2035 [Italy]

- Document 27,151 tokens in 85 chunks; 18 chunks sent (rag)
- Context by source: question: scope 17%, question: methods 17%, question: storage 16%, question: funding 11%, question: targets 11%, question: demand 11%, question: instrument 11%, beginning 5%
- Target_type: fixed (expert 'Emissions', excerpt 'CDR', RAG 'Emissions')
- Passage (question: methods): "16 https://transport.ec.europa.eu/transport- modes/maritime/decarbonising -maritime -transport- fueleu -maritime_en . 17 EUROSTAT . 18 EUROSTAT . 9 41. Natural gas demand declined by 18% in the period August 2022 and December 2024…"
- Passage (question: storage): "reversing biodiversity loss. 66. In addition to the FF55, several other European Green Deal initiatives aim to maintain and increase carbon sinks and stocks as well as the resilience of the LULUCF sector while contributing to prot…"
- Passage (question: scope): "targets set out in Union law. The Union certification framework will result in an unambiguous positive climate impact. 68. The European Common Agricultural Policy, implemented in European Member States in different ways through Na…"

## Row 171: Act on Promotion of Global Warming Countermeasures (温暖化対策推進法)

- Document 41,132 tokens in 138 chunks; 20 chunks sent (rag)
- Context by source: question: methods 17%, question: demand 17%, question: scope 15%, question: storage 14%, question: instrument 14%, question: funding 11%, question: targets 8%, beginning 5%
- Broad_method: fixed (expert 'Multiple', excerpt 'Enabling infrastructure', RAG 'Multiple')
- Specific_method: fixed (expert 'Multiple', excerpt 'CO₂ geological storage; CO₂ transport', RAG 'Multiple')
- Target_type: fixed (expert 'Emissions', excerpt 'CDR', RAG 'Emissions')
- Target_binding: fixed (expert 'Yes', excerpt 'No', RAG 'Yes')
- Passage (question: storage): "Article 22-8 (Special Provisions of the Natural Parks Act) Article 22-9 (Special Provisions of the River Act) Article 22-10 (Special Provisions of the Act on Waste Management and Public Cleansing) Article 22-11 (Special Provisions…"
- Passage (question: funding): "Article 41 (Promotion of Climate Change Action by the Minister of the Environment) ▶ Chapter VIII Maintaining Greenhouse Gas Absorption by Forests and Plants Article 42 ▶ Chapter IX Inventory of Assigned Amounts Article 43 (Prepar…"
- Passage (question: storage): "Chapter VI Support for Target Business Activities by the Japan Green Investment Corp. for Carbon Neutrality Section 1 General Provisions (Articles 36-2 through 36-7) Section 2 Incorporation (Articles 36-8 through 36-13) Section 3 …"

## Row 182: Japan's Nationally Determined Contribution 2025 (2035/2040 NDC)

- Document 7,010 tokens in 23 chunks; 19 chunks sent (rag)
- Context by source: question: scope 17%, question: storage 16%, question: instrument 16%, question: targets 11%, question: methods 11%, question: demand 11%, question: funding 11%, beginning 6%
- Instrument_broad: **broken** (expert 'Regulatory instrument', excerpt 'Regulatory instrument', RAG 'Other')
- Target_type: **broken** (expert 'Emissions', excerpt 'Emissions', RAG 'CDR')
- Passage (question: targets): "Information to facilitate clarity, transparency and understanding of nationally determined contributions, referred to in deci sion 1/CP.21, paragraph 28 (Decision 4/CMA.1 and Annex I) 1. Quantifiable information on the reference p…"
- Passage (question: targets): "applicable, Parties to provide other relevant information; Not applicable. (d) Target relative to the reference indicator, expressed numerically, for example in percentage or amount of reduction; Japan aims to reduce its greenhous…"
- Passage (question: scope): "date, consistent with any further relevant decision adopted by the Conference of the Parties serving as the meeting of the Parties to the Paris Agreement (CMA); From April 1, 20 31, to March 31, 20 41 (b) Whether it is a single -y…"

## Row 186: Korea Emissions Trading System (K-ETS)

- Document 7,833 tokens in 27 chunks; 21 chunks sent (rag)
- Context by source: question: methods 16%, question: instrument 16%, question: storage 15%, question: targets 14%, question: scope 13%, question: funding 10%, beginning 9%, question: demand 7%
- Instrument_broad: fixed (expert 'Regulatory instrument', excerpt 'Economic instrument', RAG 'Regulatory instrument')
- Passage (question: targets): "The Korea Emissions Trading System (K-ETS) launched in 2015 as East Asia’s first nationwide, mandatory ETS. It covered 77.75% of Korea's GHG emissions in 2023. The K-ETS aims to help the country in its objective to become carbon n…"
- Passage (question: targets): "The K-ETS was established by the “Framework Act on Low Carbon, Green Growth” (2010). It was preceded by a mandatory Target Management System (TMS), launched in 2012, following a two-year pilot phase. The TMS facilitated the collec…"
- Passage (question: methods): "Allocation rules are streamlined into two broad categories: power generation and non-power generation sectors. The auctioning share for the power generation sector will be gradually increased to 50% by 2030. Sectors at risk of car…"

## Row 199: Mexico's Updated Nationally Determined Contribution (NDC Actualización 2022)

- Document 23,778 tokens in 76 chunks; 19 chunks sent (rag+intro)
- Context by source: question: scope 16%, question: storage 15%, question: methods 15%, question: instrument 15%, question: targets 10%, question: funding 10%, question: demand 10%, beginning 5%, introduction 3%
- no coded field changed
- Passage (question: scope): "impacta desproporcionalmente a los pobres y desposeídos, a mujeres y hombres trabajadores, a comunidades indígenas, campesinas, y a migrantes. Se requiere una atención inm ediata en el proyecto nacional a la problemática climática…"
- Passage (question: targets): "a los objetivos más ambiciosos del Acuerdo de París. Finalmente, se ratifica la meta de reducción de las emisiones de carbono negro de 51% de forma no condicionada en 2030, y 70% de forma condicionada. El escenario tendencial proy…"
- Passage (question: scope): "Actualización 2022 - 2030 | PÁG. 12 realizar sus labores en esta modalidad. El trabajo remoto o teletrabajo contribuye a reducir la huella de carbono, así como de otros contaminantes atmosféric os, lo que fortalece las políticas d…"

## Row 203: Strategy and National Plan for Pastures (to 2033)

- Document 433,375 tokens in 1714 chunks; 22 chunks sent (rag)
- Context by source: question: storage 18%, question: methods 15%, question: demand 14%, question: scope 13%, question: instrument 12%, question: targets 11%, beginning 10%, question: funding 7%
- Policy_scope: **broken** (expert 'Framework', excerpt 'Framework', RAG '')
- Instrument_broad: **broken** (expert 'Other', excerpt 'Other', RAG '')
- Target_type: fixed (expert '', excerpt 'CDR', RAG '')
- Target_binding: fixed (expert '', excerpt 'No', RAG '')
- Passage (question: storage): "/heenmedial/behmedial /adiolated/tehmedial/khahmedial/tehmedial /nooniolated/aleffinal/jeemmedial/lamiolated/wawwithhamzaaboveiolated /tehiolated/aleffinal/ainmedial/meemmedial/tehmedial/jeemmedial/meemmedial/lamiolated/al…"
- Passage (question: instrument): "/لadmedial/fehmedial/lamiolated/alefiolated /meemiolated/tehmedial/hehmedial/yehmedial/wawiolated /arabiccomma/yehfinal/aininitial/rehiolated/lamiolated/alefiolated/wawiolated /tehmarbutafinal/yehmedial/wawiolated/ainini…"
- Passage (question: instrument): "/لyehmedial/wawiolated/tahiolated/lamiolated/alefiolated/wawiolated /tahiolated/eenmedial/wawiolated/tehmedial/meemmedial/lamiolated/alefiolated /alefmakuraiolated/daliolated/meemmedial/lamiolated/alefiolated /yehfi…"

## Row 207: Saudi Arabia Second Nationally Determined Contribution (2025)

- Document 14,435 tokens in 46 chunks; 16 chunks sent (rag+intro)
- Context by source: question: scope 17%, introduction 14%, question: funding 11%, question: methods 11%, question: targets 11%, question: demand 11%, question: storage 11%, question: instrument 9%, beginning 6%
- Instrument_broad: **broken** (expert 'Regulatory instrument', excerpt 'Regulatory instrument', RAG 'Other')
- Passage (question: scope): "and pathways for climate action , sustainable developme nt, and net-zero ambitions. The ambitions outlined in this NDC are contingent on sustained economic growth and diversification, supported by a robust contribution from hydroc…"
- Passage (question: targets): "The Kingdom aims to reduce, remove, and avoid GHG emissions by 335 million tons of CO 2eq annually to be reached by 2040, expressed through a combination of GHG and non -GHG metrics. Non -GHG metrics include an ambition of, inter …"
- Passage (question: demand): "However, the implementation of the Kingdom’s NDC could face barriers arising from climate change related trade -restrictive unilateral measures and cross -border directives that introduce and actively impose externally defined cri…"

## Row 208: Forestry 2030 Roadmap (Forestry Strategy 2009–2030)

- Document 27,138 tokens in 93 chunks; 18 chunks sent (rag+summary)
- Context by source: question: scope 17%, own summary 11%, question: methods 11%, question: funding 11%, question: storage 11%, question: instrument 11%, question: targets 11%, question: demand 10%, beginning 6%
- Broad_method: **broken** (expert 'Conventional CDR', excerpt 'Conventional CDR', RAG 'Enabling infrastructure')
- Passage (question: funding): "determined by ongoing research and review of local and international information on the effects sustainable management and use of these resources. The process of developing Forestry 2030 Roadmap, and the involvement of key role pl…"
- Passage (question: storage): "1. INTRODUCTION ................................................................................................................................................... 2 2. ENVIRONMENTAL, SOCIAL AND ECONOMIC CONTEXT ..................…"
- Passage (question: targets): "4.1 CHALLENGE 1: LAND REFORM ....................................................................................................................... 15 4.1.1 POST SETTLEMENT SUPPORT TO COMMUNITIES/ COMMUNITY READINESS .....15 4.1.…"

## Row 219: Storage of Carbon Dioxide (Licensing etc.) Regulations 2010

- Document 21,318 tokens in 74 chunks; 21 chunks sent (rag)
- Context by source: question: instrument 16%, question: methods 14%, question: storage 14%, question: demand 14%, question: scope 14%, question: funding 10%, question: targets 10%, beginning 9%
- Instrument_type: **broken** (expert 'regulatory_safeguard; mrv_standard', excerpt 'regulatory_safeguard; mrv_standard', RAG 'target; mrv_standard; regulatory_safeguard; community_safeguard; operating_subsidy; public_loan; public_procurement')
- Target_type: **broken** (expert '', excerpt '', RAG 'CO₂ storage')
- Target_binding: **broken** (expert '', excerpt '', RAG 'No')
- Passage (question: demand): "legislation which levies a tax in relation to greenhouse gas emissions attributable to a person; ] “ CO 2 ” means carbon dioxide; “ corrective measures plan ” has the meaning given by regulation 7(6); “ the Directive ” means Direc…"
- Passage (question: scope): "of the European Parliament and of the Council of 13 October 2003 establishing a scheme for greenhouse gas emission allowance trading within the Community and amending Council Directive 96/61/EC M7 ; “ financial security ” includes…"
- Passage (question: targets): "the establishment or maintenance in a controlled place which is not in, under or over the territorial sea adjacent to Scotland of an installation for the purposes of activities within section 17(2), (and “ licence holder ” is to b…"

## Row 233: Carbon Capture and Storage Infrastructure Fund (CIF)

- Document 7,992 tokens in 27 chunks; 20 chunks sent (rag)
- Context by source: question: instrument 17%, question: methods 16%, question: storage 15%, question: scope 14%, question: targets 11%, question: funding 11%, question: demand 10%, beginning 5%
- Policy_scope: fixed (expert 'Instrument', excerpt 'Framework', RAG 'Instrument')
- Instrument_broad: fixed (expert 'Economic instrument', excerpt 'Regulatory instrument', RAG 'Economic instrument')
- Instrument_type: fixed (expert 'capital_subsidy; operating_subsidy', excerpt 'capital_subsidy; operating_subsidy; tax_incentive', RAG 'capital_subsidy; operating_subsidy')
- Target_type: **broken** (expert '', excerpt '', RAG 'CO₂ storage')
- Passage (question: storage): "News stories, speeches, letters and notices Guidance and regulation Detailed guidance, regulations and rules Research and statistics Reports, analysis and official statistics Policy papers and consultations Consultations and strat…"
- Passage (question: storage): "psi@nationalarchives.gov.uk . Where we have identified any third party copyright information you will need to obtain permission from the copyright holders concerned. This publication is available at https://www.gov.uk/government/p…"
- Passage (question: funding): "capital expenditure for CCUS-enabled ‘blue’ hydrogen projects from the £240m Net Zero Hydrogen Fund (NZHF). Funding for electrolytic ‘green’ hydrogen projects will be allocated through a separate process. Support for power CCUS wi…"

## Row 250: The United States of America Nationally Determined Contribution (2024) – 61–66% by 2035

- Document 18,639 tokens in 60 chunks; 14 chunks sent (rag+intro)
- Context by source: introduction 24%, question: demand 11%, question: scope 11%, question: instrument 11%, question: targets 11%, question: methods 11%, question: storage 10%, beginning 6%, question: funding 5%
- Target_type: fixed (expert 'Emissions', excerpt 'CDR', RAG 'Emissions')
- Passage (question: scope): "economic growth in every sector and every region of the country. Advanced through hundreds of policies and measures undertaken by federal, state, territorial, Tribal, and local governments, the strategy includes historic passage o…"
- Passage (question: storage): "coming from wind, solar, and battery storage. New federal regulations require power companies to control pollution from coal and new gas -fired power plants, further cutting greenhouse gas emissions and protecting public health . …"
- Passage (question: demand): "durable wood products, as well as high-integrity carbon markets that align with the voluntary carbon market joint policy statement and principles announced in May 2024. States , Tribes, and local governments can encourage the adop…"

## Row 252: Carbon Negative Shot (DOE Energy Earthshots)

- Document 6,634 tokens in 21 chunks; 17 chunks sent (rag+summary)
- Context by source: question: methods 17%, question: scope 16%, question: targets 11%, question: demand 11%, question: instrument 11%, question: storage 11%, question: funding 10%, own summary 7%, beginning 6%
- no coded field changed
- Passage (question: methods): "Pillar 3: Map Gigaton Scale Pathways ....................................................................................................................7 Pillar 4: Enable and Encourage CDR Markets ................................…"
- Passage (question: scope): "enhancing measurement, monitoring, reporting and verification approaches, building confidence for private markets that will supply the majority of early demand during the development phase to 2030. CDR pathways, like any clean ene…"
- Passage (question: targets): "2 https://www.energy.gov/fecm/carbon- negative- shot The Carbon Negative Shot ™ is an all -hands -on-deck call for innovation in carbon dioxide removal pathways that will capture carbon dioxide from the atmosphere and store it at …"

## Row 255: Infrastructure Investment and Jobs Act (IIJA) – carbon management

- Document 717,449 tokens in 2290 chunks; 19 chunks sent (rag)
- Context by source: question: methods 16%, question: scope 16%, question: storage 16%, question: instrument 16%, question: demand 11%, question: funding 10%, question: targets 10%, beginning 5%
- Instrument_broad: **broken** (expert 'Economic instrument', excerpt 'Economic instrument', RAG 'Regulatory instrument')
- Instrument_type: **broken** (expert 'capital_subsidy; operating_subsidy', excerpt 'capital_subsidy; operating_subsidy', RAG 'crediting_mechanism; compliance_market_integration')
- Passage (question: storage): "Sec. 40205. Rare earth elements demonstration facility. Sec. 40206. Critical minerals supply chains and reliability. Sec. 40207. Battery processing and manufacturing. Sec. 40208. Electric drive vehicle battery recycling and second…"
- Passage (question: instrument): "may help reduce port-related emissions from idling trucks; and (C) <<NOTE: Coordination.>> coordinate and provide funding to test, evaluate, and deploy projects that reduce port-related emissions from idling trucks, including thro…"
- Passage (question: funding): "this section and the applicable notice of funding opportunity; and ``(ii) the Federal assistance to be provided for the project under this section is more than $80,000,000. ``(B) Terms.--A phased funding agreement shall-- ``(i) es…"

## Row 256: SCALE Act core implementation via IIJA/CIFIA

- Document 717,449 tokens in 2290 chunks; 19 chunks sent (rag)
- Context by source: question: methods 16%, question: scope 16%, question: storage 16%, question: instrument 16%, question: demand 11%, question: funding 10%, question: targets 10%, beginning 5%
- Instrument_broad: **broken** (expert 'Economic instrument', excerpt 'Economic instrument', RAG 'Regulatory instrument')
- Specific_method: **broken** (expert 'CO₂ transport; CO₂ geological storage', excerpt 'CO₂ geological storage; CO₂ transport', RAG 'Carbon capture, transport, utilization, and storage; CO₂ geological storage')
- Target_type: **broken** (expert '', excerpt '', RAG 'CO₂ storage')
- Target_binding: **broken** (expert '', excerpt '', RAG 'No')
- Passage (question: storage): "Sec. 40205. Rare earth elements demonstration facility. Sec. 40206. Critical minerals supply chains and reliability. Sec. 40207. Battery processing and manufacturing. Sec. 40208. Electric drive vehicle battery recycling and second…"
- Passage (question: instrument): "may help reduce port-related emissions from idling trucks; and (C) <<NOTE: Coordination.>> coordinate and provide funding to test, evaluate, and deploy projects that reduce port-related emissions from idling trucks, including thro…"
- Passage (question: funding): "this section and the applicable notice of funding opportunity; and ``(ii) the Federal assistance to be provided for the project under this section is more than $80,000,000. ``(B) Terms.--A phased funding agreement shall-- ``(i) es…"

## Row 259: EPA Underground Injection Control – Class VI Well Regulations

- Document 6,561 tokens in 23 chunks; 21 chunks sent (rag)
- Context by source: question: scope 16%, question: storage 15%, question: demand 15%, question: methods 13%, question: targets 11%, question: funding 10%, question: instrument 10%, beginning 9%
- Instrument_type: fixed (expert 'regulatory_safeguard; mrv_standard', excerpt 'regulatory_safeguard; compliance_market_integration', RAG 'regulatory_safeguard; mrv_standard')
- Target_type: **broken** (expert '', excerpt '', RAG 'CO₂ storage')
- Target_binding: **broken** (expert '', excerpt '', RAG 'No')
- Passage (question: scope): "captured from point source emissions, such as from an industrial facility (e.g., steel and cement production) or energy production (e.g., ethanol, hydrogen production, or power plants), as well as CO 2 captured directly from the a…"
- Passage (question: targets): "Injection of carbon dioxide is typically thousands of feet below the surface into rock formations isolated from underground sources of drinking water. Figure is not to scale. Requirements include: Site characterization requirement…"
- Passage (question: storage): "Appropriate construction materials depend upon site specific conditions including the CO 2 stream, the formation fluids, and formation temperatures and pressures. Laboratory testing and modeling based upon site specific conditions…"

## Row 270: Action Plan for Carbon Dioxide Peaking Before 2030 [2030年前碳达峰行动方案]

- Document 17,949 tokens in 67 chunks; 23 chunks sent (rag)
- Context by source: question: scope 18%, question: instrument 16%, question: methods 14%, question: demand 13%, question: targets 10%, beginning 10%, question: funding 10%, question: storage 9%
- no coded field changed
- Passage (question: scope): "2. Working Guidelines · Planning from an overall perspective and implementing tailored policies. We will take a whole-of-nation approach, bolstering top-level design and coordination on all sides. In all regions, fields, and indus…"
- Passage (question: targets): "During the 15th Five-Year Plan period, major progress will be made in adjustment of the industrial structure, a clean, safe, efficient and low-carbon energy system will be preliminary established, low-carbon development models wil…"
- Passage (question: targets): "We will see that the goal to peak carbon dioxide emissions permeates the whole process and every aspect of economic and social development. Particular focus will be placed on implementation of ten major peaking carbon dioxide emis…"

## Row 284: China National Biodiversity Conservation Strategy and Action Plan (2011–2030) [中国生物多样性保护战略与行动计划]

- Document 25,024 tokens in 79 chunks; 18 chunks sent (rag+summary)
- Context by source: question: scope 17%, question: methods 17%, question: storage 16%, question: demand 11%, question: funding 11%, question: targets 11%, question: instrument 11%, beginning 5%, own summary 1%
- no coded field changed
- Passage (question: storage): "is still quite heavy . The monitoring and warning system on biodiversity has not been set up. China also has such problems as insufficient investment in biodiversity , inadequate capacit ies of management , protection and fundamen…"
- Passage (question: scope): "The overall goal is to achieve the conservation and sustainable use of biodiversity and fair and equitable sharing of benefits arising from use of genetic resources, guided by the scientific development principles and the principl…"
- Passage (question: targets): " Establish a system of biodiversity monitoring, evaluation and warning , and set up a system to manage trade in biological resources as well as a system for access to and benefit sharing of genetic resources. Mid-term Goal By 202…"

## Row 292: EU Nationally Determined Contribution 2035 [Germany]

- Document 27,151 tokens in 85 chunks; 18 chunks sent (rag)
- Context by source: question: scope 17%, question: methods 17%, question: storage 16%, question: funding 11%, question: targets 11%, question: demand 11%, question: instrument 11%, beginning 5%
- no coded field changed
- Passage (question: methods): "16 https://transport.ec.europa.eu/transport- modes/maritime/decarbonising -maritime -transport- fueleu -maritime_en . 17 EUROSTAT . 18 EUROSTAT . 9 41. Natural gas demand declined by 18% in the period August 2022 and December 2024…"
- Passage (question: storage): "reversing biodiversity loss. 66. In addition to the FF55, several other European Green Deal initiatives aim to maintain and increase carbon sinks and stocks as well as the resilience of the LULUCF sector while contributing to prot…"
- Passage (question: scope): "targets set out in Union law. The Union certification framework will result in an unambiguous positive climate impact. 68. The European Common Agricultural Policy, implemented in European Member States in different ways through Na…"

## Row 296: Carbon Dioxide Storage Act (Kohlendioxidspeicherungsgesetz – KSpG)

- Document 29,736 tokens in 94 chunks; 19 chunks sent (rag)
- Context by source: question: storage 17%, question: methods 17%, question: scope 16%, question: instrument 16%, question: demand 11%, question: targets 11%, question: funding 6%, beginning 5%
- Value_chain_focus: **broken** (expert 'Cross-cutting', excerpt 'Cross-cutting', RAG 'Supply')
- Instrument_type: fixed (expert 'regulatory_safeguard; mrv_standard', excerpt 'target; mrv_standard; regulatory_safeguard; community_safeguard', RAG 'regulatory_safeguard; mrv_standard')
- Target_type: fixed (expert '', excerpt 'CO₂ storage', RAG '')
- Target_binding: fixed (expert '', excerpt 'Yes', RAG '')
- Passage (question: instrument): "Forschungsspeicher § 36 Geltung von Vorschriften § 37 Genehmigung von Forschungsspeichern § 38 Anwendung von Vorschriften Kapitel 7 Schlussbestimmungen § 39 Zuständige Behörden § 40 Wissensaustausch; Verordnungsermächtigung § 41 G…"
- Passage (question: scope): "(4) Dieses Gesetz gilt nach Maßgabe des Seerechtsübereinkommens der Vereinten Nationen vom 10. Dezember 1982 (BGBl. 1994 II S. 1798, 1799) auch im Bereich der ausschließlichen Wirtschaftszone und des Festlandsockels. (5) Die Lände…"
- Passage (question: scope): "Speichervorhaben zur Erforschung, Entwicklung und Erprobung neuer Materialien, Produkte und Verfahren, in die insgesamt weniger als 100 000 Tonnen Kohlendioxid injiziert werden; 4. Gesteinsschichten abgrenzbare Bereiche im geologi…"

## Row 322: Turkey's Updated First Nationally Determined Contribution (2021/2023)

- Document 24,661 tokens in 78 chunks; 16 chunks sent (rag+intro)
- Context by source: question: scope 17%, introduction 15%, question: funding 11%, question: methods 11%, question: storage 11%, question: instrument 11%, question: demand 11%, question: targets 7%, beginning 6%
- no coded field changed
- Passage (question: funding): "Waste Sector ................................ ................................ ................................ .................... 16 Land Use, Land -Use Change and Forestry (LULUCF) ................................ ............…"
- Passage (question: scope): "change are determined in line with the Development Plan2. Türkiye's new 2030 target is based on the modeled impact of these policies and strategies and is aligned with its net zero target . GENERAL OVERVIEW OF TÜRKİYE'S CURRENT AN…"
- Passage (question: instrument): "key for greening the financial system. There have been number of developments to improve the green financial ecosystem in Türkiye. One of the most important of these developments is “Sustainable Ba nking Strategic Plan 2022 -2025"…"
