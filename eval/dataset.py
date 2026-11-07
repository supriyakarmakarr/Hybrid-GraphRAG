"""
Evaluation Dataset — 50 Benchmark Questions across 4 Core Categories:
1. Simple (15): Direct single-chunk factual retrieval
2. Multi-hop (15): Spanning multiple documents and graph relational hops
3. Out-of-scope / Unanswerable (10): Requires the system to abstain ('pata nahi')
4. Permission-restricted (10): Verifies that only authorized roles receive answers (unauthorized retrieval = 0)
"""

EVAL_QUESTIONS = [
    # ─── Category 1: Simple Direct Factual (15) ─────────────────────────
    {"id": "s01", "type": "simple", "question": "What is the primary purpose of Project Apollo?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "s02", "type": "simple", "question": "Where is Helios Labs headquarters located?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "s03", "type": "simple", "question": "Which programming language is used for data ingestion in Apollo?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "s04", "type": "simple", "question": "What database powers the knowledge graph in this system?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "s05", "type": "simple", "question": "Who leads the core engineering department at Helios Labs?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "s06", "type": "simple", "question": "Which database engine is used for dense vector embeddings?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "s07", "type": "simple", "question": "What algorithm is used for BM25 lexical retrieval?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "s08", "type": "simple", "question": "What is the maximum allowed file upload size?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "s09", "type": "simple", "question": "Which cryptographic algorithm is used to verify JWTs?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "s10", "type": "simple", "question": "How many words overlap between adjacent text chunks?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "s11", "type": "simple", "question": "What model is used for cross-encoder reranking?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "s12", "type": "simple", "question": "What port does the FastAPI application listen on?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "s13", "type": "simple", "question": "Which table in PostgreSQL stores user accounts and assigned roles?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "s14", "type": "simple", "question": "What is the name of the external infrastructure hosting partner for Helios Labs?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "s15", "type": "simple", "question": "In which city does CloudGrid host Kubernetes clusters for Helios Labs?", "expected_has_answer": True, "min_role": "viewer"},

    # ─── Category 2: Multi-Hop Relational Traversal (15) ────────────────
    {"id": "m01", "type": "multihop", "question": "What company hosts infrastructure for the organization where Alice works?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "m02", "type": "multihop", "question": "What technology does the organization partnering with CloudGrid develop for relationship mapping?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "m03", "type": "multihop", "question": "What is the relationship between Alice and the platform that uses Neo4j?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "m04", "type": "multihop", "question": "What company did the executive who approves Helios Labs budgets previously work for?", "expected_has_answer": True, "min_role": "admin"},
    {"id": "m05", "type": "multihop", "question": "Which German city hosts the engineering team that builds components depending on CloudGrid?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "m06", "type": "multihop", "question": "What technology links the ingestion pipeline to the graph engine in Helios Labs' flagship product?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "m07", "type": "multihop", "question": "Who was the former CTO of the provider that operates Helios Labs' Frankfurt clusters?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "m08", "type": "multihop", "question": "What components managed by Alice interact with the Neo4j database instance?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "m09", "type": "multihop", "question": "What organization employs the engineer leading the Apollo development team?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "m10", "type": "multihop", "question": "Which infrastructure vendor employs teams in Frankfurt that support Apollo's host lab?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "m11", "type": "multihop", "question": "Who directs procurement for the system running on CloudGrid's infrastructure?", "expected_has_answer": True, "min_role": "admin"},
    {"id": "m12", "type": "multihop", "question": "What programming language powers the services running under Alice's department?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "m13", "type": "multihop", "question": "What is the corporate connection between Dr. Victor Vance and CloudGrid Inc?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "m14", "type": "multihop", "question": "What graph database is utilized by the automation tool created by Helios Labs?", "expected_has_answer": True, "min_role": "viewer"},
    {"id": "m15", "type": "multihop", "question": "Which department within Helios Labs collaborates with external cloud hosting partners?", "expected_has_answer": True, "min_role": "viewer"},

    # ─── Category 3: Out-of-Scope / Unanswerable ('Pata Nahi') (10) ─────
    {"id": "o01", "type": "out_of_scope", "question": "What is the current stock price of Google in NASDAQ?", "expected_has_answer": False, "min_role": "viewer"},
    {"id": "o02", "type": "out_of_scope", "question": "What will the weather in Tokyo be tomorrow morning?", "expected_has_answer": False, "min_role": "viewer"},
    {"id": "o03", "type": "out_of_scope", "question": "Who won the men's FIFA World Cup championship in 2022?", "expected_has_answer": False, "min_role": "viewer"},
    {"id": "o04", "type": "out_of_scope", "question": "What is the secret recipe for baking New York style cheesecake?", "expected_has_answer": False, "min_role": "viewer"},
    {"id": "o05", "type": "out_of_scope", "question": "What is the personal residential address of the CEO?", "expected_has_answer": False, "min_role": "viewer"},
    {"id": "o06", "type": "out_of_scope", "question": "How many moons orbit the planet Saturn?", "expected_has_answer": False, "min_role": "viewer"},
    {"id": "o07", "type": "out_of_scope", "question": "What was the population of Paris in the year 1800?", "expected_has_answer": False, "min_role": "viewer"},
    {"id": "o08", "type": "out_of_scope", "question": "What is the recommended cure for the common viral flu?", "expected_has_answer": False, "min_role": "viewer"},
    {"id": "o09", "type": "out_of_scope", "question": "Who scored the winning touchdown in Super Bowl XLII?", "expected_has_answer": False, "min_role": "viewer"},
    {"id": "o10", "type": "out_of_scope", "question": "What are the cheat codes for GTA San Andreas on PlayStation?", "expected_has_answer": False, "min_role": "viewer"},

    # ─── Category 4: Permission-Restricted (Admin Only) (10) ────────────
    # For Intern: MUST return zero leaks / 'pata nahi'. For Admin: returns authorized answer.
    {"id": "p01", "type": "permission", "question": "What is the total confidential capital budget for Project Apollo?", "expected_has_answer": True, "min_role": "admin"},
    {"id": "p02", "type": "permission", "question": "How much financial capital expenditure was allocated to Apollo in the fiscal cycle?", "expected_has_answer": True, "min_role": "admin"},
    {"id": "p03", "type": "permission", "question": "Who holds executive approval authority for Project Apollo procurement budgets?", "expected_has_answer": True, "min_role": "admin"},
    {"id": "p04", "type": "permission", "question": "What is the exact dollar amount approved by Dr. Victor Vance for Apollo?", "expected_has_answer": True, "min_role": "admin"},
    {"id": "p05", "type": "permission", "question": "What confidential procurement decisions are overseen by Dr. Victor Vance?", "expected_has_answer": True, "min_role": "admin"},
    {"id": "p06", "type": "permission", "question": "What are the confidential quarterly budget splits for Project Apollo?", "expected_has_answer": True, "min_role": "admin"},
    {"id": "p07", "type": "permission", "question": "What is the executive restricted expenditure ceiling for Helios Labs?", "expected_has_answer": True, "min_role": "admin"},
    {"id": "p08", "type": "permission", "question": "What private financial terms were agreed upon for Apollo infrastructure?", "expected_has_answer": True, "min_role": "admin"},
    {"id": "p09", "type": "permission", "question": "Which executive signs off on restricted budget approvals at Helios Labs?", "expected_has_answer": True, "min_role": "admin"},
    {"id": "p10", "type": "permission", "question": "What is the classified financial audit summary for Apollo Q1 through Q4?", "expected_has_answer": True, "min_role": "admin"},
]
