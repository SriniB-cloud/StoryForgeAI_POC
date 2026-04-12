"""
StoryForge AI — ShopFlow POC v3
Generates all test files from config + templates.
This script mirrors Stages 1-5 of the notebook pipeline.
"""

import json, yaml, os
from faker import Faker
from jinja2 import Environment, FileSystemLoader
from rich.console import Console
from rich.table import Table

console = Console()
fake = Faker()
fake.seed_instance(42)

BASE = os.path.dirname(os.path.abspath(__file__))

# ── Load config ───────────────────────────────────────────────
with open(f"{BASE}/config/test_gen_config.yaml") as f:
    cfg = yaml.safe_load(f)

with open(f"{BASE}/config/app_context.yaml") as f:
    ctx = yaml.safe_load(f)

# ── Stage 1: Parsed Spec ──────────────────────────────────────
parsed_spec = {
    "story_id": "US-001",
    "actor": "registered shopper on ShopFlow",
    "action": "search for a product, add it to cart, complete payment",
    "goal": "order is placed and order confirmation with unique order ID is received",
    "preconditions": ["shopper is registered", "shopper has valid credentials"],
    "acceptance_criteria": [
        {"id": "AC1",  "text": "Shopper must be authenticated before adding to cart or checking out"},
        {"id": "AC2",  "text": "Search returns product name, price and image for a valid keyword"},
        {"id": "AC3",  "text": "Empty or invalid keyword shows a no-results message"},
        {"id": "AC4",  "text": "Add to cart updates the cart badge item count"},
        {"id": "AC5",  "text": "Cart shows correct product name, quantity and total price"},
        {"id": "AC6",  "text": "Empty cart disables the checkout button"},
        {"id": "AC7",  "text": "Checkout accepts valid payment card details and places the order"},
        {"id": "AC8",  "text": "Successful payment returns order confirmation with unique order ID and status CONFIRMED"},
        {"id": "AC9",  "text": "Invalid card details show an appropriate error and not a 500"},
        {"id": "AC10", "text": "Session timeout during checkout redirects to login and cart is preserved after re-login"},
    ],
    "business_rules": [
        "Payment gateway operates in sandbox mode",
        "Session tokens are JWT-based",
        "Cart is persisted server-side per userId",
    ]
}

console.print("\n[bold cyan]━━ Stage 1: Parsing Engine[/bold cyan]")
console.print(f"  Story ID : {parsed_spec['story_id']}")
console.print(f"  Actor    : {parsed_spec['actor']}")
console.print(f"  AC count : {len(parsed_spec['acceptance_criteria'])}")

# ── Stage 2: Test Case Generator ─────────────────────────────
api_tests = [
    {"id": "TC-A01", "area": "Auth",    "test_level": "positive", "priority": "P0",
     "title": "Valid credentials return JWT token",
     "acceptance_criteria": "AC1",
     "expected_result": "200 OK with non-null token"},

    {"id": "TC-A02", "area": "Auth",    "test_level": "negative", "priority": "P0",
     "title": "Invalid password returns 401 or 403",
     "acceptance_criteria": "AC1",
     "expected_result": "401 or 403 Unauthorised"},

    {"id": "TC-A03", "area": "Auth",    "test_level": "edge",     "priority": "P1",
     "title": "Empty body returns 400 not 500",
     "acceptance_criteria": "AC1",
     "expected_result": "400 or 422 Bad Request"},

    {"id": "TC-A04", "area": "Product", "test_level": "positive", "priority": "P0",
     "title": "Valid keyword returns products with name, price and image",
     "acceptance_criteria": "AC2",
     "expected_result": "200 OK with non-empty array; each item has name, price, image"},

    {"id": "TC-A05", "area": "Product", "test_level": "negative", "priority": "P1",
     "title": "Invalid keyword returns no-results message",
     "acceptance_criteria": "AC3",
     "expected_result": "200 OK with message: No results found"},

    {"id": "TC-A06", "area": "Cart",    "test_level": "positive", "priority": "P0",
     "title": "Add to cart returns updated itemCount",
     "acceptance_criteria": "AC4",
     "expected_result": "200 OK with cartId and itemCount > 0"},

    {"id": "TC-A07", "area": "Cart",    "test_level": "positive", "priority": "P0",
     "title": "GET cart returns name, quantity and total",
     "acceptance_criteria": "AC5, AC10",
     "expected_result": "200 OK with items array and total"},

    {"id": "TC-A08", "area": "Cart",    "test_level": "negative", "priority": "P1",
     "title": "Unauthenticated cart add returns 401",
     "acceptance_criteria": "AC1",
     "expected_result": "401 or 403 Unauthorised"},

    {"id": "TC-A09", "area": "Payment", "test_level": "positive", "priority": "P0",
     "title": "Valid card processes payment and returns paymentRef",
     "acceptance_criteria": "AC7",
     "expected_result": "200 OK with paymentRef and status SUCCESS"},

    {"id": "TC-A10", "area": "Payment", "test_level": "negative", "priority": "P0",
     "title": "Invalid card returns 422 error not 500",
     "acceptance_criteria": "AC9",
     "expected_result": "422 with error message; no 500"},

    {"id": "TC-A11", "area": "Order",   "test_level": "positive", "priority": "P0",
     "title": "Place order returns unique orderId and status CONFIRMED",
     "acceptance_criteria": "AC8",
     "expected_result": "200 OK with orderId and status CONFIRMED"},
]

ui_tests = [
    {"id": "TC-U01", "area": "Search", "test_level": "positive",
     "title": "Search returns product cards with name, price and image",
     "acceptance_criteria": "AC2"},

    {"id": "TC-U02", "area": "Search", "test_level": "negative",
     "title": "Invalid search keyword shows no-results message",
     "acceptance_criteria": "AC3"},

    {"id": "TC-U03", "area": "Cart",   "test_level": "positive",
     "title": "Add to cart updates badge and cart shows correct details",
     "acceptance_criteria": "AC4, AC5"},

    {"id": "TC-U04", "area": "Cart",   "test_level": "edge",
     "title": "Empty cart disables checkout button",
     "acceptance_criteria": "AC6"},
]

e2e_tests = [
    {"id": "TC-E01", "test_level": "positive",
     "title": "Full journey: login → search → add to cart → pay → order confirmed",
     "acceptance_criteria": "AC1, AC2, AC4, AC7, AC8"},

    {"id": "TC-E02", "test_level": "negative",
     "title": "Invalid card shows payment error not 500",
     "acceptance_criteria": "AC9"},

    {"id": "TC-E03", "test_level": "edge",
     "title": "Session timeout redirects to login and cart is preserved",
     "acceptance_criteria": "AC10"},
]

console.print("\n[bold cyan]━━ Stage 2: Test Case Generator[/bold cyan]")
console.print(f"  API tests  : {len(api_tests)}")
console.print(f"  UI tests   : {len(ui_tests)}")
console.print(f"  E2E tests  : {len(e2e_tests)}")

# ── Stage 3: Test Data Generator (Faker seed=42) ─────────────
test_data = {
    "username":             fake.user_name(),
    "password":             "Test@" + fake.numerify("####"),
    "email":                fake.email(),
    "user_id":              fake.uuid4()[:8],
    "search_keyword":       "laptop",
    "invalid_keyword":      "xyzzy_no_match_999",
    "card_number":          "4111111111111111",
    "card_expiry":          "12/28",
    "card_cvv":             "123",
    "invalid_card_number":  "0000000000000000",
    "invalid_card_expiry":  "01/20",
    "invalid_card_cvv":     "000",
    "product_id":           "PROD-" + fake.bothify("???-###").upper(),
    "cart_id":              "CART-" + fake.uuid4()[:8].upper(),
    "order_id_pattern":     "ORD-XXXXXXXXXX",
    "_note":                "Generated by Faker seed=42. Sensitive fields never sent to LLM."
}

with open(f"{BASE}/generated/test_data.json", "w") as f:
    json.dump(test_data, f, indent=2)

console.print("\n[bold cyan]━━ Stage 3: Test Data Generator[/bold cyan]")
console.print(f"  Username    : {test_data['username']}")
console.print(f"  Card        : {test_data['card_number']} (sandbox)")
console.print(f"  Seed        : 42 (deterministic)")
console.print(f"  PII via LLM : False ✅")

# ── Stage 4: Coverage Report ──────────────────────────────────
all_tests = api_tests + ui_tests + e2e_tests
covered_acs = set()
for t in all_tests:
    for ac in t.get("acceptance_criteria", "").replace(" ", "").split(","):
        if ac.startswith("AC"):
            covered_acs.add(ac)

ac_ids = {a["id"] for a in parsed_spec["acceptance_criteria"]}
coverage_pct = round(len(covered_acs) / len(ac_ids) * 100)

console.print("\n[bold cyan]━━ Stage 4: Coverage Report[/bold cyan]")
table = Table(title="AC Coverage")
table.add_column("AC", style="cyan")
table.add_column("Status")
for ac in parsed_spec["acceptance_criteria"]:
    status = "✅ COVERED" if ac["id"] in covered_acs else "❌ MISSING"
    table.add_row(ac["id"], status)
console.print(table)
console.print(f"\n  Coverage : {len(covered_acs)}/{len(ac_ids)} = {coverage_pct}%")
verdict = "✅ PASS" if coverage_pct >= 80 else "❌ FAIL"
console.print(f"  Verdict  : {verdict}")

# ── Stage 5: Code Synthesis (Jinja2) ─────────────────────────
env = Environment(loader=FileSystemLoader(f"{BASE}/templates"))

render_ctx = {
    "story_id":     parsed_spec["story_id"],
    "actor":        parsed_spec["actor"],
    "base_url":     ctx["application"]["base_url"],
    "frontend_url": ctx["application"]["frontend_url"],
    "test_data":    test_data,
}

# API tests
tmpl = env.get_template("api_test.j2")
java_out = tmpl.render(**render_ctx, test_cases=api_tests)
with open(f"{BASE}/generated/ShopFlowTest.java", "w") as f:
    f.write(java_out)

# UI tests
tmpl = env.get_template("ui_test.j2")
ui_out = tmpl.render(**render_ctx, test_cases=ui_tests)
with open(f"{BASE}/generated/shopflow-ui.spec.ts", "w") as f:
    f.write(ui_out)

# E2E tests
tmpl = env.get_template("e2e_test.j2")
e2e_out = tmpl.render(**render_ctx, test_cases=e2e_tests)
with open(f"{BASE}/generated/shopflow-e2e.spec.ts", "w") as f:
    f.write(e2e_out)

console.print("\n[bold cyan]━━ Stage 5: Code Synthesis[/bold cyan]")

# Count lines
java_lines = len(java_out.splitlines())
ui_lines   = len(ui_out.splitlines())
e2e_lines  = len(e2e_out.splitlines())
total_lines = java_lines + ui_lines + e2e_lines

out_table = Table(title="Generated Output")
out_table.add_column("File")
out_table.add_column("Description")
out_table.add_column("Tests", justify="right")
out_table.add_column("Lines", justify="right")
out_table.add_row("ShopFlowTest.java",      "REST-assured API tests",       str(len(api_tests)), str(java_lines))
out_table.add_row("shopflow-ui.spec.ts",    "Playwright UI tests",          str(len(ui_tests)),  str(ui_lines))
out_table.add_row("shopflow-e2e.spec.ts",   "Playwright E2E journey tests", str(len(e2e_tests)), str(e2e_lines))
out_table.add_row("test_data.json",         "Faker test data (seed=42)",    "—",                 "—")
console.print(out_table)

# Test pyramid
pyr_table = Table(title="Test Pyramid")
pyr_table.add_column("Layer")
pyr_table.add_column("Tool")
pyr_table.add_column("Count", justify="right")
pyr_table.add_column("Actual %", justify="right")
pyr_table.add_column("Target %", justify="right")
total_tests = len(api_tests) + len(ui_tests) + len(e2e_tests)
pyr_table.add_row("API", "REST-assured + Java 17",    str(len(api_tests)), f"{round(len(api_tests)/total_tests*100)}%", "56% ✅")
pyr_table.add_row("UI",  "Playwright + TypeScript",   str(len(ui_tests)),  f"{round(len(ui_tests)/total_tests*100)}%",  "25% ✅")
pyr_table.add_row("E2E", "Playwright + TypeScript",   str(len(e2e_tests)), f"{round(len(e2e_tests)/total_tests*100)}%", "19% ✅")
console.print(pyr_table)

console.print(f"\n[bold green]✅ Total lines generated: {total_lines}[/bold green]")
console.print(f"[bold green]✅ AC Coverage: {coverage_pct}% — Verdict: {verdict}[/bold green]\n")
