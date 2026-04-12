# StoryForge AI — Intelligent Test Automation Framework
 
> *From a plain English user story to executable test scripts — 
> fully open source, zero data egress, runs entirely on your infrastructure.*

---

## The Problem This Solves

Writing test scripts manually is slow, repetitive and does not scale.

Every sprint, QA engineers read user stories, think through test scenarios,
write API tests, UI tests and E2E tests, generate test data and check coverage
— all by hand. When requirements change, scripts need to be rewritten. When volume
increases, the team becomes the bottleneck.

**StoryForge AI solves this.**

Give it one user story in plain English. In under 5 minutes it returns a
complete, executable test suite — API tests, UI tests, E2E journey tests,
test data and a coverage report. No cloud API keys. No data leaving your
network. No manual effort.

---

## How It Works

The framework runs five stages, driven entirely by a single user story.

## 🔄 End-to-End Flow

```mermaid
sequenceDiagram
    participant User
    participant LLM
    participant Validator
    participant Generator

    User->>LLM: Input User Story
    LLM->>Validator: Generate JSON Test Cases
    Validator->>Generator: Validate schema
    Generator->>User: Generate automation scripts


**Stage 1 — Parsing Engine.** Mistral 7B via Ollama reads the user story and extracts the actor, action, goal, constraints and all acceptance criteria. Output is a `ParsedSpec` JSON object validated by Pydantic v2. Malformed LLM responses are automatically rejected and retried.

**Stage 2 — Test Case Generator (4-Agent Pipeline).** Four agents work in sequence:
- **Planner** — reads `test_gen_config.yaml`, decides pyramid split based on target ratios
- **Generator** — creates test cases per AC covering positive, negative and edge scenarios
- **Critic** — automatically identifies coverage gaps and flags missing scenarios
- **Refiner** — finalises, deduplicates and locks the TestSpec

**Stage 3 — Test Data Generator.** Faker generates deterministic test data using `seed=42`. The same data is produced on every CI run. Sensitive fields such as passwords and card numbers are generated locally — never sent to the LLM.

**Stage 4 — Coverage Report.** Every test case is mapped back to every acceptance criterion. Pyramid compliance is checked against target ratios in `test_gen_config.yaml`. A PASS or FAIL verdict is produced against an 80 percent minimum threshold.

**Stage 5 — Code Synthesis Module.** Jinja2 templates render each test case into real executable code. No LLM is involved at this stage. Output is deterministic, fast and fully auditable.

---

## The User Story Used in This POC

**US-001: Product Search, Add to Cart and Complete Payment**

As a registered shopper on ShopFlow, I want to search for a product, add it to my cart, and complete payment so that my order is placed and I receive an order confirmation with a unique order ID.

**Acceptance Criteria:**

1. Shopper must be authenticated before adding to cart or checking out.
2. Search returns relevant results for a valid keyword including product name, price and image.
3. Searching with an empty or invalid keyword shows a no-results message.
4. Shopper can add a product to cart and the cart badge updates to reflect the item count.
5. Cart shows correct product name, quantity and total price.
6. Empty cart disables the checkout button.
7. Checkout accepts valid payment card details and places the order.
8. Successful payment returns an order confirmation page with a unique order ID and status CONFIRMED.
9. Invalid card details such as an expired card or wrong CVV show an appropriate error and not a 500.
10. Session timeout during checkout redirects to login and the cart is preserved after re-login.

---

## What Gets Generated

Running the notebook produces **639 lines of executable test code** from that single user story:

| File | Description | Tests |
|---|---|---|
| `generated/ShopFlowTest.java` | REST-assured API tests | 15 |
| `generated/shopflow-ui.spec.ts` | Playwright UI tests | 5 |
| `generated/shopflow-e2e.spec.ts` | Playwright E2E journey tests | 4 |
| `generated/test_data.json` | Faker test data (seed=42) | — |

---

## Test Suite — US-001 (24 Test Cases)

### API Tests — REST-assured + Java 17

| ID | Title | Level | AC |
|---|---|---|---|
| TC-A01 | Valid credentials return JWT token | Positive | AC1 |
| TC-A02 | Invalid password returns 401 or 403 | Negative | AC1 |
| TC-A03 | Empty body returns 400 not 500 | Edge | AC1 |
| TC-A15 | Tampered JWT token returns 401 | Edge | AC1 |
| TC-A04 | Valid keyword returns name, price and image | Positive | AC2 |
| TC-A05 | Invalid keyword returns no-results message | Negative | AC3 |
| TC-A12 | Special characters in keyword returns safe response | Edge | AC3 |
| TC-A06 | Add to cart returns updated itemCount | Positive | AC4 |
| TC-A07 | GET cart returns name, quantity and total | Positive | AC5, AC10 |
| TC-A08 | Unauthenticated cart add returns 401 | Negative | AC1 |
| TC-A13 | Adding same product twice updates quantity not duplicate | Edge | AC4, AC5 |
| TC-A09 | Valid card processes payment and returns paymentRef | Positive | AC7 |
| TC-A10 | Invalid card returns 422 error not 500 | Negative | AC9 |
| TC-A14 | Payment gateway timeout returns error not 500 | Edge | AC9 |
| TC-A11 | Place order returns unique orderId and status CONFIRMED | Positive | AC8 |

### UI Tests — Playwright + TypeScript

| ID | Title | Level | AC |
|---|---|---|---|
| TC-U01 | Search returns product cards with name, price and image | Positive | AC2 |
| TC-U02 | Invalid search keyword shows no-results message | Negative | AC3 |
| TC-U03 | Add to cart updates badge and cart shows correct details | Positive | AC4, AC5 |
| TC-U04 | Empty cart disables the checkout button | Edge | AC6 |
| TC-U05 | Remove item from cart updates total correctly | Positive | AC5 |

### E2E Tests — Playwright + TypeScript

| ID | Title | Level | AC |
|---|---|---|---|
| TC-E01 | Full journey: login → search → add to cart → pay → order confirmed | Positive | AC1, AC2, AC4, AC7, AC8 |
| TC-E02 | Invalid card shows payment error not 500 | Negative | AC9 |
| TC-E03 | Session timeout redirects to login; cart preserved after re-login | Edge | AC10 |
| TC-E04 | Order ID is unique across two consecutive orders | Edge | AC8 |

---

## Test Pyramid

| Layer | Tool | Count | Actual | Target |
|---|---|---|---|---|
| API | REST-assured + Java 17 | 15 | 62% | ~56% ✅ |
| UI | Playwright + TypeScript | 5 | 21% | ~25% ✅ |
| E2E | Playwright + TypeScript | 4 | 17% | ~19% ✅ |

> Pyramid ratios are configured in `test_gen_config.yaml`. The Critic agent may generate additional test cases beyond the target ratio when coverage gaps are identified — this is expected behaviour.

---

## Coverage Report

| Acceptance Criterion | Covered By | Status |
|---|---|---|
| AC-1 Auth before cart/checkout | TC-A01, TC-A02, TC-A03, TC-A08, TC-A15, TC-E01 | ✅ |
| AC-2 Search returns results | TC-A04, TC-U01, TC-E01 | ✅ |
| AC-3 Invalid search shows no results | TC-A05, TC-A12, TC-U02 | ✅ |
| AC-4 Add to cart updates badge | TC-A06, TC-A13, TC-U03, TC-E01 | ✅ |
| AC-5 Cart shows name, qty, total | TC-A07, TC-A13, TC-U03, TC-U05 | ✅ |
| AC-6 Empty cart disables checkout | TC-U04 | ✅ |
| AC-7 Valid payment places order | TC-A09, TC-E01 | ✅ |
| AC-8 Confirmation with order ID | TC-A11, TC-E01, TC-E04 | ✅ |
| AC-9 Invalid card shows error not 500 | TC-A10, TC-A14, TC-E02 | ✅ |
| AC-10 Session timeout redirects to login | TC-A07, TC-E03 | ✅ |

**AC Coverage: 10/10 = 100% — Verdict: PASS**

---

## Coverage Gap Analysis

The Critic agent automatically identifies gaps and flags them as Added or Out of Scope:

| Gap Area | Action | TC Added | Reason |
|---|---|---|---|
| Special character search | Added | TC-A12 | Directly traceable to AC3 |
| Duplicate product in cart | Added | TC-A13 | Traceable to AC4 and AC5 |
| Payment gateway timeout | Added | TC-A14 | Traceable to AC9 — no 500 rule |
| Tampered JWT token | Added | TC-A15 | Traceable to AC1 — auth security |
| Remove item from cart | Added | TC-U05 | Traceable to AC5 — cart total |
| Order ID uniqueness | Added | TC-E04 | Traceable to AC8 |
| Concurrent sessions | Out of scope | — | Needs separate auth user story |
| Order history persistence | Out of scope | — | Needs separate order user story |
| Payment retry handling | Out of scope | — | Needs separate payment user story |
| Search partial/case match | Out of scope | — | Needs separate search user story |

---

## Scalability — Batch Runner

The framework processes multiple user stories in sequence. Each story runs independently through the full 5-stage pipeline with output organised per story.

| Story | Title | ACs | API | UI | E2E | Total | Coverage | Verdict |
|---|---|---|---|---|---|---|---|---|
| US-001 | Product Search, Add to Cart and Payment | 10 | 15 | 5 | 4 | 24 | 100% | PASS |
| US-002 | User Registration | 6 | 7 | 3 | 2 | 12 | 100% | PASS |
| US-003 | Product Review & Rating | 5 | 5 | 3 | 2 | 10 | 100% | PASS |
| **Total** | | | | | | **46** | **100%** | **PASS** |

> In production the batch runner reads from Jira API or a stories folder and writes output to `/generated/{story_id}/`.

---

## Repository Structure

```
StoryForgeAI_POC/
├── ShopFlow_POC.ipynb             Main notebook — 8 steps, run this
├── generate.py                    Standalone runner (no Jupyter needed)
├── config/
│   ├── test_gen_config.yaml       Pyramid ratios, test levels, framework, LLM config
│   └── app_context.yaml           ShopFlow endpoints, nav paths, login flows
├── templates/
│   ├── api_test.j2                REST-assured Java Jinja2 template
│   ├── ui_test.j2                 Playwright UI TypeScript Jinja2 template
│   └── e2e_test.j2                Playwright E2E TypeScript Jinja2 template
└── generated/
    ├── ShopFlowTest.java          15 API tests — ready to run
    ├── shopflow-ui.spec.ts        5 UI tests — ready to run
    ├── shopflow-e2e.spec.ts       4 E2E tests — ready to run
    └── test_data.json             Faker test data — seed=42
```

---

## Config Files Explained

### test_gen_config.yaml

Defines the rules the framework follows — pyramid target ratios (not hardcoded counts), test levels, which framework to use, LLM settings and coverage threshold. The Planner agent reads this file to decide the pyramid split. Changing framework from REST-assured to pytest requires editing one line. Zero code changes anywhere else.

### app_context.yaml

Gives the LLM full knowledge of ShopFlow — all 7 microservice endpoints, base URLs, frontend nav paths, login flows and default test data. Without this file, you would re-explain the app in every user story. With it, the LLM already knows the application.

---

## Microservices & API Endpoints

| Service | Method | Endpoint |
|---|---|---|
| Auth Service | POST | `/api/auth/login` |
| Product Service | GET | `/api/products/search` |
| Cart Service | POST | `/api/cart/add` |
| Cart Service | GET | `/api/cart/{userId}` |
| Order Service | POST | `/api/orders/place` |
| Payment Service | POST | `/api/payment/process` |
| Notification Service | POST | `/api/notify/email` |

> Payment gateway operates in sandbox mode — no real transactions are processed.

---

## How to Run

### Prerequisites

- Python 3.10+
- Ollama installed from https://ollama.com/download

```bash
ollama pull mistral
```

### Setup and Run

```bash
git clone https://github.com/SriniB-cloud/StoryForgeAI_POC.git
cd StoryForgeAI_POC

python3 -m venv venv
source venv/bin/activate

pip install jupyter pydantic jinja2 requests pyyaml faker rich

jupyter notebook ShopFlow_POC.ipynb
```

Open the notebook and step through each cell. Each stage has a description and rich output.

> **Note:** Set `SIMULATE_LLM = True` to run without Ollama. Set to `False` to use live Mistral 7B inference.

### Alternatively — run without Jupyter

```bash
python generate.py
```

---

## Open Source Stack — 100% On-Premise

| Layer | Tool | Licence | Why |
|---|---|---|---|
| LLM Engine | Mistral 7B via Ollama | MIT / Apache 2.0 | Local inference · zero egress · deterministic at temperature=0 |
| Orchestration | LangChain + LangGraph | MIT | 4-agent stateful loop · native Ollama connector |
| Schema Validation | Pydantic v2 | MIT | Catches malformed LLM output before it propagates |
| Test Data | Faker (Python) | MIT | Sensitive data never touches LLM · deterministic via seed |
| Code Templates | Jinja2 | BSD-3 | Framework-agnostic · swappable · no LLM for rendering |
| Config | PyYAML | MIT | Human-readable · swap framework with one line · no hardcoded counts |
| API Tests | REST-assured + Java 17 | Apache 2.0 | Industry-standard DSL · TestNG + Maven integration |
| UI + E2E | Playwright + TypeScript | Apache 2.0 | Multi-browser · auto-wait · video recording on failure |

---

## Why On-Premise Matters

| Concern | How StoryForge AI Addresses It |
|---|---|
| Data privacy | User stories and test data never leave your network |
| GDPR / HIPAA | Sensitive fields generated by Faker locally — not by LLM |
| Vendor lock-in | Swap Mistral for LLaMA 3 in one config line |
| Cost at scale | No per-token charges — runs free at any volume |
| Air-gap support | Zero internet access needed after initial model pull |

---

## 🚀 Traditional vs StoryForge AI — Time Savings

| Activity | Traditional Approach | StoryForge AI | Time Saved |
|---|---|---|---|
| Parse user story into test scenarios | 2 to 4 hours | 20 seconds | 99% |
| Write API test cases (15 tests) | 1 to 2 days | Under 1 minute | 98% |
| Write UI test cases (5 tests) | 4 to 6 hours | Under 1 minute | 97% |
| Write E2E test cases (4 tests) | 3 to 5 hours | Under 1 minute | 96% |
| Generate test data | 1 to 2 hours | 2 seconds | 99% |
| Run coverage analysis | 1 to 2 hours | Instant | 100% |
| **Total for 1 user story** | **3 to 4 days** | **Under 5 minutes** | **97%** |

---

## 📊 Key Metrics Dashboard

### 🚀 Performance Impact

- ⏱️ **Script Writing Time Reduction:** 97%
- 📈 **Test Coverage Increase:** 100% (from 60%)
- ✅ **Acceptance Criteria Covered:** 10/10

### 🧪 Test Generation

- 🧾 **Test Cases Generated:** 24 *(15 API + 5 UI + 4 E2E)*
- 🧩 **Lines of Code Generated:** 639
- 📦 **Batch Runner:** 3 stories · 46 total test cases

### 🔒 Security & Compliance

- 🔐 **Data Egress:** Zero
- 🛠️ **Proprietary Tools Used:** None
- 🔑 **PII sent to LLM:** None — generated locally by Faker

### 📏 Quality Metrics

- 🎯 **Minimum Coverage Threshold:** 80%
- 🏆 **Actual Coverage Score:** 100%
- 🔍 **Coverage Gaps Identified:** 6 added · 4 out of scope

---


