"""Role families: what kind of job this is, and what proof that kind of job looks for."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ProjectTemplate:
    title: str
    description: str          # {slots} filled from the posting's skills
    slots: dict[str, tuple[list[str], str]] = field(default_factory=dict)
    # slot -> (categories to take the top skill from, default text when the posting has none)


@dataclass
class Family:
    name: str
    title: str                 # regex on the job title
    keywords: str              # regex on the whole posting
    default_title: str
    focus: str                 # "building ... " phrase for the summary
    technical: bool
    projects: list[ProjectTemplate]


# Each slot: (categories or exact skill names to take the posting's top pick from, default).
LANG = (["Languages"], "your main language")
DB = (["PostgreSQL", "MySQL", "MongoDB", "Redis", "Cassandra", "DynamoDB", "Elasticsearch",
       "SQL Server", "Oracle Database", "SQLite", "ClickHouse"], "PostgreSQL")
QUEUE = (["Messaging & streaming"], "a message queue")
INFRA = (["AWS", "Google Cloud", "Azure", "Kubernetes", "Docker", "Cloudflare"],
         "a cloud provider")
FE = (["React", "Next.js", "Vue.js", "Angular", "Svelte", "TypeScript"], "React")
MOBILE = (["Swift", "SwiftUI", "Kotlin", "Jetpack Compose", "React Native", "Flutter"],
          "the platform's native toolkit")
DATA_TOOL = (["Apache Airflow", "dbt", "Apache Spark", "Databricks", "Hadoop"],
             "an orchestrator such as Airflow")
WAREHOUSE = (["Snowflake", "BigQuery", "Redshift", "Databricks", "ClickHouse", "PostgreSQL"],
             "a warehouse")
BI = (["Tableau", "Power BI", "Looker", "Excel", "Google Sheets"], "a BI tool")
ML = (["PyTorch", "TensorFlow", "Keras", "scikit-learn", "XGBoost", "Hugging Face", "LangChain"],
      "PyTorch")
OBS = (["Prometheus", "Grafana", "Datadog", "OpenTelemetry", "ELK", "Splunk"],
       "Prometheus and Grafana")
SEC = (["Security & compliance"], "OWASP practices")
TEST = (["pytest", "Jest", "Cypress", "Selenium", "Playwright", "JUnit"], "a test framework")
DESIGN = (["Figma", "Sketch", "Adobe Creative Suite"], "Figma")
MKT = (["Marketing & sales"], "your channel")

FAMILIES: list[Family] = [
    Family(
        "Backend engineering",
        r"back[\s-]?end|server[\s-]side|\bapi\b|distributed systems|golang|\bgo (engineer|developer)|"
        r"java (engineer|developer)|python (engineer|developer)|platform engineer|payments engineer",
        r"\b(apis?|microservices?|distributed|back[\s-]?end|server[\s-]side|databases?|"
        r"throughput|latency|services)\b",
        "Backend Engineer", "building reliable, scalable backend services", True,
        [
            ProjectTemplate(
                "Production-style service, measured",
                "Build and deploy a {lang} service backed by {db} and {queue} on {infra}, with "
                "idempotent APIs, retries, metrics and tracing. Load-test it and publish the "
                "numbers ([N] req/s at p99 < [X] ms) with a one-page design doc on the "
                "trade-offs.",
                {"lang": LANG, "db": DB, "queue": QUEUE, "infra": INFRA}),
            ProjectTemplate(
                "Merged open-source contribution",
                "Land a merged pull request in an open-source {lang} project this team would "
                "recognise (a {db} driver, a {infra} tool, a library from their stack) and "
                "link it from your resume.",
                {"lang": LANG, "db": DB, "infra": INFRA}),
        ]),
    Family(
        "Frontend engineering",
        r"front[\s-]?end|\bui engineer|web (engineer|developer)|react (engineer|developer)|"
        r"javascript (engineer|developer)",
        r"\b(react|css|front[\s-]?end|browser|ui components?|web app|accessibility|design system)\b",
        "Frontend Engineer", "building fast, accessible web interfaces", True,
        [
            ProjectTemplate(
                "Polished, measured web app",
                "Ship a responsive {fe} app with component tests, an accessibility pass "
                "(WCAG AA), and CI deploys. Report its Lighthouse scores and Core Web Vitals "
                "before and after your optimisations.",
                {"fe": FE}),
            ProjectTemplate(
                "Reusable component library",
                "Publish a small, documented component library in {fe} (Storybook, tests, "
                "keyboard support) and use it in a real app.",
                {"fe": FE}),
        ]),
    Family(
        "Full-stack engineering",
        r"full[\s-]?stack",
        r"\b(full[\s-]?stack|front[\s-]?end and back[\s-]?end|end[\s-]to[\s-]end features)\b",
        "Full-Stack Engineer", "shipping end-to-end product features", True,
        [
            ProjectTemplate(
                "End-to-end product, live",
                "Build and launch a small product with a {fe} front end, a {lang} API and {db}, "
                "with auth, payments or another real-world flow, deployed on {infra}. Show real "
                "users or usage numbers ([N] sign-ups, [N] weekly actives).",
                {"fe": FE, "lang": LANG, "db": DB, "infra": INFRA}),
        ]),
    Family(
        "Mobile engineering",
        r"\b(ios|android|mobile)\b",
        r"\b(ios|android|mobile|app store|play store|swift|kotlin|react native|flutter)\b",
        "Mobile Engineer", "building high-quality mobile apps", True,
        [
            ProjectTemplate(
                "Published app with real users",
                "Publish an app built with {mobile} to the App Store or Google Play, with "
                "offline support, crash reporting and analytics. Put downloads, rating and "
                "crash-free rate on your resume.",
                {"mobile": MOBILE}),
        ]),
    Family(
        "Data engineering",
        r"data engineer|analytics engineer|etl|data platform",
        r"\b(pipelines?|etl|elt|data warehouse|airflow|spark|dbt|ingestion|data lake)\b",
        "Data Engineer", "building reliable data pipelines and warehouses", True,
        [
            ProjectTemplate(
                "End-to-end pipeline with data quality checks",
                "Ingest a public dataset daily with {data_tool}, model it in {warehouse}, add "
                "data-quality tests and alerting, and publish a dashboard on top. Report volume "
                "([N] GB/day), run time and freshness.",
                {"data_tool": DATA_TOOL, "warehouse": WAREHOUSE}),
        ]),
    Family(
        "Machine learning & AI engineering",
        r"machine learning|\bml\b|\bai\b|deep learning|applied scientist|research scientist|"
        r"llm|nlp|computer vision|mlops",
        r"\b(models?|training|inference|llms?|machine learning|pytorch|tensorflow|embeddings|"
        r"fine[\s-]tun\w*|evaluation)\b",
        "Machine Learning Engineer", "building and shipping machine learning systems", True,
        [
            ProjectTemplate(
                "Model in production, with an evaluation",
                "Train or fine-tune a model with {ml} on a public dataset, serve it behind an API, "
                "and write up the evaluation: baseline vs. yours ([metric] +[X] points), latency "
                "and cost per 1K requests.",
                {"ml": ML}),
            ProjectTemplate(
                "LLM application with an eval harness",
                "Build a retrieval-augmented assistant over a real document set, with an "
                "automated evaluation set ([N] questions) and the accuracy before and after "
                "each improvement.",
                {}),
        ]),
    Family(
        "Data science",
        r"data scien",
        r"\b(statistic\w*|experiments?|a/b test\w*|causal|regression|hypothes\w*|modeling)\b",
        "Data Scientist", "turning data into decisions with statistics and machine learning", True,
        [
            ProjectTemplate(
                "Analysis that changed a decision",
                "Answer a real business question on a public dataset: frame the hypothesis, run "
                "the analysis or experiment in {lang}, and write a one-page memo with the "
                "recommendation and its expected impact ($[X] or +[X]%).",
                {"lang": LANG}),
        ]),
    Family(
        "Data & business analytics",
        r"(data|business|bi|product|marketing|financial|insights|reporting) analyst|analytics",
        r"\b(dashboards?|reporting|insights|sql|tableau|power bi|looker|excel|kpis?|stakeholders)\b",
        "Data Analyst", "turning data into insight the business acts on", True,
        [
            ProjectTemplate(
                "Dashboard plus a decision memo",
                "Take a public dataset from this company's industry, answer a business question "
                "with SQL, publish a {bi} dashboard, and write a one-page memo with the "
                "recommendation and the impact it would have.",
                {"bi": BI}),
        ]),
    Family(
        "DevOps, SRE & platform",
        r"devops|\bsre\b|site reliability|platform|infrastructure|cloud engineer|"
        r"reliability engineer|systems engineer",
        r"\b(kubernetes|terraform|ci/cd|on[\s-]call|reliability|infrastructure|observability|"
        r"deployments?|uptime|incidents?)\b",
        "Site Reliability Engineer", "running reliable infrastructure and fast delivery pipelines",
        True,
        [
            ProjectTemplate(
                "Infrastructure as code, observable",
                "Stand up a small production-like platform on {infra} with Terraform, a CI/CD "
                "pipeline, and {obs} dashboards and alerts, with SLOs. Document an incident "
                "drill: detection time, mitigation, postmortem.",
                {"infra": INFRA, "obs": OBS}),
        ]),
    Family(
        "Security engineering",
        r"security|appsec|penetration|soc analyst|threat|cyber",
        r"\b(security|vulnerabilit\w*|threat|appsec|owasp|penetration|compliance|iam|encryption)\b",
        "Security Engineer", "finding and fixing security risk before attackers do", True,
        [
            ProjectTemplate(
                "Security review with fixes",
                "Run a security review of an open-source app using {sec}: threat model, "
                "findings by severity, and merged fixes or responsibly disclosed reports.",
                {"sec": SEC}),
        ]),
    Family(
        "QA & test engineering",
        r"\bqa\b|quality|test|sdet",
        r"\b(test (automation|plans?|cases?)|qa|quality|regression|selenium|cypress|playwright)\b",
        "QA Engineer", "catching defects early with automated testing", True,
        [
            ProjectTemplate(
                "Automated test suite in CI",
                "Build an automated test suite for an open-source web app with {test}, running in "
                "CI on every pull request. Report coverage, run time, and the bugs it caught.",
                {"test": TEST}),
        ]),
    Family(
        "Engineering management",
        r"engineering manager|head of engineering|director of engineering|vp,? engineering|"
        r"vp of engineering|cto|manager,? (software|engineering)",
        r"\b(direct reports|people management|hiring|1:1s?|one-on-ones|career growth|"
        r"performance reviews)\b",
        "Engineering Manager", "leading engineering teams that ship", False,
        [
            ProjectTemplate(
                "Leadership portfolio",
                "Prepare two short case studies: a team you grew (hires, promotions, retention) "
                "and a delivery you turned around (cycle time, incidents, roadmap hit rate), "
                "each with before and after numbers.",
                {}),
        ]),
    Family(
        "Product management",
        r"product manager|product owner|\bapm\b|product lead|head of product|"
        r"group product|director of product",
        r"\b(roadmaps?|prds?|discovery|product strategy|customers?|stakeholders|prioriti[sz]\w*)\b",
        "Product Manager", "shipping products customers adopt", False,
        [
            ProjectTemplate(
                "Product teardown with a proposal",
                "Write a teardown of this company's product: a user problem backed by evidence "
                "(reviews, interviews, data), a one-page PRD for the fix, success metrics, and "
                "a launch plan. Link it from your resume.",
                {}),
        ]),
    Family(
        "Product & UX design",
        r"designer|\bux\b|\bui\b|product design|user experience|interaction design",
        r"\b(figma|user research|prototyp\w*|wireframes?|usability|design systems?)\b",
        "Product Designer", "designing products people find easy to use", False,
        [
            ProjectTemplate(
                "Case study with outcomes",
                "Publish two portfolio case studies made in {design}: the problem, research, "
                "iterations, final design, and the measured outcome (task success +[X]%, "
                "support tickets -[X]%).",
                {"design": DESIGN}),
        ]),
    Family(
        "Marketing & growth",
        r"marketing|growth|\bseo\b|content|brand|demand gen|communications",
        r"\b(campaigns?|seo|content|brand|acquisition|conversion|funnel|channels?|marketing)\b",
        "Marketing Manager", "growing pipeline and revenue through marketing", False,
        [
            ProjectTemplate(
                "Campaign with numbers",
                "Run a small real campaign ({mkt}) for a project, a non-profit or your own "
                "product, and report the funnel: reach, CTR, conversion, cost per acquisition.",
                {"mkt": MKT}),
        ]),
    Family(
        "Sales & customer success",
        r"sales|account executive|\bsdr\b|\bbdr\b|account manager|customer success|"
        r"business development|partnerships",
        r"\b(quota|pipeline|deals?|prospect\w*|renewals?|churn|accounts?|revenue|customers)\b",
        "Account Executive", "growing revenue and keeping customers successful", False,
        [
            ProjectTemplate(
                "Territory or account plan",
                "Write a 30-60-90 day plan for this role: target accounts, outreach sequence, "
                "and the pipeline maths to reach quota.",
                {}),
        ]),
    Family(
        "Project & program management",
        r"project manager|program manager|scrum master|delivery manager|\btpm\b",
        r"\b(timelines?|delivery|milestones?|risks?|dependencies|scope|stakeholders|agile|scrum)\b",
        "Program Manager", "delivering complex programs on time", False,
        [
            ProjectTemplate(
                "Delivery case study",
                "Write up a program you ran: scope, plan, risks, how you handled the slip that "
                "happened, and the result (on time, [X]% under budget, [N] teams aligned).",
                {}),
        ]),
    Family(
        "Software engineering",
        r"software|developer|engineer|programmer",
        r"\b(software|code|engineering)\b",
        "Software Engineer", "building and shipping production software", True,
        [
            ProjectTemplate(
                "Shipped project with real usage",
                "Build and deploy a project in {lang} with tests and CI, used by real people. "
                "Put the usage numbers and the hardest technical problem you solved on your "
                "resume.",
                {"lang": LANG}),
        ]),
]

GENERAL = Family(
    "General", r"$^", r"$^", "", "delivering measurable results", False,
    [ProjectTemplate(
        "Proof-of-work sample",
        "Produce one piece of work that mirrors the job's main duty, as a sample you can link: "
        "a plan, an analysis, a deliverable. Note the result it would drive.", {})])


def detect_family(title: str, text: str) -> Family:
    best, best_score = GENERAL, 0.0
    t = title.lower()
    for fam in FAMILIES:
        score = 0.0
        if t and re.search(fam.title, t, re.I):
            score += 12 if fam.name != "Software engineering" else 6
        score += min(len(re.findall(fam.keywords, text, re.I)), 15) * 0.5
        if score > best_score:
            best, best_score = fam, score
    if best_score < 2:
        return GENERAL
    return best
