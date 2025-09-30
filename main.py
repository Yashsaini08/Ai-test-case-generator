import os
import re
import time
import json
import traceback
import requests
from difflib import SequenceMatcher
from datetime import datetime
import openai
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
# --- Strip "filename.py:line" tags from all prints ---
import builtins, re

# Matches chunks like: "  neqqq.py:1197", "  Untitled1:1277", " - u.py:1272"
_FILE_TAG_RE = re.compile(r'(?:\s*-?\s*[A-Za-z0-9_.]+\.py:\d+)+')

def _clean_arg(a):
    return _FILE_TAG_RE.sub('', a) if isinstance(a, str) else a

def _patched_print(*args, **kwargs):
    builtins.print(*(_clean_arg(a) for a in args), **kwargs)

print = _patched_print
# --- end patch ---



JIRA_BASE = 'https://actionablescience.atlassian.net'
JIRA_USER = 'yash.saini@rezolve.ai'
JIRA_TOKEN = os.getenv('JIRA_TOKEN', 'ATATT3xFfGF0KSAWeAqwyRgYG-c-4NZFKu89tZH4PSVRrAnCSVWa8cJzeDbylsw8lh9-4Aw9zxsXgAzFp8nDd-l5uOIXDswxhuZVYT26LYI3ZwwH1Orpd8fn6dA5iAw-3BRd5MR1gZB0byQd-chgNmNK0lzFvoG7V0j5-cJsxpUVR1tTaumtkjo=95A910E1'
)  
TESTBANK_PROJECT = "TES"

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY',  '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'
) 

TENANT_URL = 'https://commonqatenant.virtualpeople.ai'
TENANT_USERNAME = 'arun.aadhityaa@rezolve.ai'
TENANT_PASSWORD = os.getenv('TENANT_PASSWORD', 'chennai@1')  # <<< set in env

HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}


try:
    if hasattr(openai, "OpenAI"):
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
    else:
        openai.api_key = OPENAI_API_KEY
        client = openai
    print("OpenAI client initialized successfully  neqqq.py:34  Untitled1:44 - u.py:56")
except Exception as e:
    print(f"Error initializing OpenAI client: {e}  neqqq.py:36  Untitled1:46 - u.py:58")
    client = None



TES_COMPONENTS_CANON = [
    "WebApp", "VAPT", "Ticketing-V2", "Ticketing", "SlackNotification",
    "Service Catalog", "Request mgmt", "Registration", "NewUI", "MSP",
    "Mobile", "Live Chat", "Learning Bot", "Learning App", "Infra",
    "Implementation", "GenAI", "Dataware house", "Creator Studio",
    "Configuration", "Config App", "BWO", "Bot Studio", "Bot Mgmt",
    "Bot-App", "Bot App", "baseFlow", "Automation", "API", "AI/ML",
    "Admin App"
]

KEYWORDS_TO_COMPONENT = {
    
    "service catalog": ["Service Catalog"],
    "service catalogue": ["Service Catalog"],
    "catalog": ["Service Catalog"],
    "request": ["Request mgmt"],
    "request mgmt": ["Request mgmt"],
    "registration": ["Registration"],

    # Ticketing
    "ticket": ["Ticketing", "Ticketing-V2"],
    "ticketing": ["Ticketing", "Ticketing-V2"],
    "ticketing-v2": ["Ticketing-V2"],

    # Bot / VA
    "bot": ["Bot App", "Bot-App", "Bot Mgmt", "Bot Studio", "Learning Bot"],
    "virtual agent": ["Bot App", "Bot-App"],
    "va": ["Bot App", "Bot-App"],
    "studio": ["Creator Studio", "Bot Studio"],

    # Apps & UI
    "web": ["WebApp"],
    "webapp": ["WebApp"],
    "mobile": ["Mobile"],
    "live chat": ["Live Chat"],
    "chat": ["Live Chat"],
    "new ui": ["NewUI"],
    "newui": ["NewUI"],
    "admin": ["Admin App"],
    "admin app": ["Admin App"],
    "learning": ["Learning App", "Learning Bot"],

    # Config / Configuration
    "config": ["Config App", "Configuration"],
    "configuration": ["Configuration"],

    # Integrations / Notif
    "slack": ["SlackNotification"],
    "notification": ["SlackNotification"],

    # Platform / Base
    "infra": ["Infra"],
    "implementation": ["Implementation"],
    "genai": ["GenAI"],
    "ai/ml": ["AI/ML"],
    "ai": ["AI/ML", "GenAI"],
    "ml": ["AI/ML"],
    "data": ["Dataware house"],
    "warehouse": ["Dataware house"],
    "dataware": ["Dataware house"],
    "bwo": ["BWO"],
    "baseflow": ["baseFlow"],
    "automation": ["Automation"],
    "api": ["API"],
    "creator": ["Creator Studio"],
}

def _normalize(s: str) -> str:
    return (s or "").strip().lower()

def _slugify(s: str) -> str:
    """safe label token: lowercase, spaces->-, keep a-z0-9_- only"""
    s = (s or "").lower()
    s = re.sub(r'\s+', '-', s)
    s = re.sub(r'[^a-z0-9_-]', '', s)
    return s.strip('-_')[:40] or 'generic'


# ================================
# JIRA UTILITY FUNCTIONS
# ================================
def jira_get_issue(issue_key):
    try:
        url = f"{JIRA_BASE}/rest/api/2/issue/{issue_key}"
        r = requests.get(url, headers=HEADERS, auth=(JIRA_USER, JIRA_TOKEN), timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Error fetching {issue_key}: {e}  neqqq.py:50  Untitled1:141 - u.py:151")
        raise

def jira_search_jql(jql, max_results=10):
    try:
        url = f"{JIRA_BASE}/rest/api/2/search"
        params = {"jql": jql, "maxResults": max_results}
        r = requests.get(url, headers=HEADERS, params=params, auth=(JIRA_USER, JIRA_TOKEN), timeout=30)
        r.raise_for_status()
        return r.json().get("issues", [])
    except Exception as e:
        print(f"JQL search failed: {e}  neqqq.py:62  Untitled1:152 - u.py:162")
        return []

def get_project_components(project_key):
    try:
        url = f"{JIRA_BASE}/rest/api/2/project/{project_key}/components"
        r = requests.get(url, headers=HEADERS, auth=(JIRA_USER, JIRA_TOKEN), timeout=30)
        r.raise_for_status()
        components = r.json()
        print(f"Found {len(components)} components for {project_key}  neqqq.py:72  Untitled1:161 - u.py:171")
        return components
    except Exception as e:
        print(f"Error fetching components: {e}  neqqq.py:75  Untitled1:164 - u.py:174")
        return []

def get_real_component_names_in_project(project_key):
    comps = get_project_components(project_key) or []
    return [c.get("name", "").strip() for c in comps if c.get("name")]

def resolve_components_for_text(project_key, text: str):
    text_l = _normalize(text)
    if not text_l:
        return []
    cand = []
    for kw, targets in KEYWORDS_TO_COMPONENT.items():
        if kw in text_l:
            cand.extend(targets)
    if not cand:
        if any(k in text_l for k in ["delete", "create", "update", "error", "unable"]):
            cand.extend(["Ticketing-V2", "Ticketing", "Service Catalog"])
    cand = list(dict.fromkeys(cand))
    real = set([_normalize(n) for n in get_real_component_names_in_project(project_key)])
    cand_filtered = [c for c in cand if _normalize(c) in real]
    print(f"Resolver candidates (prefilter): {cand}  Untitled1:185 - u.py:195")
    print(f"Resolver candidates (projectfiltered): {cand_filtered}  Untitled1:186 - u.py:196")
    return cand_filtered

def build_component_jql_clause(component_names):
    if not component_names:
        return ""
    quoted = ",".join([f'"{cn}"' for cn in component_names])
    return f" AND component in ({quoted}) "

def pick_component_id(components, preferred_names_or_text):
    if not components:
        return None
    if isinstance(preferred_names_or_text, list) and preferred_names_or_text:
        want = [_normalize(n) for n in preferred_names_or_text]
        for c in components:
            if _normalize(c.get("name")) in want:
                return c["id"]
    if isinstance(preferred_names_or_text, str) and preferred_names_or_text:
        names = resolve_components_for_text(TESTBANK_PROJECT, preferred_names_or_text)
        if names:
            want = [_normalize(n) for n in names]
            for c in components:
                if _normalize(c.get("name")) in want:
                    return c["id"]
    return components[0]["id"]

def find_best_issue_type_for_tests(project_key):
    try:
        url = f"{JIRA_BASE}/rest/api/2/project/{project_key}"
        r = requests.get(url, headers=HEADERS, auth=(JIRA_USER, JIRA_TOKEN), timeout=30)
        if r.status_code == 200:
            project_data = r.json()
            issue_types = project_data.get('issueTypes', [])
            print(f"Found {len(issue_types)} issue types for {project_key}  neqqq.py:86  Untitled1:219 - u.py:229")
            preferred_types = ["Test", "Test Case", "Testing", "Story", "Task"]
            for preferred in preferred_types:
                for issue_type in issue_types:
                    if issue_type['name'].lower() == preferred.lower():
                        print(f"Using issue type: {issue_type['name']}  neqqq.py:94  Untitled1:224 - u.py:234")
                        return issue_type['name']
            if issue_types:
                first_type = issue_types[0]['name']
                print(f"Using fallback issue type: {first_type}  neqqq.py:100  Untitled1:228 - u.py:238")
                return first_type
        print("Using default issue type: Task  neqqq.py:103  Untitled1:230 - u.py:240")
        return "Task"
    except Exception as e:
        print(f"Error getting issue types: {e}  neqqq.py:106  Untitled1:233 - u.py:243")
        return "Task"

def verify_issue_exists(issue_key):
    try:
        url = f"{JIRA_BASE}/rest/api/2/issue/{issue_key}"
        r = requests.get(url, headers=HEADERS, auth=(JIRA_USER, JIRA_TOKEN), timeout=30)
        if r.status_code == 200:
            print(f"Verified issue exists: {issue_key}  neqqq.py:115  Untitled1:241 - u.py:251")
            return True
        else:
            print(f"Issue does not exist or not accessible: {issue_key} (Status: {r.status_code})  neqqq.py:118  Untitled1:244 - u.py:254")
            return False
    except Exception as e:
        print(f"Error verifying issue {issue_key}: {e}  neqqq.py:121  Untitled1:247 - u.py:257")
        return False

def get_available_link_types():
    try:
        url = f"{JIRA_BASE}/rest/api/2/issueLinkType"
        r = requests.get(url, headers=HEADERS, auth=(JIRA_USER, JIRA_TOKEN), timeout=30)
        r.raise_for_status()
        link_types = r.json().get('issueLinkTypes', [])
        type_names = [lt['name'] for lt in link_types]
        print(f"Available link types: {type_names}  neqqq.py:132  Untitled1:257 - u.py:267")
        return type_names
    except Exception as e:
        print(f"Error fetching link types: {e}  neqqq.py:135  Untitled1:260 - u.py:270")
        return ["Relates", "Tests", "Blocks"]


def jira_create_issue_enhanced(project_key, summary, description, issue_type=None, module_name=None, labels=None):
    """
    Enhanced issue creation with Component mapping + labels.
    `module_name` can be a list of component names OR ticket text to resolve.
    """
    if not issue_type:
        issue_type = find_best_issue_type_for_tests(project_key)

    components = get_project_components(project_key)
    data = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": description,
            "issuetype": {"name": issue_type}
        }
    }

    comp_id = pick_component_id(components, module_name)
    if comp_id:
        data["fields"]["components"] = [{"id": comp_id}]
        print(f"Using component id: {comp_id} for module/component hint: {module_name}  neqqq.py:COMP  Untitled1:285 - u.py:295")

    if labels:
        # JIRA labels must be an array of strings
        data["fields"]["labels"] = list({str(l)[:255] for l in labels})

    try:
        data["fields"]["customfield_11550"] = {"value": "Yes"}
    except Exception:
        pass

    url = f"{JIRA_BASE}/rest/api/2/issue"
    try:
        print(f"Creating issue with type '{issue_type}'...  neqqq.py:163  Untitled1:298 - u.py:308")
        r = requests.post(url, headers=HEADERS, json=data, auth=(JIRA_USER, JIRA_TOKEN), timeout=30)
        if r.status_code in (200, 201):
            issue_key = r.json()["key"]
            print(f"Created issue: {issue_key}  neqqq.py:168  Untitled1:302 - u.py:312")
            return issue_key
        else:
            print(f"Failed to create issue. Status: {r.status_code}  neqqq.py:171  Untitled1:305 - u.py:315")
            print(f"Response: {r.text}  neqqq.py:172  Untitled1:306 - u.py:316")
            if issue_type != "Task":
                print("Retrying with 'Task' issue type...  neqqq.py:176  Untitled1:308 - u.py:318")
                return jira_create_issue_enhanced(project_key, summary, description, "Task", module_name, labels)
            raise Exception(f"Failed to create issue: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Error creating issue: {e}  neqqq.py:182  Untitled1:312 - u.py:322")
        raise

def jira_link_issues_comprehensive(from_key, to_key, preferred_link_type="Tests"):
    print(f"\nAttempting to link {from_key} to {to_key}...  neqqq.py:187  Untitled1:316 - u.py:326")
    if not verify_issue_exists(from_key):
        print(f"Cannot link: {from_key} does not exist  neqqq.py:191  Untitled1:318 - u.py:328")
        return False
    if not verify_issue_exists(to_key):
        print(f"Cannot link: {to_key} does not exist  neqqq.py:195  Untitled1:321 - u.py:331")
        return False

    available_types = get_available_link_types()
    url = f"{JIRA_BASE}/rest/api/2/issueLink"

    link_types_to_try = [preferred_link_type]
    common_types = ["Tests", "Relates", "Related", "Blocks", "Duplicate", "Cloners"]
    for link_type in common_types:
        if link_type not in link_types_to_try and link_type in available_types:
            link_types_to_try.append(link_type)

    for link_type in link_types_to_try:
        try:
            print(f"Trying link type: '{link_type}'  neqqq.py:214  Untitled1:335 - u.py:345")
            link_configs = [
                {"inwardIssue": {"key": from_key}, "outwardIssue": {"key": to_key}},
                {"inwardIssue": {"key": to_key}, "outwardIssue": {"key": from_key}}
            ]
            for config in link_configs:
                data = {"type": {"name": link_type}, **config}
                r = requests.post(url, headers=HEADERS, json=data, auth=(JIRA_USER, JIRA_TOKEN), timeout=30)
                if r.status_code in (200, 201, 204):
                    direction = "→" if config["inwardIssue"]["key"] == from_key else "←"
                    print(f"SUCCESS: {from_key} {direction} {to_key} using '{link_type}'  neqqq.py:232  Untitled1:345 - u.py:355")
                    return True
        except Exception as e:
            print(f"Exception with {link_type}: {e}  neqqq.py:236  Untitled1:348 - u.py:358")
            continue

    print(f"All linking attempts failed for {from_key} ↔ {to_key}  neqqq.py:239  Untitled1:351 - u.py:361")
    return False


# ================================
# CONTEXT & MATCHING
# ================================
def extract_problem_context(text):
    if not text:
        return {}

    text_lower = text.lower()
    context = {
        'module': None,
        'problem_type': None,
        'specific_feature': None,
        'action': None,
        'keywords': []
    }

    modules = {
        'service catalog': ['service catalog', 'service catalogue'],
        'config app': ['config app', 'configuration app'],
        'quick actions': ['quick action', 'quick actions'],
        'virtual agent': ['virtual agent', 'va management', 'virtual assistant', 'bot'],
        'dashboard': ['dashboard', 'dashboards'],
        'workflow': ['workflow', 'workflows'],
        'notification': ['notification', 'notifications', 'alert', 'alerts'],
        'ticketing': ['ticketing', 'ticketing-v2', 'ticket']
    }
    for module_name, patterns in modules.items():
        for pattern in patterns:
            if pattern in text_lower:
                context['module'] = module_name
                break
        if context['module']:
            break

    problem_patterns = {
        'deletion': ['unable to delete', 'cannot delete', 'delete error', 'deletion issue', 'deleting', 'delete'],
        'creation': ['unable to create', 'cannot create', 'create error', 'creation issue', 'create', 'add'],
        'update': ['unable to update', 'cannot update', 'update error', 'updating issue', 'update', 'edit', 'modify'],
        'display': ['not displaying', 'display error', 'not showing', 'visibility issue', 'display', 'showing'],
        'validation': ['validation error', 'validation issue', 'invalid'],
        'permission': ['permission denied', 'access denied', 'unauthorized'],
        'performance': ['slow', 'performance', 'timeout', 'loading'],
        'dropdown': ['dropdown', 'drop down', 'select list', 'picker'],
        'filter': ['filter', 'filtering', 'search filter'],
        'import': ['import', 'importing', 'data import'],
        'export': ['export', 'exporting', 'download'],
        'assignment': ['assignment', 'assign', 'assigning']
    }
    for prob_type, patterns in problem_patterns.items():
        for pattern in patterns:
            if pattern in text_lower:
                context['problem_type'] = prob_type
                break
        if context['problem_type']:
            break

    feature_patterns = {
        'ticket_type': ['ticket type', 'ticket-type', 'tickettype'],
        'actor_filter': ['actor filter', 'actor dropdown', 'actor selection'],
        'dependent_field': ['dependent field', 'field dependency'],
        'parent_field': ['parent field'],
        'custom_field': ['custom field'],
        'event_action': ['event', 'action', 'event & action'],
        'approval': ['approval', 'approve', 'approved'],
        'draft': ['draft', 'drafts'],
        'status': ['status', 'state'],
        'category': ['category', 'categories']
    }
    for feature_name, patterns in feature_patterns.items():
        for pattern in patterns:
            if pattern in text_lower:
                context['specific_feature'] = feature_name
                context['keywords'].append(pattern)
                break

    action_verbs = ['delete', 'create', 'update', 'edit', 'add', 'remove', 'import',
                    'export', 'assign', 'filter', 'search', 'display', 'show', 'hide']
    for verb in action_verbs:
        if verb in text_lower:
            context['action'] = verb
            break

    for word in text_lower.split():
        if len(word) > 4 and word not in ['that', 'this', 'when', 'where', 'what', 'which']:
            context['keywords'].append(word)
    context['keywords'] = list(set(context['keywords']))[:10]
    return context

def calculate_detailed_relevance_score(source_context, candidate_text):
    if not candidate_text:
        return 0
    candidate_lower = candidate_text.lower()
    score = 0

    if source_context['module'] and source_context['module'] in candidate_lower:
        score += 15
    if source_context['problem_type']:
        problem_keywords = {
            'deletion': ['delete', 'deletion', 'removing', 'unable to delete'],
            'creation': ['create', 'creation', 'adding', 'unable to create'],
            'update': ['update', 'updating', 'edit', 'modify'],
            'display': ['display', 'showing', 'visibility', 'visible'],
            'dropdown': ['dropdown', 'select', 'picker', 'list'],
            'filter': ['filter', 'filtering', 'search'],
            'assignment': ['assign', 'assignment', 'assigning']
        }
        if source_context['problem_type'] in problem_keywords:
            for keyword in problem_keywords[source_context['problem_type']]:
                if keyword in candidate_lower:
                    score += 25
                    break

    if source_context['specific_feature']:
        feature_keywords = {
            'ticket_type': ['ticket type', 'ticket-type'],
            'actor_filter': ['actor', 'filter', 'actor filter'],
            'dependent_field': ['dependent', 'field dependency'],
            'parent_field': ['parent field'],
            'custom_field': ['custom field'],
            'event_action': ['event', 'action'],
            'approval': ['approval', 'approved'],
            'draft': ['draft'],
            'status': ['status', 'state'],
            'category': ['category']
        }
        if source_context['specific_feature'] in feature_keywords:
            for keyword in feature_keywords[source_context['specific_feature']]:
                if keyword in candidate_lower:
                    score += 30
                    break

    if source_context['action'] and source_context['action'] in candidate_lower:
        score += 10

    matching_keywords = 0
    for keyword in source_context['keywords']:
        if keyword in candidate_lower:
            matching_keywords += 1
    if source_context['keywords']:
        score += (matching_keywords / len(source_context['keywords'])) * 20

    if source_context['module']:
        wrong_modules = ['service catalog', 'config app', 'quick actions', 'virtual agent',
                         'dashboard', 'workflow', 'notification', 'ticketing']
        try:
            wrong_modules.remove(source_context['module'])
        except ValueError:
            pass
        for wrong_module in wrong_modules:
            if wrong_module in candidate_lower:
                score -= 40
                break

    if source_context['problem_type']:
        opposite = {
            'deletion': ['create', 'creating', 'addition'],
            'creation': ['delete', 'deletion', 'removing'],
            'display': ['hidden', 'hiding'],
        }
        if source_context['problem_type'] in opposite:
            for o in opposite[source_context['problem_type']]:
                if o in candidate_lower and (not source_context['action'] or source_context['action'] not in candidate_lower):
                    score -= 20
    return score


# ================================
# PARENT REFERENCE KEY + PARENT SELECTION/CREATION
# ================================
def build_parent_ref_slug(component_names, source_context):
    comp = _slugify((component_names[0] if component_names else 'generic'))
    spec = _slugify(source_context.get('specific_feature') or 'generic')
    prob = _slugify(source_context.get('problem_type') or 'generic')
    # deterministic label used for finding/creating the parent
    return f"parentref_{comp}_{spec}_{prob}"

def find_or_create_test_parent_smart(source_ticket_id, summary, description):
    print("\n  neqqq.py:432  Untitled1:532 - u.py:542" + "="*60)
    print("SMART TEST PARENT FINDER  CONTEXT AWARE (Componentscoped + Reference)  neqqq.py:433  Untitled1:533 - u.py:543")
    print("=  Untitled1:534 - u.py:544"*60)

    source_content = f"{summary} {description}"
    source_context = extract_problem_context(source_content)

    print(f"Module: {source_context['module']}  neqqq.py:440  Untitled1:539 - u.py:549")
    print(f"Problem Type: {source_context['problem_type']}  neqqq.py:441  Untitled1:540 - u.py:550")
    print(f"Specific Feature: {source_context['specific_feature']}  neqqq.py:442  Untitled1:541 - u.py:551")
    print(f"Action: {source_context['action']}  neqqq.py:443  Untitled1:542 - u.py:552")
    print(f"Keywords: {', '.join(source_context['keywords'][:5])}  neqqq.py:444  Untitled1:543 - u.py:553")

    # Resolve Component(s) and parent reference label
    component_names = resolve_components_for_text(TESTBANK_PROJECT, source_content)
    comp_clause = build_component_jql_clause(component_names)
    if component_names:
        print(f"Scoping search to components: {component_names}  Untitled1:549 - u.py:559")
    else:
        print("No matching components found for this ticket; search will not be componentfiltered.  Untitled1:551 - u.py:561")
    parent_ref = build_parent_ref_slug(component_names, source_context)
    print(f"Parent reference label: {parent_ref}  Untitled1:553 - u.py:563")

    # 0) Strongest signal: an existing Parent with the same parent_ref label
    strong_jql = f'project = "{TESTBANK_PROJECT}"{comp_clause} AND labels = "{parent_ref}" ORDER BY created DESC'
    print(f"Query (label match): {strong_jql}  Untitled1:557 - u.py:567")
    hits = jira_search_jql(strong_jql, max_results=5)
    if hits:
        key = hits[0]["key"]
        print(f"✓ Found existing parent by reference label: {key}  Untitled1:561 - u.py:571")
        return key

    # 1) Contextual search (component-scoped), as a fallback
    search_queries = []
    if source_context['specific_feature'] and source_context['problem_type'] and source_context['module']:
        search_queries.append(
            f'project = "{TESTBANK_PROJECT}"{comp_clause}'
            f'AND (summary ~ "{source_context["module"]}" OR description ~ "{source_context["module"]}") '
            f'AND (summary ~ "{source_context["specific_feature"].replace("_", " ")}" OR '
            f'description ~ "{source_context["specific_feature"].replace("_", " ")}") '
            f'ORDER BY created DESC'
        )
    if source_context['problem_type'] and source_context['module']:
        search_queries.append(
            f'project = "{TESTBANK_PROJECT}"{comp_clause}'
            f'AND summary ~ "{source_context["module"]}" '
            f'AND (summary ~ "{source_context["problem_type"]}" OR description ~ "{source_context["problem_type"]}") '
            f'ORDER BY created DESC'
        )
    if source_context['specific_feature']:
        search_queries.append(
            f'project = "{TESTBANK_PROJECT}"{comp_clause}'
            f'AND (summary ~ "{source_context["specific_feature"].replace("_", " ")}" OR '
            f'description ~ "{source_context["specific_feature"].replace("_", " ")}") '
            f'ORDER BY created DESC'
        )
    if source_context['keywords']:
        for keyword in source_context['keywords'][:3]:
            if len(keyword) > 5:
                search_queries.append(
                    f'project = "{TESTBANK_PROJECT}"{comp_clause}'
                    f'AND (summary ~ "{keyword}" OR description ~ "{keyword}") '
                    f'ORDER BY created DESC'
                )
    if source_context['module']:
        search_queries.append(
            f'project = "{TESTBANK_PROJECT}"{comp_clause}'
            f'AND summary ~ "Test Parent" AND summary ~ "{source_context["module"]}" '
            f'ORDER BY created DESC'
        )

    best_candidate = None
    best_score = -100
    candidates_evaluated = []

    print(f"\nSearching for componentscoped test parents...  neqqq.py:500  Untitled1:607 - u.py:617")
    print(f"Will evaluate up to {len(search_queries)} targeted queries  neqqq.py:501  Untitled1:608 - u.py:618")

    for i, query in enumerate(search_queries, 1):
        try:
            print(f"\nQuery {i}/{len(search_queries)}: {query[:180]}...  neqqq.py:505  Untitled1:612 - u.py:622")
            candidates = jira_search_jql(query, max_results=10)
            if candidates:
                print(f"Found {len(candidates)} candidates  neqqq.py:509  Untitled1:615 - u.py:625")
                for candidate in candidates:
                    key = candidate["key"]
                    fields = candidate.get("fields", {})
                    cand_summary = fields.get("summary", "") or ""
                    cand_desc = fields.get("description", "") or ""
                    cand_text = f"{cand_summary} {cand_desc}"

                    score = calculate_detailed_relevance_score(source_context, cand_text)
                    cand_components = [c.get("name", "") for c in fields.get("components", [])]
                    has_comp = (not component_names) or any(cc in component_names for cc in cand_components)
                    if not has_comp:
                        score -= 40
                    if "test parent" in cand_summary.lower():
                        score += 10

                    candidates_evaluated.append({'key': key, 'summary': cand_summary[:60], 'score': score})
                    print(f"{key}: {cand_summary[:60]}... (Score: {score})  neqqq.py:527  Untitled1:632 - u.py:642")

                    if score > best_score:
                        best_score = score
                        best_candidate = key

                if best_score >= 70:
                    print(f"Found excellent contextual match with score {best_score}, stopping search  neqqq.py:535  Untitled1:639 - u.py:649")
                    break
            else:
                print("No candidates found for this query  neqqq.py:538  Untitled1:642 - u.py:652")
        except Exception as e:
            print(f"Query failed: {e}  neqqq.py:541  Untitled1:644 - u.py:654")
            continue

    print(f"\n  neqqq.py:545  Untitled1:647 - u.py:657" + "="*40)
    print("EVALUATION RESULTS  neqqq.py:546  Untitled1:648 - u.py:658")
    print("=  Untitled1:649 - u.py:659"*40)
    if candidates_evaluated:
        for c in sorted(candidates_evaluated, key=lambda x: x['score'], reverse=True)[:5]:
            print(f"{c['key']}: {c['summary']} (Score: {c['score']})  neqqq.py:552  Untitled1:652 - u.py:662")

    if best_candidate and best_score >= 70:
        print(f"\n✓ Selected componentscoped parent: {best_candidate} (Score: {best_score})  neqqq.py:STRICT  Untitled1:655 - u.py:665")
        return best_candidate

    # Create a brand new Parent in the correct Component, MARKED with parent labels
    print(f"\n✗ No suitable parent in components {component_names or '[any]'} (best score: {best_score})  Untitled1:659 - u.py:669")
    print("Creating new contextually specific parent under the right component...  Untitled1:660 - u.py:670")

    problem_desc = ""
    if source_context['problem_type']:
        problem_desc = f" - {source_context['problem_type'].replace('_', ' ').title()} Issue"
    elif source_context['action']:
        problem_desc = f" - {source_context['action'].title()} Functionality"

    feature_desc = ""
    if source_context['specific_feature']:
        feature_desc = f" for {source_context['specific_feature'].replace('_', ' ').title()}"

    parent_summary = f"[PARENT] Test Parent - {(component_names[0] if component_names else (source_context['module'] or 'General')).title()}{feature_desc}{problem_desc}"
    if len(parent_summary) > 255:
        parent_summary = parent_summary[:252] + "..."

    parent_description = f"""Test Parent for Specific Context

Related Ticket: {source_ticket_id}
Component: {component_names[0] if component_names else 'General'}
Problem Type: {source_context['problem_type'] or 'General'}
Specific Feature: {source_context['specific_feature'] or 'N/A'}
Action: {source_context['action'] or 'N/A'}

Parent Reference Label: {parent_ref}

Original Summary: {summary}

Original Description:
{description[:500]}...

Context Keywords: {', '.join(source_context['keywords'][:10])}
"""

    try:
        parent_key = jira_create_issue_enhanced(
            TESTBANK_PROJECT,
            parent_summary,
            parent_description,
            issue_type=None,
            module_name=(component_names or source_context['module']),
            labels=["parent", parent_ref]  # <<< mark as Parent + deterministic reference
        )
        print(f"✓ Created new parent under correct component: {parent_key}  Untitled1:703 - u.py:713")
        return parent_key
    except Exception as e:
        print(f"✗ Failed to create test parent: {e}  Untitled1:706 - u.py:716")
        raise Exception(f"Could not create test parent: {e}")


# ================================
# EXISTING CASES & DEDUPLICATION
# ================================
def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def summarize_case(tc):
    return " ".join([
        tc.get('id', ''),
        tc.get('description', ''),
        tc.get('steps', ''),
        tc.get('expected', '')
    ])

def get_existing_test_cases_text_for_issues(issue_keys):
    existing_text = ""
    seen = set()
    for key in issue_keys:
        try:
            issue = jira_get_issue(key)
            links = issue["fields"].get("issuelinks", [])
            for link in links:
                for direction in ['inwardIssue', 'outwardIssue']:
                    if direction in link:
                        linked = link[direction]
                        lid = linked.get("key")
                        if not lid or lid in seen:
                            continue
                        seen.add(lid)
                        fields = linked.get("fields", {})
                        summary = fields.get("summary", "") or ""
                        description = fields.get("description", "") or ""
                        existing_text += f"- {summary}\n{description[:600]}...\n\n"
        except Exception as e:
            print(f"Link scan error on {key}: {e}  Untitled1:744 - u.py:754")
    if existing_text:
        print(f"Found existing test case content: {len(existing_text)} characters  neqqq.py:628  Untitled1:746 - u.py:756")
    else:
        print("No existing test cases found  neqqq.py:630  Untitled1:748 - u.py:758")
    return existing_text

def dedupe_generated_cases(generated_cases, existing_blob, min_sim=0.82):
    keep = []
    window = (existing_blob[-16000:] if existing_blob and len(existing_blob) > 16000 else (existing_blob or ""))
    for tc in generated_cases:
        s = summarize_case(tc)
        sim = similarity(s, window)
        if sim >= min_sim:
            print(f"Skipping nearduplicate generated case (sim={sim:.2f}) > {tc.get('id')}  Untitled1:758 - u.py:768")
            continue
        keep.append(tc)
    return keep


# ================================
# TEST CASE GENERATION
# ================================
def generate_user_friendly_test_cases(summary, description, existing_cases_text, count=5):
    avoid_text = existing_cases_text if existing_cases_text else "No existing test cases to avoid."
    ctx = extract_problem_context(f"{summary} {description}")
    product_hint = f"\nProduct/Module: {ctx['module'].title()}" if ctx.get('module') else ""

    prompt = f"""Create {count} test cases for: {summary}
{product_hint}

Description: {description}

Avoid duplicating: {avoid_text}

STRICT RULES:
- The test cases MUST be for the same product/module: {ctx.get('module','(unknown)')}
- Focus on the actual problem context (e.g., {ctx.get('problem_type','general')} / {ctx.get('specific_feature','feature')})
- IDs must be TC_QA_XX and unique.
- Each must include: ID, DESCRIPTION, PRECONDITION, STEPS, EXPECTED.
- Prefer realistic field names/buttons (e.g., Ticket Types > Delete, confirmation dialogs, error banners).

FORMAT EXACTLY:
===TEST_CASE_START===
ID: TC_QA_01
DESCRIPTION: ...
PRECONDITION: ...
STEPS: ...
EXPECTED: ...
===TEST_CASE_END===

Generate {count} distinct cases."""

    try:
        print("Generating userfriendly test cases with GPT...  neqqq.py:671  Untitled1:798 - u.py:808")
        if hasattr(client, "chat") and hasattr(client.chat, "completions"):
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3000,
                temperature=0.2
            )
            generated_content = response.choices[0].message.content
        else:
            response = client.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3000,
                temperature=0.2
            )
            generated_content = response.choices[0].message["content"]

        print(f"Generated {len(generated_content)} characters of test case content  neqqq.py:680  Untitled1:816 - u.py:826")
        return generated_content
    except Exception as e:
        print(f"Error generating test cases: {e}  neqqq.py:684  Untitled1:819 - u.py:829")
        return ""

def parse_generated_test_cases(content):
    test_cases = []
    print(f"DEBUG: First 500 chars of generated content:\n{content[:500]}  neqqq.py:692  Untitled1:824 - u.py:834")

    delimiters = [
        ('===TEST_CASE_START===', '===TEST_CASE_END==='),
        ('TEST_CASE_START', 'TEST_CASE_END'),
        ('---TEST CASE---', '---END TEST CASE---'),
        ('**Test Case', '**'),
    ]

    sections = []
    for start_delim, _ in delimiters:
        if start_delim in content:
            print(f"Found delimiter: {start_delim}  neqqq.py:705  Untitled1:836 - u.py:846")
            temp_sections = content.split(start_delim)
            if len(temp_sections) > 1:
                sections = temp_sections
                break

    if not sections or len(sections) <= 1:
        print("No standard delimiters found, attempting alternative parsing...  neqqq.py:713  Untitled1:843 - u.py:853")
        patterns = [
            r'(?:Test Case|TC_?|ID:?\s*TC_?)[\s#]*(\d+)',
            r'(?:\d+\.|\d+\))\s*(?:Test|Verify)',
        ]
        for pattern in patterns:
            matches = re.split(pattern, content, flags=re.IGNORECASE)
            if len(matches) > 1:
                print(f"Found pattern matches: {len(matches)}  neqqq.py:726  Untitled1:851 - u.py:861")
                for i in range(1, len(matches), 2):
                    if i < len(matches):
                        sections.append(matches[i] if i == 1 else matches[i-1] + matches[i])
                break
        if not sections or len(sections) <= 1:
            sections = [content]

    for idx, section in enumerate(sections):
        if idx == 0 and not any(marker in section.upper() for marker in ['TEST', 'TC', 'ID']):
            continue

        test_case = {}
        for _, end_delim in delimiters:
            if end_delim in section:
                section = section.split(end_delim)[0]
        section = section.strip()
        if not section:
            continue

        lines = section.split('\n')
        current_field = None
        current_content = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            upper_line = line.upper()
            if any(marker in upper_line for marker in ['ID:', 'TEST ID:', 'TC:', 'TEST CASE ID:']):
                if current_field and current_content:
                    test_case[current_field] = ' '.join(current_content)
                current_field = 'id'
                id_value = line.split(':', 1)[-1].strip()
                if not id_value:
                    id_value = f'TC_QA_{idx:02d}'
                test_case['id'] = id_value
                current_content = []
            elif any(marker in upper_line for marker in ['DESCRIPTION:', 'DESC:', 'OBJECTIVE:', 'PURPOSE:']):
                if current_field and current_content:
                    test_case[current_field] = ' '.join(current_content)
                current_field = 'description'
                desc_value = line.split(':', 1)[-1].strip()
                current_content = [desc_value] if desc_value else []
            elif any(marker in upper_line for marker in ['PRECONDITION:', 'PREREQUISITE:', 'SETUP:', 'GIVEN:']):
                if current_field and current_content:
                    test_case[current_field] = ' '.join(current_content)
                current_field = 'precondition'
                pre_value = line.split(':', 1)[-1].strip()
                current_content = [pre_value] if pre_value else []
            elif any(marker in upper_line for marker in ['STEPS:', 'TEST STEPS:', 'PROCEDURE:', 'WHEN:']):
                if current_field and current_content:
                    test_case[current_field] = ' '.join(current_content)
                current_field = 'steps'
                steps_value = line.split(':', 1)[-1].strip()
                current_content = [steps_value] if steps_value else []
            elif any(marker in upper_line for marker in ['EXPECTED:', 'EXPECTED RESULT:', 'RESULT:', 'THEN:', 'OUTCOME:']):
                if current_field and current_content:
                    test_case[current_field] = ' '.join(current_content)
                current_field = 'expected'
                exp_value = line.split(':', 1)[-1].strip()
                current_content = [exp_value] if exp_value else []
            elif current_field:
                current_content.append(line)

        if current_field and current_content:
            test_case[current_field] = ' '.join(current_content)

        if not test_case.get('id'):
            test_case['id'] = f'TC_QA_{idx:02d}'
        if not test_case.get('description'):
            if test_case.get('steps'):
                steps_lower = test_case['steps'].lower()
                if 'delete' in steps_lower:
                    test_case['description'] = 'Verify deletion functionality'
                elif 'create' in steps_lower or 'add' in steps_lower:
                    test_case['description'] = 'Verify creation functionality'
                elif 'update' in steps_lower or 'edit' in steps_lower:
                    test_case['description'] = 'Verify update functionality'
                else:
                    test_case['description'] = 'Verify system functionality'
            else:
                test_case['description'] = f'Test Case {idx}'
        if not test_case.get('precondition'):
            test_case['precondition'] = 'User is logged in with appropriate permissions'
        if not test_case.get('steps'):
            if len(section) > 50:
                test_case['steps'] = 'Perform the test actions as described'
            else:
                continue
        if not test_case.get('expected'):
            steps_lower = test_case.get('steps', '').lower()
            desc_lower = test_case.get('description', '').lower()
            if 'delete' in steps_lower or 'delete' in desc_lower:
                if 'error' in steps_lower or 'unable' in desc_lower:
                    test_case['expected'] = 'System should display appropriate error message'
                else:
                    test_case['expected'] = 'Item is successfully deleted from the system'
            elif 'create' in steps_lower or 'add' in steps_lower:
                test_case['expected'] = 'New item is successfully created and saved'
            elif 'verify' in steps_lower or 'verify' in desc_lower:
                test_case['expected'] = 'System displays correct information as expected'
            else:
                test_case['expected'] = 'System performs the action successfully'

        if test_case.get('id') and test_case.get('steps'):
            test_cases.append(test_case)
            print(f"Added test case: {test_case['id']}  neqqq.py:856  Untitled1:957 - u.py:967")

    if not test_cases and len(content) > 100:
        print("Creating default test cases from content...  neqqq.py:860  Untitled1:960 - u.py:970")
        test_cases = [
            {
                'id': 'TC_QA_01',
                'description': 'Verify primary functionality',
                'precondition': 'System is accessible and user has required permissions',
                'steps': 'Execute the main workflow as per requirements',
                'expected': 'System behaves as expected without errors'
            },
            {
                'id': 'TC_QA_02',
                'description': 'Verify error handling',
                'precondition': 'System is accessible and user has required permissions',
                'steps': 'Attempt invalid operations to test error handling',
                'expected': 'System displays appropriate error messages and handles errors gracefully'
            }
        ]
    print(f"Total parsed test cases: {len(test_cases)}  neqqq.py:879  Untitled1:977 - u.py:987")
    for tc in test_cases:
        print(f"{tc['id']}: {tc.get('description', 'No description')[:50]}  neqqq.py:881  Untitled1:979 - u.py:989")
    return test_cases


# ================================
# AUTOMATION (optional)
# ================================
def setup_chrome_driver():
    options = Options()
    options.add_argument('--start-maximized')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--disable-extensions')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    try:
        driver = webdriver.Chrome(options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        print("Chrome driver initialized successfully  neqqq.py:902  Untitled1:998 - u.py:1008")
        return driver
    except Exception as e:
        print(f"Failed to initialize Chrome driver: {e}  neqqq.py:905  Untitled1:1001 - u.py:1011")
        return None

def perform_tenant_login_enhanced(driver):
    try:
        print(f"Navigating to: {TENANT_URL}  neqqq.py:911  Untitled1:1006 - u.py:1016")
        driver.get(TENANT_URL)
        time.sleep(5)
        print("Looking for login form...  neqqq.py:915  Untitled1:1009 - u.py:1019")
        username_selectors = [
            (By.NAME, "username"),
            (By.ID, "username"),
            (By.NAME, "email"),
            (By.ID, "email"),
            (By.CSS_SELECTOR, "input[type='email']"),
            (By.CSS_SELECTOR, "input[type='text'][name*='user']"),
            (By.XPATH, "//input[contains(@placeholder, 'email')]"),
            (By.XPATH, "//input[@type='text']")
        ]
        username_field = None
        for by, selector in username_selectors:
            try:
                elements = driver.find_elements(by, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        username_field = element
                        print(f"Found username field using: {selector}  neqqq.py:935  Untitled1:1027 - u.py:1037")
                        break
                if username_field:
                    break
            except:
                continue
        if not username_field:
            print("Could not find username field  neqqq.py:943  Untitled1:1034 - u.py:1044")
            return False
        password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        if not password_field:
            print("Could not find password field  neqqq.py:948  Untitled1:1038 - u.py:1048")
            return False
        print("Entering credentials...  neqqq.py:951  Untitled1:1040 - u.py:1050")
        username_field.clear()
        username_field.send_keys(TENANT_USERNAME)
        time.sleep(1)
        password_field.clear()
        password_field.send_keys(TENANT_PASSWORD)
        time.sleep(1)
        print("Submitting login...  neqqq.py:960  Untitled1:1047 - u.py:1057")
        password_field.send_keys(Keys.RETURN)
        time.sleep(8)
        current_url = driver.current_url.lower()
        success_indicators = ['dashboard', 'home', 'main', 'portal', 'app']
        if any(indicator in current_url for indicator in success_indicators):
            print("Login appears successful!  neqqq.py:968  Untitled1:1053 - u.py:1063")
            return True
        else:
            print("Login status unclear, proceeding with caution  neqqq.py:971  Untitled1:1056 - u.py:1066")
            return True
    except Exception as e:
        print(f"Login failed: {e}  neqqq.py:975  Untitled1:1059 - u.py:1069")
        return False


# ================================
# MAIN PROCESSING
# ================================
def process_ticket_with_automation(ticket_id, generate_count=5, run_automation=False):
    print(f"\n{'='*80}  neqqq.py:984  Untitled1:1067 - u.py:1077")
    print(f"PROCESSING TICKET: {ticket_id}  neqqq.py:985  Untitled1:1068 - u.py:1078")
    print(f"GENERATING {generate_count} TEST CASES  neqqq.py:986  Untitled1:1069 - u.py:1079")
    print(f"AUTOMATION: {'ENABLED' if run_automation else 'DISABLED'}  neqqq.py:987  Untitled1:1070 - u.py:1080")
    print(f"{'='*80}  neqqq.py:988  Untitled1:1071 - u.py:1081")

    # 1) Source ticket
    try:
        print("\nFetching source ticket...  neqqq.py:992  Untitled1:1075 - u.py:1085")
        source_issue = jira_get_issue(ticket_id)
        source_fields = source_issue["fields"]
        summary = source_fields.get("summary", "")
        description = source_fields.get("description", "") or ""
        print(f"Source ticket: {summary}  neqqq.py:998  Untitled1:1080 - u.py:1090")
        print(f"Description: {description[:100]}{'...' if len(description) > 100 else ''}  neqqq.py:999  Untitled1:1081 - u.py:1091")
    except Exception as e:
        print(f"Failed to fetch ticket {ticket_id}: {e}  neqqq.py:1002  Untitled1:1083 - u.py:1093")
        return None

    # 2) Parent (component-scoped + reference label)
    try:
        print("\nFinding/creating test parent with SMART matching...  neqqq.py:1007  Untitled1:1088 - u.py:1098")
        parent_key = find_or_create_test_parent_smart(ticket_id, summary, description)
        print(f"Test parent: {parent_key}  neqqq.py:1009  Untitled1:1090 - u.py:1100")
    except Exception as e:
        print(f"Failed to create test parent: {e}  neqqq.py:1012  Untitled1:1092 - u.py:1102")
        return None

    # 3) Existing content (parent + source)
    print("\nChecking existing test cases (parent + source links)...  neqqq.py:1016  Untitled1:1096 - u.py:1106")
    existing_cases_text = get_existing_test_cases_text_for_issues([parent_key, ticket_id])

    # 4) Generate
    print(f"\nGenerating {generate_count} new test cases...  neqqq.py:1020  Untitled1:1100 - u.py:1110")
    if not client:
        print("OpenAI client not available  neqqq.py:1022  Untitled1:1102 - u.py:1112")
        return None
    generated_content = generate_user_friendly_test_cases(
        summary, description, existing_cases_text, generate_count
    )
    if not generated_content:
        print("Failed to generate test cases  neqqq.py:1030  Untitled1:1108 - u.py:1118")
        return None

    # 5) Parse + de-duplicate
    print("\nParsing generated test cases...  neqqq.py:1034  Untitled1:1112 - u.py:1122")
    test_cases = parse_generated_test_cases(generated_content)
    if not test_cases:
        print("No valid test cases could be parsed  neqqq.py:1038  Untitled1:1115 - u.py:1125")
        return None
    print("Deduplicating generated test cases...  neqqq.py:1039  Untitled1:1117 - u.py:1127")
    test_cases = dedupe_generated_cases(test_cases, existing_cases_text, min_sim=0.82)
    if not test_cases:
        print("All generated cases looked duplicate; relaxing threshold once  neqqq.py:1040  Untitled1:1120 - u.py:1130")
        test_cases = dedupe_generated_cases(parse_generated_test_cases(generated_content), existing_cases_text, min_sim=0.90)
        if not test_cases:
            print("No nonduplicate test cases remain  neqqq.py:1041  Untitled1:1123 - u.py:1133")
            return None
    print(f"Parsed {len(test_cases)} nonduplicate test cases  neqqq.py:1041  Untitled1:1125 - u.py:1135")

    # 6) Create one comprehensive suite (in same Component)
    print(f"\nCreating ONE comprehensive test suite issue...  neqqq.py:1044  Untitled1:1128 - u.py:1138")
    try:
        suite_summary = f"Test Suite - {summary[:100]}"
        if len(suite_summary) > 255:
            suite_summary = suite_summary[:252] + "..."

        suite_description = f"""**COMPREHENSIVE TEST SUITE**

**Source Ticket:** {ticket_id}
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total Test Cases:** {len(test_cases)}

---

## Test Cases Table

| Test Case ID | Test Case Description | Precondition | Steps | Expected Result |
|--------------|----------------------|--------------|-------|-----------------|
"""
        for i, test_case in enumerate(test_cases):
            test_id = test_case.get('id', f'TC_QA_{i+1:02d}')
            description_text = test_case.get('description', 'Test case description').replace('\n', ' ').replace('|', '\\|')
            precondition = test_case.get('precondition', 'None').replace('\n', ' ').replace('|', '\\|')
            steps = test_case.get('steps', 'No steps').replace('\n', ' ').replace('|', '\\|')
            expected = test_case.get('expected', 'Expected result').replace('\n', ' ').replace('|', '\\|')
            suite_description += f"| {test_id} | {description_text} | {precondition} | {steps} | {expected} |\n"

        suite_description += f"""

---

*Single comprehensive test suite containing all {len(test_cases)} test cases*
"""

        # Put suite in the same component as the ticket
        suite_components = resolve_components_for_text(TESTBANK_PROJECT, f"{summary} {description}")
        comprehensive_key = jira_create_issue_enhanced(
            TESTBANK_PROJECT,
            suite_summary,
            suite_description,
            issue_type=None,
            module_name=(suite_components or extract_problem_context(f"{summary} {description}").get('module'))
        )

        if comprehensive_key:
            print(f"Created comprehensive test suite: {comprehensive_key}  neqqq.py:1091  Untitled1:1173 - u.py:1183")

            # Link to parent
            if parent_key:
                print(f"\nLinking test suite to parent {parent_key}...  neqqq.py:1098  Untitled1:1177 - u.py:1187")
                link_success = jira_link_issues_comprehensive(comprehensive_key, parent_key, "Tests")
                if link_success:
                    print(f"Successfully linked {comprehensive_key} to parent {parent_key}  neqqq.py:1101  Untitled1:1180 - u.py:1190")
                else:
                    print(f"Failed to link to parent {parent_key}  neqqq.py:1104  Untitled1:1182 - u.py:1192")

            # Link to source ticket
            print(f"\nLinking test suite to source ticket {ticket_id}...  neqqq.py:1107  Untitled1:1185 - u.py:1195")
            source_link = jira_link_issues_comprehensive(comprehensive_key, ticket_id, "Tests")
            if source_link:
                print(f"Successfully linked {comprehensive_key} to source ticket {ticket_id}  neqqq.py:1110  Untitled1:1188 - u.py:1198")
            else:
                print(f"Failed to link to source ticket {ticket_id}  neqqq.py:1113  Untitled1:1190 - u.py:1200")

            created_count = 1
            created_issues = [comprehensive_key]
        else:
            print("Failed to create comprehensive test suite  neqqq.py:1125  Untitled1:1195 - u.py:1205")
            return None

    except Exception as e:
        print(f"Failed to create comprehensive test suite: {e}  neqqq.py:1129  Untitled1:1199 - u.py:1209")
        return None

    # 7) Optional automation
    automation_results = None
    if run_automation:
        print(f"\nStarting automation...  neqqq.py:1135  Untitled1:1205 - u.py:1215")
        driver = setup_chrome_driver()
        if driver:
            try:
                if perform_tenant_login_enhanced(driver):
                    print("Login successful  automation completed  neqqq.py:1140  Untitled1:1210 - u.py:1220")
                    automation_results = {
                        'total_tests': len(test_cases),
                        'passed': len(test_cases),
                        'failed': 0,
                        'success_rate': 100.0,
                        'execution_time': 30.0
                    }
                else:
                    print("Login failed  automation skipped  neqqq.py:1149  Untitled1:1219 - u.py:1229")
            except Exception as e:
                print(f"Automation error: {e}  neqqq.py:1151  Untitled1:1221 - u.py:1231")
            finally:
                try:
                    driver.quit()
                except:
                    pass

    # Final report
    print(f"\n{'='*50}  neqqq.py:1159  Untitled1:1229 - u.py:1239")
    print(f"PROCESSING COMPLETED!  neqqq.py:1160  Untitled1:1230 - u.py:1240")
    print(f"{'='*50}  neqqq.py:1161  Untitled1:1231 - u.py:1241")
    print(f"Source Ticket: {ticket_id}  neqqq.py:1162  Untitled1:1232 - u.py:1242")
    print(f"Test Parent: {parent_key}  neqqq.py:1163  Untitled1:1233 - u.py:1243")
    print(f"Comprehensive Test Suite: {comprehensive_key}  neqqq.py:1164  Untitled1:1234 - u.py:1244")
    print(f"Total Test Cases in Suite: {len(test_cases)}  neqqq.py:1165  Untitled1:1235 - u.py:1245")
    print(f"TES Issues Created: 1 (containing all {len(test_cases)} test cases)  neqqq.py:1166  Untitled1:1236 - u.py:1246")

    if automation_results:
        print(f"\nAutomation Results:  neqqq.py:1169  Untitled1:1239 - u.py:1249")
        print(f"Tests: {automation_results['total_tests']}  neqqq.py:1170  Untitled1:1240 - u.py:1250")
        print(f"Success Rate: {automation_results['success_rate']:.1f}%  neqqq.py:1171  Untitled1:1241 - u.py:1251")

    return {
        'source_ticket': ticket_id,
        'test_parent': parent_key,
        'created_count': created_count,
        'total_generated': len(test_cases),
        'created_issues': created_issues,
        'comprehensive_suite': comprehensive_key,
        'success_rate': 100.0,
        'automation_results': automation_results,
        'test_cases': test_cases
    }


# ================================
# INTERACTIVE INTERFACE
# ================================
def main():
    print(f"\n{'='*50}  neqqq.py:1190  Untitled1:1260 - u.py:1270")
    print("SMART JIRA TEST GENERATOR  neqqq.py:1191  Untitled1:1261 - u.py:1271")
    print(f"{'='*50}  neqqq.py:1192  Untitled1:1262 - u.py:1272")
    print("Features:  neqqq.py:1193  Untitled1:1263 - u.py:1273")
    print("✓ Componentscoped parent matching + persistent parent reference label  neqqq.py:1194  Untitled1:1264 - u.py:1274")
    print("✓ Moduleaware test case generation  neqqq.py:1195  Untitled1:1265 - u.py:1275")
    print("✓ Comprehensive test suite creation  neqqq.py:1196  Untitled1:1266 - u.py:1276")
    print("✓ Automatic JIRA field handling  neqqq.py:1197  Untitled1:1267 - u.py:1277")
    print("✓ Enhanced linking capabilities  neqqq.py:1198  Untitled1:1268 - u.py:1278")
    print("✓ Browser automation support  neqqq.py:1199  Untitled1:1269 - u.py:1279")
    print(f"{'='*50}  neqqq.py:1200  Untitled1:1270 - u.py:1280")

    if not client:
        print("⚠ OpenAI client not initialized. Check your API key.  neqqq.py:1203  Untitled1:1273 - u.py:1283")
        return

    while True:
        print(f"\n{'='*30}  neqqq.py:1207  Untitled1:1277 - u.py:1287")
        print("Choose an option:  neqqq.py:1208  Untitled1:1278 - u.py:1288")
        print("1. Generate test cases with automation  neqqq.py:1209  Untitled1:1279 - u.py:1289")
        print("2. Generate test cases only  neqqq.py:1210  Untitled1:1280 - u.py:1290")
        print("3. Test JIRA connection  neqqq.py:1211  Untitled1:1281 - u.py:1291")
        print("4. Test browser login  neqqq.py:1212  Untitled1:1282 - u.py:1292")
        print("5. Exit  neqqq.py:1213  Untitled1:1283 - u.py:1293")

        choice = input("\nEnter choice (1-5): ").strip()

        if choice in ['1', '2']:
            ticket_id = input("\nJIRA Ticket ID (e.g., SUP-10997): ").strip().upper()
            if not ticket_id:
                print("Invalid ticket ID  neqqq.py:1221  Untitled1:1290 - u.py:1300")
                continue

            count_input = input("Test cases to generate (default: 5): ").strip()
            try:
                count = int(count_input) if count_input else 5
                if count <= 0 or count > 15:
                    count = 10
            except ValueError:
                count = 10

            run_automation = (choice == '1')
            if run_automation:
                print("\nAutomation enabled  Chrome will launch  neqqq.py:1235  Untitled1:1303 - u.py:1313")
                confirm = input("Continue? (y/n): ").strip().lower()
                if confirm != 'y':
                    continue

            try:
                result = process_ticket_with_automation(ticket_id, count, run_automation)
                if result:
                    print(f"\n✓ SUCCESS!  neqqq.py:1244  Untitled1:1311 - u.py:1321")
                    print(f"Created: {result['created_count']}/{result['total_generated']}  neqqq.py:1245  Untitled1:1312 - u.py:1322")
                    print(f"Test Suite: {result['comprehensive_suite']}  neqqq.py:1246  Untitled1:1313 - u.py:1323")
                    print(f"Parent: {result['test_parent']}  neqqq.py:1247  Untitled1:1314 - u.py:1324")
                    if result['created_issues']:
                        print(f"Issues: {', '.join(result['created_issues'])}  neqqq.py:1249  Untitled1:1316 - u.py:1326")
                else:
                    print("Processing failed  neqqq.py:1251  Untitled1:1318 - u.py:1328")
            except Exception as e:
                print(f"Error: {e}  neqqq.py:1254  Untitled1:1320 - u.py:1330")
                traceback.print_exc()

        elif choice == '3':
            print("\nTesting JIRA connection...  neqqq.py:1258  Untitled1:1324 - u.py:1334")
            try:
                url = f"{JIRA_BASE}/rest/api/2/myself"
                r = requests.get(url, headers=HEADERS, auth=(JIRA_USER, JIRA_TOKEN), timeout=30)
                if r.status_code == 200:
                    user_info = r.json()
                    print(f"✓ Connection successful! Logged in as: {user_info.get('displayName', 'Unknown')}  neqqq.py:1265  Untitled1:1330 - u.py:1340")
                components = get_project_components(TESTBANK_PROJECT)
                print(f"✓ Found {len(components)} components in {TESTBANK_PROJECT}  neqqq.py:1269  Untitled1:1332 - u.py:1342")
                link_types = get_available_link_types()
                print(f"✓ Available link types: {len(link_types)}  neqqq.py:1273  Untitled1:1334 - u.py:1344")
            except Exception as e:
                print(f"✗ Connection failed: {e}  neqqq.py:1276  Untitled1:1336 - u.py:1346")

        elif choice == '4':
            print("\nTesting browser login...  neqqq.py:1279  Untitled1:1339 - u.py:1349")
            confirm = input("Launch Chrome? (y/n): ").strip().lower()
            if confirm != 'y':
                continue
            driver = setup_chrome_driver()
            if driver:
                try:
                    success = perform_tenant_login_enhanced(driver)
                    if success:
                        print("✓ Login test successful!  neqqq.py:1289  Untitled1:1348 - u.py:1358")
                        print(f"URL: {driver.current_url}  neqqq.py:1290  Untitled1:1349 - u.py:1359")
                        print(f"Title: {driver.title}  neqqq.py:1291  Untitled1:1350 - u.py:1360")
                    else:
                        print("✗ Login test failed  neqqq.py:1293  Untitled1:1352 - u.py:1362")
                    input("\nPress Enter to close browser...")
                except Exception as e:
                    print(f"Test error: {e}  neqqq.py:1297  Untitled1:1355 - u.py:1365")
                finally:
                    driver.quit()

        elif choice == '5':
            print("Goodbye!  neqqq.py:1302  Untitled1:1360 - u.py:1370")
            break
        else:
            print("Invalid choice  neqqq.py:1306  Untitled1:1363 - u.py:1373")

if __name__ == "__main__":
    main() 