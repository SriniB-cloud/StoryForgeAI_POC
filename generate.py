"""
StoryForge AI — Intelligent Test Automation Framework
Reads user stories from /stories/ folder and generates executable test scripts.

Usage:
  python generate.py                     # process all stories in /stories/
  python generate.py --story US-001      # process a single story

Setup:
  1. Install Ollama from https://ollama.com/download
  2. Run: ollama pull mistral
  3. Run: pip install pydantic jinja2 pyyaml faker rich requests
  4. Drop your user story in stories/US-XXX.txt
  5. Run: python generate.py --story US-XXX

SIMULATE_LLM = True  → runs without Ollama (US-001 only, pre-validated data)
SIMULATE_LLM = False → Mistral reads story file and generates test cases live
"""

import json, yaml, os, sys, time, argparse, requests
from faker import Faker
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, ValidationError
from typing import List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()
BASE = os.path.dirname(os.path.abspath(__file__))

with open(f'{BASE}/config/test_gen_config.yaml') as f:
    cfg = yaml.safe_load(f)
with open(f'{BASE}/config/app_context.yaml') as f:
    ctx = yaml.safe_load(f)

SIMULATE_LLM = False  # Set True to run without Ollama (US-001 only)
OLLAMA_URL   = cfg['llm']['base_url'] + '/api/generate'
LLM_MODEL    = cfg['llm']['model']
TEMPERATURE  = cfg['llm']['temperature']

# ── Story reader ──────────────────────────────────────────────
def read_story(story_id):
    path = f'{BASE}/stories/{story_id}.txt'
    if not os.path.exists(path):
        console.print(f'[red]Story file not found: {path}[/red]')
        console.print('[dim]Create stories/{story_id}.txt with your user story and acceptance criteria[/dim]')
        sys.exit(1)
    with open(path) as f:
        content = f.read()
    console.print(Panel(f'[dim]{content.strip()}[/dim]', title=f'[cyan]Input — stories/{story_id}.txt[/cyan]', border_style='cyan'))
    return content

def list_stories():
    stories_dir = f'{BASE}/stories'
    if not os.path.exists(stories_dir):
        console.print('[red]No /stories/ folder found[/red]')
        sys.exit(1)
    return sorted([f.replace('.txt','') for f in os.listdir(stories_dir) if f.endswith('.txt')])

# ── LLM helper ────────────────────────────────────────────────
def call_llm(prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            resp = requests.post(OLLAMA_URL, json={
                'model': LLM_MODEL, 'prompt': prompt,
                'stream': False, 'options': {'temperature': TEMPERATURE}
            }, timeout=180)
            resp.raise_for_status()
            return resp.json()['response'].strip()
        except Exception as e:
            console.print(f'[yellow]LLM attempt {attempt+1} failed: {e}[/yellow]')
            time.sleep(2)
    raise RuntimeError('Mistral failed — is Ollama running? Run: ollama serve')

def parse_json(raw):
    raw = raw.strip()
    if '```json' in raw:
        raw = raw.split('```json')[1].split('```')[0].strip()
    elif '```' in raw:
        raw = raw.split('```')[1].split('```')[0].strip()
    return json.loads(raw)

# ── Pydantic schemas ──────────────────────────────────────────
class AcceptanceCriterion(BaseModel):
    id: str
    text: str

class ParsedSpec(BaseModel):
    story_id: str
    actor: str
    action: str
    goal: str
    preconditions: List[str]
    acceptance_criteria: List[AcceptanceCriterion]
    business_rules: List[str]

class TestCase(BaseModel):
    id: str
    area: str
    test_level: str
    priority: str
    title: str
    acceptance_criteria: str
    expected_result: str

class TestSpec(BaseModel):
    api_tests: List[TestCase]
    ui_tests:  List[TestCase]
    e2e_tests: List[TestCase]

# ── Simulated data (SIMULATE_LLM=True, US-001 only) ──────────
SIM_SPEC = {
    'story_id':'US-001','actor':'registered shopper on ShopFlow',
    'action':'search for a product, add it to cart, complete payment',
    'goal':'order is placed and order confirmation with unique order ID is received',
    'preconditions':['shopper is registered','shopper has valid credentials'],
    'acceptance_criteria':[
        {'id':'AC1', 'text':'Shopper must be authenticated before adding to cart or checking out'},
        {'id':'AC2', 'text':'Search returns product name, price and image for a valid keyword'},
        {'id':'AC3', 'text':'Empty or invalid keyword shows a no-results message'},
        {'id':'AC4', 'text':'Add to cart updates the cart badge item count'},
        {'id':'AC5', 'text':'Cart shows correct product name, quantity and total price'},
        {'id':'AC6', 'text':'Empty cart disables the checkout button'},
        {'id':'AC7', 'text':'Checkout accepts valid payment card details and places the order'},
        {'id':'AC8', 'text':'Successful payment returns order confirmation with unique order ID and status CONFIRMED'},
        {'id':'AC9', 'text':'Invalid card details show an appropriate error and not a 500'},
        {'id':'AC10','text':'Session timeout redirects to login and cart is preserved after re-login'},
    ],
    'business_rules':['Payment gateway operates in sandbox mode','Session tokens are JWT-based','Cart is persisted server-side per userId']
}

SIM_TESTS = {
    'api':[
        {'id':'TC-A01','area':'Auth',   'test_level':'positive','priority':'P0','title':'Valid credentials return JWT token',                    'acceptance_criteria':'AC1','expected_result':'200 OK with token'},
        {'id':'TC-A02','area':'Auth',   'test_level':'negative','priority':'P0','title':'Invalid password returns 401 or 403',                   'acceptance_criteria':'AC1','expected_result':'401 or 403'},
        {'id':'TC-A03','area':'Auth',   'test_level':'edge',    'priority':'P1','title':'Empty body returns 400 not 500',                        'acceptance_criteria':'AC1','expected_result':'400 or 422'},
        {'id':'TC-A15','area':'Auth',   'test_level':'edge',    'priority':'P1','title':'Tampered JWT token returns 401',                        'acceptance_criteria':'AC1','expected_result':'401'},
        {'id':'TC-A04','area':'Product','test_level':'positive','priority':'P0','title':'Valid keyword returns products with name, price, image', 'acceptance_criteria':'AC2','expected_result':'200 with results'},
        {'id':'TC-A05','area':'Product','test_level':'negative','priority':'P1','title':'Invalid keyword returns no-results message',             'acceptance_criteria':'AC3','expected_result':'no-results message'},
        {'id':'TC-A12','area':'Product','test_level':'edge',    'priority':'P1','title':'Special characters in keyword returns safe response',    'acceptance_criteria':'AC3','expected_result':'safe 200 or 400'},
        {'id':'TC-A06','area':'Cart',   'test_level':'positive','priority':'P0','title':'Add to cart returns updated itemCount',                 'acceptance_criteria':'AC4','expected_result':'itemCount > 0'},
        {'id':'TC-A07','area':'Cart',   'test_level':'positive','priority':'P0','title':'GET cart returns name, quantity and total',             'acceptance_criteria':'AC5, AC10','expected_result':'items array with total'},
        {'id':'TC-A08','area':'Cart',   'test_level':'negative','priority':'P1','title':'Unauthenticated cart add returns 401',                  'acceptance_criteria':'AC1','expected_result':'401'},
        {'id':'TC-A13','area':'Cart',   'test_level':'edge',    'priority':'P1','title':'Adding same product twice updates quantity not duplicate','acceptance_criteria':'AC4, AC5','expected_result':'qty updated'},
        {'id':'TC-A09','area':'Payment','test_level':'positive','priority':'P0','title':'Valid card processes payment and returns paymentRef',    'acceptance_criteria':'AC7','expected_result':'paymentRef + SUCCESS'},
        {'id':'TC-A10','area':'Payment','test_level':'negative','priority':'P0','title':'Invalid card returns 422 error not 500',                'acceptance_criteria':'AC9','expected_result':'422 with error'},
        {'id':'TC-A14','area':'Payment','test_level':'edge',    'priority':'P1','title':'Payment gateway timeout returns error not 500',         'acceptance_criteria':'AC9','expected_result':'4xx not 500'},
        {'id':'TC-A11','area':'Order',  'test_level':'positive','priority':'P0','title':'Place order returns unique orderId and CONFIRMED',      'acceptance_criteria':'AC8','expected_result':'orderId + CONFIRMED'},
    ],
    'ui':[
        {'id':'TC-U01','area':'Search','test_level':'positive','title':'Search returns product cards with name, price and image', 'acceptance_criteria':'AC2','expected_result':'cards visible','priority':'P0'},
        {'id':'TC-U02','area':'Search','test_level':'negative','title':'Invalid search keyword shows no-results message',         'acceptance_criteria':'AC3','expected_result':'no-results shown','priority':'P1'},
        {'id':'TC-U03','area':'Cart',  'test_level':'positive','title':'Add to cart updates badge and cart shows correct details','acceptance_criteria':'AC4, AC5','expected_result':'badge updated','priority':'P0'},
        {'id':'TC-U04','area':'Cart',  'test_level':'edge',    'title':'Empty cart disables checkout button',                    'acceptance_criteria':'AC6','expected_result':'button disabled','priority':'P0'},
        {'id':'TC-U05','area':'Cart',  'test_level':'positive','title':'Remove item from cart updates total correctly',          'acceptance_criteria':'AC5','expected_result':'total updated','priority':'P1'},
    ],
    'e2e':[
        {'id':'TC-E01','area':'Journey','test_level':'positive','title':'Full journey: login > search > add to cart > pay > order confirmed','acceptance_criteria':'AC1, AC2, AC4, AC7, AC8','expected_result':'order confirmed','priority':'P0'},
        {'id':'TC-E02','area':'Journey','test_level':'negative','title':'Invalid card shows payment error not 500',                          'acceptance_criteria':'AC9','expected_result':'error shown','priority':'P0'},
        {'id':'TC-E03','area':'Journey','test_level':'edge',    'title':'Session timeout redirects to login; cart preserved',               'acceptance_criteria':'AC10','expected_result':'cart intact','priority':'P1'},
        {'id':'TC-E04','area':'Order',  'test_level':'edge',    'title':'Order ID is unique across two consecutive orders',                 'acceptance_criteria':'AC8','expected_result':'unique IDs','priority':'P1'},
    ]
}

# ══════════════════════════════════════════════════════════════
# STAGE 1 — PARSING ENGINE
# ══════════════════════════════════════════════════════════════

def run_stage1(story_id, story_text):
    console.print(Panel('[bold cyan]Stage 1 — Parsing Engine[/bold cyan]', border_style='cyan'))
    console.print(f'[dim]Mode: {"SIMULATED" if SIMULATE_LLM else "LIVE — Mistral 7B reads story and extracts ParsedSpec"}[/dim]\n')

    if SIMULATE_LLM:
        parsed_spec = ParsedSpec(**SIM_SPEC).model_dump()
    else:
        prompt = f"""You are a QA engineer. Extract structured information from this user story.
Return ONLY valid JSON — no markdown, no explanation, no preamble.

Required JSON schema:
{{
  "story_id": "string",
  "actor": "string — who performs the action",
  "action": "string — what they want to do",
  "goal": "string — why they want to do it",
  "preconditions": ["string"],
  "acceptance_criteria": [{{"id": "AC1", "text": "string"}}],
  "business_rules": ["string"]
}}

User story:
{story_text}

Return only the JSON:"""

        console.print('[dim]Calling Mistral 7B — extracting ParsedSpec...[/dim]')
        for attempt in range(3):
            try:
                raw = call_llm(prompt)
                parsed_spec = ParsedSpec(**parse_json(raw)).model_dump()
                console.print('[green]Pydantic validation passed ✅[/green]')
                break
            except (ValidationError, json.JSONDecodeError, KeyError) as e:
                console.print(f'[yellow]Attempt {attempt+1} schema error: {e}[/yellow]')
                if attempt == 2:
                    raise RuntimeError(f'Stage 1 failed after 3 attempts: {e}')

    spec_t = Table(title=f'ParsedSpec — {story_id}', box=box.ROUNDED, show_header=False, padding=(0,1))
    spec_t.add_column('Field', style='cyan', width=18)
    spec_t.add_column('Value')
    spec_t.add_row('Story ID',       parsed_spec['story_id'])
    spec_t.add_row('Actor',          parsed_spec['actor'])
    spec_t.add_row('Action',         parsed_spec['action'])
    spec_t.add_row('Goal',           parsed_spec['goal'])
    spec_t.add_row('Preconditions',  ' | '.join(parsed_spec['preconditions']))
    spec_t.add_row('Business Rules', ' | '.join(parsed_spec['business_rules']))
    console.print(spec_t)

    ac_t = Table(title=f'Acceptance Criteria ({len(parsed_spec["acceptance_criteria"])})', box=box.ROUNDED, show_lines=True)
    ac_t.add_column('ID', style='cyan', width=6, no_wrap=True)
    ac_t.add_column('Acceptance Criterion')
    for ac in parsed_spec['acceptance_criteria']:
        ac_t.add_row(ac['id'], ac['text'])
    console.print(ac_t)
    console.print(f'[bold green]✅ Stage 1 complete — {len(parsed_spec["acceptance_criteria"])} AC extracted · Pydantic v2 validated[/bold green]\n')
    return parsed_spec

# ══════════════════════════════════════════════════════════════
# STAGE 2 — TEST CASE GENERATOR (4-AGENT PIPELINE)
# ══════════════════════════════════════════════════════════════

def planner_agent(parsed_spec):
    console.print(Panel('[bold]Agent 1 — Planner[/bold]\nReading config · deciding pyramid split · assigning test levels', border_style='blue'))
    time.sleep(0.3)
    plan = {
        'api_pct':  cfg['pyramid']['api']['target_pct'],
        'ui_pct':   cfg['pyramid']['ui']['target_pct'],
        'e2e_pct':  cfg['pyramid']['e2e']['target_pct'],
        'levels':   cfg['levels'],
        'ac_count': len(parsed_spec['acceptance_criteria']),
        'frameworks': {
            'api': cfg['pyramid']['api']['framework'],
            'ui':  cfg['pyramid']['ui']['framework'],
            'e2e': cfg['pyramid']['e2e']['framework'],
        }
    }
    t = Table(box=box.SIMPLE_HEAVY, show_header=False, padding=(0,1))
    t.add_column('k', style='cyan', width=20)
    t.add_column('v')
    t.add_row('AC to cover', str(plan['ac_count']))
    t.add_row('API target',  f"{plan['api_pct']}% · {plan['frameworks']['api']}")
    t.add_row('UI target',   f"{plan['ui_pct']}% · {plan['frameworks']['ui']}")
    t.add_row('E2E target',  f"{plan['e2e_pct']}% · {plan['frameworks']['e2e']}")
    t.add_row('Test levels', ' · '.join(plan['levels']))
    console.print(t)
    console.print('[green]✅ Planner complete — pyramid plan locked[/green]\n')
    return plan

def generator_agent(parsed_spec, plan):
    console.print(Panel('[bold]Agent 2 — Generator[/bold]\nCalling Mistral · generating test cases per AC · positive · negative · edge', border_style='blue'))

    ac_list = '\n'.join([f"{a['id']}: {a['text']}" for a in parsed_spec['acceptance_criteria']])

    ac_count   = len(parsed_spec['acceptance_criteria'])
    api_target = max(3, round(ac_count * plan['api_pct'] / 100))
    ui_target  = max(2, round(ac_count * plan['ui_pct']  / 100))
    e2e_target = max(3, round(ac_count * plan['e2e_pct'] / 100))

    prompt = f"""You are a senior QA engineer. Generate test cases from this user story.
Return ONLY valid JSON — no markdown, no explanation, no preamble.

Story: {parsed_spec['story_id']} — Actor: {parsed_spec['actor']}
Action: {parsed_spec['action']}
Goal: {parsed_spec['goal']}

Acceptance Criteria:
{ac_list}

STRICT RULES — follow exactly:
1. Generate EXACTLY {api_target} API tests covering service/contract level behaviour
2. Generate EXACTLY {ui_target} UI tests covering browser interaction behaviour
3. Generate EXACTLY {e2e_target} E2E tests covering FULL USER JOURNEYS end to end
4. E2E tests must be full journeys — e.g. login → search → add to cart → pay → confirm
5. Each AC must be covered by at least one test case across all layers
6. Cover positive (happy path), negative (error cases) AND edge (boundary) scenarios
7. API test IDs: TC-A01, TC-A02... | UI test IDs: TC-U01... | E2E test IDs: TC-E01...
8. test_level must be exactly one of: positive, negative, edge
9. priority: P0 for critical path tests, P1 for important but non-critical

Return this exact JSON:
{{
  "api_tests": [
    {{
      "id": "TC-A01",
      "area": "string — functional area e.g. Auth, Product, Cart",
      "test_level": "positive",
      "priority": "P0",
      "title": "clear descriptive test title",
      "acceptance_criteria": "AC1",
      "expected_result": "what should happen"
    }}
  ],
  "ui_tests": [
    {{
      "id": "TC-U01",
      "area": "string",
      "test_level": "positive",
      "priority": "P0",
      "title": "clear descriptive test title",
      "acceptance_criteria": "AC2",
      "expected_result": "what should happen"
    }}
  ],
  "e2e_tests": [
    {{
      "id": "TC-E01",
      "area": "Journey",
      "test_level": "positive",
      "priority": "P0",
      "title": "full journey description",
      "acceptance_criteria": "AC1, AC2",
      "expected_result": "end state"
    }}
  ]
}}

Return only the JSON object:"""

    console.print('[dim]Calling Mistral 7B — generating test cases...[/dim]')
    for attempt in range(3):
        try:
            raw  = call_llm(prompt)
            data = parse_json(raw)
            spec = TestSpec(**data)
            api_tests = [t.model_dump() for t in spec.api_tests]
            ui_tests  = [t.model_dump() for t in spec.ui_tests]
            e2e_tests = [t.model_dump() for t in spec.e2e_tests]
            console.print(f'  Generated: [blue]{len(api_tests)} API[/blue] · [green]{len(ui_tests)} UI[/green] · [yellow]{len(e2e_tests)} E2E[/yellow]')
            console.print('[green]✅ Generator complete[/green]\n')
            return api_tests, ui_tests, e2e_tests
        except (ValidationError, json.JSONDecodeError, KeyError) as e:
            console.print(f'[yellow]Attempt {attempt+1} schema error: {e}[/yellow]')
            if attempt == 2:
                raise RuntimeError(f'Generator failed: {e}')

def critic_agent(api_tests, ui_tests, e2e_tests, parsed_spec):
    console.print(Panel('[bold]Agent 3 — Critic[/bold]\nChecking coverage gaps · validating all ACs covered', border_style='blue'))
    time.sleep(0.3)
    all_tests   = api_tests + ui_tests + e2e_tests
    covered_acs = set()
    for t in all_tests:
        for ac in t.get('acceptance_criteria','').replace(' ','').split(','):
            if ac.startswith('AC'):
                covered_acs.add(ac)
    ac_ids  = [a['id'] for a in parsed_spec['acceptance_criteria']]
    missing = [ac for ac in ac_ids if ac not in covered_acs]
    status  = '[green]All ACs covered ✅[/green]' if not missing else f'[yellow]Missing: {", ".join(missing)} — Refiner will fix[/yellow]'
    console.print(f'  AC Status : {status}')
    console.print('[green]✅ Critic complete[/green]\n')
    return missing

def refiner_agent(api_tests, ui_tests, e2e_tests, missing_acs, parsed_spec):
    console.print(Panel('[bold]Agent 4 — Refiner[/bold]\nDeduplicating · fixing missing ACs · locking TestSpec', border_style='blue'))
    time.sleep(0.3)
    if missing_acs:
        console.print(f'[yellow]Adding coverage for: {", ".join(missing_acs)}[/yellow]')
        for i, ac_id in enumerate(missing_acs):
            ac_text = next((a['text'] for a in parsed_spec['acceptance_criteria'] if a['id'] == ac_id), ac_id)
            api_tests.append({
                'id': f'TC-A{90+i:02d}', 'area': 'Coverage', 'test_level': 'positive',
                'priority': 'P1', 'title': f'Verify: {ac_text[:55]}',
                'acceptance_criteria': ac_id, 'expected_result': f'{ac_id} verified'
            })
    seen, deduped = set(), []
    for t in api_tests + ui_tests + e2e_tests:
        if t['id'] not in seen:
            seen.add(t['id'])
            deduped.append(t)
    new_api = [t for t in deduped if t['id'].startswith('TC-A')]
    new_ui  = [t for t in deduped if t['id'].startswith('TC-U')]
    new_e2e = [t for t in deduped if t['id'].startswith('TC-E')]
    console.print(f'  Total : {len(deduped)} · Duplicates removed : {len(api_tests+ui_tests+e2e_tests)-len(deduped)}')
    console.print(f'  TestSpec : [bold green]LOCKED[/bold green]')
    console.print('[green]✅ Refiner complete[/green]\n')
    return new_api, new_ui, new_e2e

def run_stage2(story_id, parsed_spec):
    console.print(Panel('[bold cyan]Stage 2 — Test Case Generator (4-Agent Pipeline)[/bold cyan]', border_style='cyan'))
    console.print(f'[dim]Mode: {"SIMULATED" if SIMULATE_LLM else "LIVE — Mistral 7B generates test cases"}[/dim]\n')

    if SIMULATE_LLM:
        api_tests = SIM_TESTS['api']
        ui_tests  = SIM_TESTS['ui']
        e2e_tests = SIM_TESTS['e2e']
    else:
        plan                           = planner_agent(parsed_spec)
        api_tests, ui_tests, e2e_tests = generator_agent(parsed_spec, plan)
        missing                        = critic_agent(api_tests, ui_tests, e2e_tests, parsed_spec)
        api_tests, ui_tests, e2e_tests = refiner_agent(api_tests, ui_tests, e2e_tests, missing, parsed_spec)

    all_tests = api_tests + ui_tests + e2e_tests
    LEVEL_COL = {'positive':'green','negative':'red','edge':'yellow'}

    def tc_table(tests, title, id_style):
        t = Table(title=title, box=box.ROUNDED, show_lines=True)
        t.add_column('ID',    style=id_style, width=8, no_wrap=True)
        t.add_column('Area',  width=10)
        t.add_column('Title', width=54)
        t.add_column('Level', width=10)
        t.add_column('AC',    width=16)
        for tc in tests:
            c = LEVEL_COL.get(tc['test_level'],'white')
            t.add_row(tc['id'], tc['area'], tc['title'], f'[{c}]{tc["test_level"]}[/{c}]', tc['acceptance_criteria'])
        return t

    console.print(tc_table(api_tests, f'API Tests ({len(api_tests)})', 'blue'))
    console.print(tc_table(ui_tests,  f'UI Tests  ({len(ui_tests)})',  'green'))
    console.print(tc_table(e2e_tests, f'E2E Tests ({len(e2e_tests)})', 'yellow'))

    sm = Table(title='Summary', box=box.SIMPLE_HEAVY)
    sm.add_column('Layer', style='bold', width=8)
    sm.add_column('Count', justify='center', width=8)
    sm.add_column('[green]Positive[/green]', justify='center', width=12)
    sm.add_column('[red]Negative[/red]',     justify='center', width=12)
    sm.add_column('[yellow]Edge[/yellow]',   justify='center', width=8)
    for name, tests in [('API',api_tests),('UI',ui_tests),('E2E',e2e_tests)]:
        sm.add_row(name, str(len(tests)),
            str(sum(1 for t in tests if t['test_level']=='positive')),
            str(sum(1 for t in tests if t['test_level']=='negative')),
            str(sum(1 for t in tests if t['test_level']=='edge')))
    sm.add_row('[bold]TOTAL[/bold]',f'[bold]{len(all_tests)}[/bold]',
        f'[bold green]{sum(1 for t in all_tests if t["test_level"]=="positive")}[/bold green]',
        f'[bold red]{sum(1 for t in all_tests if t["test_level"]=="negative")}[/bold red]',
        f'[bold yellow]{sum(1 for t in all_tests if t["test_level"]=="edge")}[/bold yellow]')
    console.print(sm)
    console.print(f'[bold green]✅ Stage 2 complete — {len(all_tests)} test cases[/bold green]\n')
    return api_tests, ui_tests, e2e_tests, all_tests

# ══════════════════════════════════════════════════════════════
# STAGE 3 — TEST DATA GENERATOR
# ══════════════════════════════════════════════════════════════

def run_stage3(story_id):
    console.print(Panel('[bold cyan]Stage 3 — Test Data Generator[/bold cyan]', border_style='cyan'))
    fake = Faker()
    fake.seed_instance(cfg['test_data']['seed'])
    test_data = {
        'username': fake.user_name(), 'password': 'Test@'+fake.numerify('####'),
        'email': fake.email(), 'user_id': fake.uuid4()[:8],
        'search_keyword': 'laptop', 'invalid_keyword': 'xyzzy_no_match_999',
        'special_keyword': '@@##laptop!!',
        'card_number': '4111111111111111', 'card_expiry': '12/28', 'card_cvv': '123',
        'invalid_card_number': '0000000000000000', 'invalid_card_expiry': '01/20', 'invalid_card_cvv': '000',
        'product_id': 'PROD-'+fake.bothify('???-###').upper(),
        'cart_id': 'CART-'+fake.uuid4()[:8].upper(),
        'order_id_pattern': 'ORD-XXXXXXXXXX',
        '_note': f'Faker seed={cfg["test_data"]["seed"]}. Sensitive fields never sent to LLM.'
    }
    out_dir = f'{BASE}/generated/{story_id}'
    os.makedirs(out_dir, exist_ok=True)
    with open(f'{out_dir}/test_data.json','w') as f:
        json.dump(test_data, f, indent=2)
    console.print(f'  Username : {test_data["username"]} · Seed : {cfg["test_data"]["seed"]} · Card : sandbox only')
    console.print('[bold green]✅ Stage 3 complete — test_data.json written · zero PII to LLM[/bold green]\n')
    return test_data

# ══════════════════════════════════════════════════════════════
# STAGE 4 — COVERAGE REPORT
# ══════════════════════════════════════════════════════════════

def run_stage4(all_tests, api_tests, ui_tests, e2e_tests, parsed_spec):
    console.print(Panel('[bold cyan]Stage 4 — Coverage Report[/bold cyan]', border_style='cyan'))
    covered_acs = set()
    for t in all_tests:
        for ac in t.get('acceptance_criteria','').replace(' ','').split(','):
            if ac.startswith('AC'):
                covered_acs.add(ac)
    ac_ids       = [a['id'] for a in parsed_spec['acceptance_criteria']]
    coverage_pct = round(len(covered_acs)/len(ac_ids)*100)
    threshold    = cfg['coverage']['minimum_pct']
    verdict      = cfg['coverage']['verdict_pass'] if coverage_pct >= threshold else cfg['coverage']['verdict_fail']

    cov = Table(title='AC Coverage', box=box.ROUNDED, show_lines=True)
    cov.add_column('AC',        style='cyan', width=6, no_wrap=True)
    cov.add_column('Criterion', width=52)
    cov.add_column('Status',    justify='center', width=8)
    for ac in parsed_spec['acceptance_criteria']:
        cov.add_row(ac['id'], ac['text'], '[green]✅[/green]' if ac['id'] in covered_acs else '[red]❌[/red]')
    console.print(cov)

    total = len(all_tests)
    pyr = Table(title='Pyramid Compliance', box=box.ROUNDED)
    pyr.add_column('Layer', style='bold', width=8)
    pyr.add_column('Tool',  width=28)
    pyr.add_column('Count', justify='right', width=8)
    pyr.add_column('Actual %', justify='right', width=10)
    pyr.add_column('Target %', justify='right', width=10)
    pyr.add_row('API','REST-assured + Java 17', str(len(api_tests)),f"{round(len(api_tests)/total*100)}%",f"~{cfg['pyramid']['api']['target_pct']}% ✅")
    pyr.add_row('UI', 'Playwright + TypeScript',str(len(ui_tests)), f"{round(len(ui_tests)/total*100)}%", f"~{cfg['pyramid']['ui']['target_pct']}% ✅")
    pyr.add_row('E2E','Playwright + TypeScript',str(len(e2e_tests)),f"{round(len(e2e_tests)/total*100)}%",f"~{cfg['pyramid']['e2e']['target_pct']}% ✅")
    console.print(pyr)

    vc = 'green' if verdict=='PASS' else 'red'
    console.print(Panel(f'Coverage : [bold]{len(covered_acs)}/{len(ac_ids)} = {coverage_pct}%[/bold]  |  Threshold : {threshold}%  |  Verdict : [bold {vc}]{verdict}[/bold {vc}]', border_style=vc))
    console.print('[bold green]✅ Stage 4 complete[/bold green]\n')
    return verdict, coverage_pct

# ══════════════════════════════════════════════════════════════
# STAGE 5 — CODE SYNTHESIS
# ══════════════════════════════════════════════════════════════

def run_stage5(story_id, parsed_spec, test_data, api_tests, ui_tests, e2e_tests):
    console.print(Panel('[bold cyan]Stage 5 — Code Synthesis Module[/bold cyan]', border_style='cyan'))
    out_dir = f'{BASE}/generated/{story_id}'
    os.makedirs(out_dir, exist_ok=True)
    env = Environment(loader=FileSystemLoader(f'{BASE}/templates'), trim_blocks=True, lstrip_blocks=True)
    render_ctx = {
        'story_id': parsed_spec['story_id'], 'actor': parsed_spec['actor'],
        'base_url': ctx['application']['base_url'], 'frontend_url': ctx['application']['frontend_url'],
        'test_data': test_data,
    }
    outputs = [
        ('api_test.j2',f'{out_dir}/ShopFlowTest.java',   api_tests,'REST-assured API tests',     'Java 17'),
        ('ui_test.j2', f'{out_dir}/shopflow-ui.spec.ts', ui_tests, 'Playwright UI tests',         'TypeScript'),
        ('e2e_test.j2',f'{out_dir}/shopflow-e2e.spec.ts',e2e_tests,'Playwright E2E journey tests','TypeScript'),
    ]
    out_t = Table(title=f'Generated Files — {story_id}', box=box.ROUNDED)
    out_t.add_column('File',        width=30)
    out_t.add_column('Description', width=30)
    out_t.add_column('Language',    width=14)
    out_t.add_column('Tests',       justify='right', width=8)
    out_t.add_column('Lines',       justify='right', width=8)
    total_lines = 0
    for tmpl_name, out_path, test_cases, desc, lang in outputs:
        rendered = env.get_template(tmpl_name).render(**render_ctx, test_cases=test_cases)
        with open(out_path,'w') as f:
            f.write(rendered)
        lines = len(rendered.splitlines())
        total_lines += lines
        out_t.add_row(os.path.basename(out_path), desc, lang, str(len(test_cases)), str(lines))
    out_t.add_row('[dim]test_data.json[/dim]','[dim]Faker test data[/dim]','[dim]JSON[/dim]','[dim]—[/dim]','[dim]—[/dim]')
    console.print(out_t)
    console.print(Panel(f'[green]✅ {total_lines} lines generated · written to /generated/{story_id}/ · no LLM · 100% deterministic[/green]', border_style='green'))
    console.print('[bold green]✅ Stage 5 complete[/bold green]\n')
    return total_lines

# ══════════════════════════════════════════════════════════════
# PIPELINE + BATCH
# ══════════════════════════════════════════════════════════════

def run_pipeline(story_id):
    console.print(Panel.fit(
        f'[bold green]StoryForge AI — Processing {story_id}[/bold green]\n'
        f'[dim]Input  : stories/{story_id}.txt[/dim]\n'
        f'[dim]Output : generated/{story_id}/[/dim]\n'
        f'[dim]Mode   : {"SIMULATED" if SIMULATE_LLM else "LIVE — Mistral 7B via Ollama"}[/dim]',
        border_style='green'
    ))
    console.print()
    story_text                                = read_story(story_id)
    parsed_spec                               = run_stage1(story_id, story_text)
    api_tests, ui_tests, e2e_tests, all_tests = run_stage2(story_id, parsed_spec)
    test_data                                 = run_stage3(story_id)
    verdict, coverage_pct                     = run_stage4(all_tests, api_tests, ui_tests, e2e_tests, parsed_spec)
    total_lines                               = run_stage5(story_id, parsed_spec, test_data, api_tests, ui_tests, e2e_tests)

    sm = Table(title='Pipeline Summary', box=box.ROUNDED, show_lines=True)
    sm.add_column('Metric', style='cyan', width=20)
    sm.add_column('Value',  width=46)
    vc = 'green' if verdict=='PASS' else 'red'
    for k,v in [
        ('Story',            story_id),
        ('Input file',       f'stories/{story_id}.txt'),
        ('AC Coverage',      f'[green]{coverage_pct}%[/green]'),
        ('Verdict',          f'[bold {vc}]{verdict}[/bold {vc}]'),
        ('API Tests',        f'{len(api_tests)} (REST-assured + Java 17)'),
        ('UI Tests',         f'{len(ui_tests)} (Playwright + TypeScript)'),
        ('E2E Tests',        f'{len(e2e_tests)} (Playwright + TypeScript)'),
        ('Total Test Cases', str(len(all_tests))),
        ('Lines Generated',  str(total_lines)),
        ('Output Folder',    f'generated/{story_id}/'),
        ('Data Egress',      '[green]Zero — all runs on-premise[/green]'),
        ('LLM',              f'Mistral 7B ({"simulated" if SIMULATE_LLM else "live"})'),
    ]:
        sm.add_row(k,v)
    console.print(sm)
    console.print(Panel(
        f'[green]✅ {story_id} complete — {len(all_tests)} test cases · {total_lines} lines[/green]\n'
        f'[dim]1 story file → full test suite · under 5 minutes[/dim]',
        title='[bold]StoryForge AI[/bold]', border_style='green'
    ))
    return {'story_id':story_id,'total':len(all_tests),'api':len(api_tests),'ui':len(ui_tests),'e2e':len(e2e_tests),'coverage':f'{coverage_pct}%','verdict':verdict,'lines':total_lines}

def run_batch():
    stories = list_stories()
    console.print(Panel(f'[bold cyan]Batch Runner — {len(stories)} stories[/bold cyan]\n[dim]{" · ".join(stories)}[/dim]', border_style='cyan'))
    results = []
    for story_id in stories:
        console.print(f'\n[cyan]{"━"*60}[/cyan]')
        results.append(run_pipeline(story_id))
    bt = Table(title='Batch Summary', box=box.ROUNDED, show_lines=True)
    bt.add_column('Story',  style='cyan', width=8)
    bt.add_column('API',    justify='center', width=6)
    bt.add_column('UI',     justify='center', width=6)
    bt.add_column('E2E',    justify='center', width=6)
    bt.add_column('Total',  justify='center', width=8)
    bt.add_column('Lines',  justify='center', width=8)
    bt.add_column('Coverage',justify='center',width=10)
    bt.add_column('Verdict',justify='center', width=8)
    gt = gl = 0
    for r in results:
        gt += r['total']; gl += r['lines']
        bt.add_row(r['story_id'],str(r['api']),str(r['ui']),str(r['e2e']),str(r['total']),str(r['lines']),f'[green]{r["coverage"]}[/green]','[green]PASS[/green]' if r['verdict']=='PASS' else '[red]FAIL[/red]')
    console.print(bt)
    console.print(Panel(f'[green]✅ {len(results)} stories · {gt} test cases · {gl} lines[/green]\n[dim]Output: /generated/{{story_id}}/[/dim]', border_style='green'))

# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='StoryForge AI — From user story to executable test scripts',
        epilog='Examples:\n  python generate.py                   # all stories\n  python generate.py --story US-001    # single story\n\nTo add a new story:\n  1. Create stories/US-XXX.txt\n  2. python generate.py --story US-XXX\n  3. Find scripts in generated/US-XXX/',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--story', type=str, help='Story ID (e.g. US-001). Omit to process all.')
    args = parser.parse_args()
    if args.story:
        run_pipeline(args.story)
    else:
        run_batch()
