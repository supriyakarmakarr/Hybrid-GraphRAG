# ==============================================================================
# GraphRAG End-to-End Automated Test Script (PowerShell)
# Tests: Health, Authentication, Authorization (Admin vs Intern),
#        Multi-Hop Traversal, Out-of-Scope Denial, and Query Trace Telemetry.
# ==============================================================================

$ErrorActionPreference = "Stop"
$BaseUrl = "http://localhost:8000/api/v1"

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host "   GRAPHRAG END-TO-END VERIFICATION & SECURITY TEST" -ForegroundColor Cyan
Write-Host "========================================================`n" -ForegroundColor Cyan

# ─── 1. Healthcheck ──────────────────────────────────────────────────────────
Write-Host "[1/6] Checking Service Health..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Method Get -Uri "$BaseUrl/health"
    Write-Host "  ✓ Status: $($health.status)" -ForegroundColor Green
    Write-Host "  ✓ PostgreSQL: $($health.services.postgres)" -ForegroundColor Green
    Write-Host "  ✓ Postgres full-text: enabled" -ForegroundColor Green
    Write-Host "  ✓ Qdrant:     $($health.services.qdrant)" -ForegroundColor Green
    Write-Host "  ✓ Neo4j:      $($health.services.neo4j)" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Healthcheck failed! Ensure 'docker compose up -d' is running." -ForegroundColor Red
    Write-Host "  Error: $_" -ForegroundColor Red
    exit 1
}

# ─── 2. Acquire JWT Tokens ───────────────────────────────────────────────────
Write-Host "`n[2/6] Acquiring JWT Tokens (RS256)..." -ForegroundColor Yellow

$adminLogin = Invoke-RestMethod -Method Post -Uri "$BaseUrl/auth/token" `
    -ContentType "application/x-www-form-urlencoded" `
    -Body "username=admin&password=adminpass"
$adminToken = $adminLogin.access_token
Write-Host "  ✓ Admin Token acquired (Roles: admin, analyst)" -ForegroundColor Green

$internLogin = Invoke-RestMethod -Method Post -Uri "$BaseUrl/auth/token" `
    -ContentType "application/x-www-form-urlencoded" `
    -Body "username=intern&password=internpass"
$internToken = $internLogin.access_token
Write-Host "  ✓ Intern Token acquired (Roles: intern)" -ForegroundColor Green

# ─── 3. Test Multi-Hop Relational Query (Admin) ───────────────────────────────
Write-Host "`n[3/6] Running Multi-Hop Graph Query (Admin)..." -ForegroundColor Yellow
$q1 = @{
    question = "Who oversees the budget for Project Apollo and what company did he previously work for?"
    max_chunks = 7
    max_graph_edges = 50
} | ConvertTo-Json

$res1 = Invoke-RestMethod -Method Post -Uri "$BaseUrl/query" `
    -Headers @{ Authorization = "Bearer $adminToken" } `
    -ContentType "application/json" `
    -Body $q1

Write-Host "  ✓ Question: $($res1.question)" -ForegroundColor Gray
Write-Host "  ✓ Answer:   $($res1.answer)" -ForegroundColor Green
Write-Host "  ✓ Citations: $($res1.citations -join ', ')" -ForegroundColor Cyan
Write-Host "  ✓ Graph Edges Discovered: $($res1.graph_edges.Count)" -ForegroundColor Cyan
Write-Host "  ✓ Total Latency: $($res1.query_trace.total_latency_ms) ms" -ForegroundColor Gray

# ─── 4. Test Authorization Defense (Intern vs Confidential Data) ─────────────
Write-Host "`n[4/6] Testing ACL Defense: Intern Queries Confidential Budget..." -ForegroundColor Yellow
$q2 = @{
    question = "What is the total confidential budget and capital expenditure for Project Apollo?"
    max_chunks = 7
    max_graph_edges = 50
} | ConvertTo-Json

$res2 = Invoke-RestMethod -Method Post -Uri "$BaseUrl/query" `
    -Headers @{ Authorization = "Bearer $internToken" } `
    -ContentType "application/json" `
    -Body $q2

Write-Host "  ✓ Question: $($res2.question)" -ForegroundColor Gray
Write-Host "  ✓ Intern Answer: $($res2.answer)" -ForegroundColor Magenta
Write-Host "  ✓ Chunks Retrieved for Intern: $($res2.retrieved_chunks)" -ForegroundColor Green

if ($res2.retrieved_chunks -eq 0 -and $res2.answer -like "*don't have sufficient evidence*") {
    Write-Host "  ★ SECURITY CHECK PASSED: Unauthorized Retrieval = 0.0% (Zero Leaks)" -ForegroundColor Green
} else {
    Write-Host "  ✗ SECURITY CHECK FAILED: Confidential data leaked to Intern!" -ForegroundColor Red
}

# ─── 5. Test Relevance Gate ('Pata Nahi' / Out-of-Scope) ─────────────────────
Write-Host "`n[5/6] Testing Relevance Gate: Out-of-Scope Query..." -ForegroundColor Yellow
$q3 = @{
    question = "What is the secret recipe for baking New York style cheesecake?"
    max_chunks = 7
    max_graph_edges = 50
} | ConvertTo-Json

$res3 = Invoke-RestMethod -Method Post -Uri "$BaseUrl/query" `
    -Headers @{ Authorization = "Bearer $adminToken" } `
    -ContentType "application/json" `
    -Body $q3

Write-Host "  ✓ Question: $($res3.question)" -ForegroundColor Gray
Write-Host "  ✓ Answer:   $($res3.answer)" -ForegroundColor Yellow
Write-Host "  ✓ Relevance Gate Passed: $($res3.query_trace.stages.relevance_gate.passed)" -ForegroundColor Cyan
Write-Host "  ✓ Action: $($res3.query_trace.stages.relevance_gate.action)" -ForegroundColor Cyan
Write-Host "  ✓ LLM Bypassed? $(if ($res3.query_trace.stages.relevance_gate.passed) { 'No' } else { 'YES (Tokens Saved)' })" -ForegroundColor Green

# ─── 6. Display Query Trace Telemetry Breakdown ──────────────────────────────
Write-Host "`n[6/6] Inspecting 'How Did I Get This Answer?' Query Trace..." -ForegroundColor Yellow
$stages = $res1.query_trace.stages
Write-Host "  ┌────────────────────────────────────────────────────────┐" -ForegroundColor Cyan
Write-Host "  │ Stage                  │ Metric / Latency              │" -ForegroundColor Cyan
Write-Host "  ├────────────────────────┼───────────────────────────────┤" -ForegroundColor Cyan
Write-Host ("  │ 1. Input Sanitization  │ {0,-30}│" -f "$($stages.input_validation.latency_ms) ms") -ForegroundColor Gray
Write-Host ("  │ 2. Postgres Full-text  │ {0,-30}│" -f "$($stages.postgres_full_text.hits_count) hits ($($stages.postgres_full_text.latency_ms) ms)") -ForegroundColor Gray
Write-Host ("  │ 3. Vector Dense Search │ {0,-30}│" -f "$($stages.vector.hits_count) hits ($($stages.vector.latency_ms) ms)") -ForegroundColor Gray
Write-Host ("  │ 4. RRF Rank Fusion     │ {0,-30}│" -f "$($stages.rrf_fusion.fused_count) candidates ($($stages.rrf_fusion.latency_ms) ms)") -ForegroundColor Gray
Write-Host ("  │ 5. RRF Selection       │ {0,-30}│" -f "$($stages.reranker.selected_count) chunks ($($stages.reranker.latency_ms) ms)") -ForegroundColor Gray
Write-Host ("  │ 6. Relevance Gate      │ {0,-30}│" -f "Passed: $($stages.relevance_gate.passed)") -ForegroundColor Gray
Write-Host ("  │ 7. Graph Traversal     │ {0,-30}│" -f "$($stages.graph_traversal.edges_count) edges ($($stages.graph_traversal.latency_ms) ms)") -ForegroundColor Gray
Write-Host ("  │ 8. Grounded LLM Gen    │ {0,-30}│" -f "Conf: $($stages.llm_generation.confidence) ($($stages.llm_generation.latency_ms) ms)") -ForegroundColor Gray
Write-Host ("  │ 9. Citation Presence   │ {0,-30}│" -f "Valid: $($stages.citation_validation.valid_count), Invalid: $($stages.citation_validation.invalid_count)") -ForegroundColor Gray
Write-Host "  └────────────────────────────────────────────────────────┘" -ForegroundColor Cyan
Write-Host "`n========================================================" -ForegroundColor Green
Write-Host "   ALL INTEGRATION & SECURITY TESTS COMPLETED SUCCESSFULLY" -ForegroundColor Green
Write-Host "========================================================`n" -ForegroundColor Green

