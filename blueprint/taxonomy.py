"""Skills the offline engine recognises, with the spellings job descriptions use for them.

Each line is ``Canonical|alias|alias``. Matching is case-insensitive, except for short acronyms
(all capitals, up to 5 letters) and the ordinary English words in ``CASE_SENSITIVE``, which must
appear with their capitalisation ("Go" the language, not "go" the verb).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

RAW: dict[str, str] = {
    "Languages": """
        Python
        Go|Golang
        Java
        JavaScript|JS|ES6
        TypeScript
        C++|cpp
        C#
        C
        Rust
        Ruby
        PHP
        Kotlin
        Swift
        Scala
        R
        SQL
        Elixir
        Haskell
        Bash|shell scripting|shell scripts
        Solidity
        Dart
    """,
    "Backend frameworks": """
        Django
        Flask
        FastAPI
        Spring Boot|Spring
        Node.js|NodeJS|Node
        Express.js|Express
        NestJS
        Ruby on Rails|Rails
        Laravel
        .NET|ASP.NET|dotnet
        Gin
        GraphQL
        gRPC
        Protocol Buffers|Protobuf
    """,
    "Frontend": """
        React|React.js|ReactJS
        Next.js|NextJS
        Vue.js|Vue
        Angular
        Svelte
        Redux
        HTML|HTML5
        CSS|CSS3
        Tailwind CSS|Tailwind
        Sass|SCSS
        Webpack
        Vite
        Accessibility|a11y|WCAG
        Responsive design|responsive web design
        Web performance|Core Web Vitals
    """,
    "Mobile": """
        iOS
        Android
        React Native
        Flutter
        SwiftUI
        Jetpack Compose
        Mobile development|mobile apps|mobile applications
    """,
    "Architecture & backend": """
        REST APIs|REST API|RESTful|REST
        Microservices|micro-services|microservice architecture
        Distributed systems|distributed computing
        Event-driven architecture|event-driven|event driven
        API design|designing APIs
        System design|systems design
        Concurrency|concurrent programming|multithreading
        Caching
        Message queues|message queue|message brokers
        WebSockets|WebSocket
        OAuth|OAuth2|OpenID Connect|OIDC
        Domain-driven design|DDD
        Data structures and algorithms|data structures|algorithms
        Object-oriented programming|OOP|object-oriented
        APIs|API|web APIs|public APIs
        SDKs|SDK|client libraries
        Software engineering|software development
        Scalability|scalable systems|high-scale|large-scale systems
        High availability|fault tolerance|fault-tolerant
        Performance optimization|performance tuning|profiling
    """,
    "Databases": """
        PostgreSQL|Postgres
        MySQL
        MongoDB|Mongo
        Redis
        Cassandra
        DynamoDB
        Elasticsearch|OpenSearch
        Snowflake
        BigQuery
        Redshift
        ClickHouse
        SQLite
        Oracle Database|Oracle
        SQL Server|MSSQL
        Neo4j
        NoSQL
        Relational databases|RDBMS|relational database
        Database design|schema design
        Vector databases|vector database|vector store|pgvector|Pinecone
    """,
    "Messaging & streaming": """
        Apache Kafka|Kafka
        RabbitMQ
        Amazon SQS|SQS
        Google Pub/Sub|Pub/Sub
        NATS
        Kinesis
        Stream processing|streaming data|real-time data|Flink
    """,
    "Cloud & infrastructure": """
        AWS|Amazon Web Services
        Google Cloud|GCP|Google Cloud Platform
        Azure|Microsoft Azure
        Docker|containerization|containerized
        Kubernetes|k8s|EKS|GKE|AKS
        Terraform
        Helm
        Ansible
        Serverless|AWS Lambda|Lambda|Cloud Functions
        Linux|Unix
        TCP/IP networking|TCP/IP|DNS|load balancing|load balancers|networking protocols
        Infrastructure as code|IaC
        Cloudflare
    """,
    "DevOps & reliability": """
        CI/CD|continuous integration|continuous delivery|continuous deployment
        GitHub Actions
        GitLab CI
        Jenkins
        ArgoCD|Argo CD
        Git
        Observability|monitoring and alerting|alerting and monitoring|logging and monitoring|monitoring and logging|production monitoring|monitoring tools
        Prometheus
        Grafana
        Datadog
        OpenTelemetry
        ELK|Kibana|Logstash
        Splunk
        Site reliability engineering|SRE|site reliability
        On-call|on call|pager duty|PagerDuty
        Incident response|incident management|postmortems|post-mortems
        SLOs|SLO|SLIs|SLAs|error budgets
    """,
    "Testing & quality": """
        Unit testing|unit tests
        Integration testing|integration tests
        Test-driven development|TDD|test driven
        Test automation|automated testing|automated tests
        End-to-end testing|E2E testing|e2e tests
        pytest
        Jest
        Cypress
        Selenium
        Playwright
        JUnit
        Code review|code reviews
        QA|quality assurance
        Performance testing|load testing
    """,
    "Data engineering": """
        Apache Airflow|Airflow
        dbt
        Apache Spark|Spark|PySpark
        Hadoop
        Databricks
        ETL|ELT
        Data pipelines|data pipeline
        Data modeling|data modelling|dimensional modeling
        Data warehousing|data warehouse|data warehouses
        Data lake|lakehouse
        Data quality
        Data governance
    """,
    "Analytics & BI": """
        Pandas
        NumPy
        Jupyter
        Tableau
        Power BI|PowerBI
        Looker
        Excel|Microsoft Excel
        Google Sheets
        A/B testing|A/B tests|A/B test|AB testing|experimentation|experiments|split testing
        Data-driven decision making|data-driven decisions|data-driven|data-informed|use data to|using data to
        Statistics|statistical analysis|statistical modeling|statistical
        Data visualization|data visualisation
        Dashboards|dashboard|dashboarding
        Data analysis|data analytics|analyzing data|analysing data
        Google Analytics|GA4
        Mixpanel
        Amplitude
        Segment
    """,
    "Machine learning & AI": """
        Machine learning|ML
        Deep learning
        PyTorch
        TensorFlow
        Keras
        scikit-learn|sklearn
        XGBoost|LightGBM
        Natural language processing|NLP
        Computer vision
        Large language models|LLMs|LLM
        Generative AI|GenAI|Gen AI
        Retrieval-augmented generation|RAG
        Prompt engineering
        AI agents|agentic|agent frameworks
        LangChain|LlamaIndex
        Hugging Face|HuggingFace
        MLOps|model deployment|model serving
        Feature engineering
        Recommendation systems|recommender systems|recommendations engine
        Time series|forecasting
    """,
    "Security & compliance": """
        Application security|AppSec|secure coding
        Penetration testing|pentesting|pen testing
        Identity and access management|IAM
        Encryption|cryptography
        SOC 2|SOC2
        ISO 27001
        GDPR
        HIPAA
        PCI DSS|PCI
        Threat modeling|threat modelling
        OWASP
        Zero trust
        SIEM
        Vulnerability management|vulnerability scanning
    """,
    "Product & delivery": """
        Product management
        Product launches|launching products|product launch|launched products
        Product roadmap|roadmaps|roadmap|roadmapping
        Product strategy
        Product requirements|PRDs|PRD|requirements gathering|user stories
        Stakeholder management|stakeholders|stakeholder
        User research|customer research|user interviews|customer interviews|talk to customers|customer discovery
        Go-to-market|GTM
        KPIs|OKRs|success metrics|product metrics
        Agile|Scrum|Kanban|sprint planning
        Prioritization|prioritisation|prioritize|prioritise
        Market research|competitive analysis
        Pricing
        Product analytics
        Project management|program management
        Jira
        Confluence
    """,
    "Design": """
        Figma
        Sketch
        Adobe Creative Suite|Photoshop|Illustrator|Adobe XD
        UX design|UI/UX|UX/UI|user experience|UX
        UI design|user interface design|UI
        Wireframing|wireframes
        Prototyping|prototypes|prototype
        Design systems|design system
        Interaction design
        Usability testing
        Information architecture
    """,
    "Marketing & sales": """
        SEO|search engine optimization
        SEM|paid search|Google Ads
        Content marketing|content strategy
        Email marketing|lifecycle marketing
        Social media marketing|social media
        Paid acquisition|performance marketing|paid social|PPC
        Marketing automation|HubSpot|Marketo
        CRM|Salesforce
        Lead generation|demand generation
        Pipeline management|sales pipeline
        Account management
        Prospecting|cold outreach|outbound
        Copywriting
        Customer success|customer onboarding
        B2B sales|enterprise sales
        Enterprise customers|enterprise clients|enterprise accounts
    """,
    "Leadership & management": """
        People management|direct reports|managing a team|manage a team|people manager
        Hiring|recruiting|interviewing
        Performance management|performance reviews|career development
        Technical leadership|tech lead|technical direction
        Mentoring|mentorship|mentor|coaching|coach
        Strategic planning|long-term strategy
        Budgeting|budget ownership
    """,
    "Soft skills": """
        Communication|communicator|written and verbal|verbal and written|communication skills|communicate|in writing|written communication
        Influence without authority|without authority|influence senior|influence stakeholders|influencing stakeholders
        Cross-functional collaboration|cross-functional|collaborate|collaboration|collaborative
        Ownership|end-to-end|take ownership|own the|autonomy|autonomous|self-starter|self-directed
        Problem solving|problem-solving|solve problems|solving problems
        Attention to detail|detail-oriented|detail oriented
        Adaptability|fast-paced|ambiguity|ambiguous|comfortable with change
        Leadership
        Teamwork|team player
        Critical thinking|analytical skills|analytical thinking
        Presentation skills|presenting|public speaking
        Negotiation
        Customer focus|customer-obsessed|customer obsession|customer empathy|customer-centric
        Time management|multitask|multitasking|juggle
        Documentation|technical writing|design docs|RFCs
    """,
    "Certifications": """
        AWS certification|AWS Certified|AWS Solutions Architect
        Google Cloud certification|Google Cloud Certified
        Azure certification|Azure Certified|AZ-900|AZ-104
        CKA|CKAD|Certified Kubernetes
        PMP
        CISSP
        CompTIA Security+|Security+
        Certified Scrum Master|Scrum Master|CSPO
        CPA
        CFA
    """,
}

# Ordinary English words that only mean the skill when capitalised.
CASE_SENSITIVE = {
    "Go", "R", "C", "Swift", "Rust", "React", "Excel", "Spark", "Oracle", "Express", "Node",
    "Rails", "Ruby", "Angular", "Flask", "Gin", "Jest", "Segment", "Amplitude", "Lambda", "Sketch",
    "Helm", "Snowflake", "Dart", "Elixir", "Svelte", "Solidity", "Airflow", "Cypress", "Selenium",
    "Playwright", "Spring", "Vue", "Mongo",
}

# Ambiguous words that need context to count as the skill: no match when followed by these.
NOT_FOLLOWED_BY = {
    "Go": r"(?:\s+(?:to|above|beyond|live|out|through|back|ahead|over|after)\b|-to\b|-live\b"
          r"|-getter)",
    "C": r"(?:-level|-suite|\s+suite|&)",
    "R": r"(?:&|-)",
    "Spring": r"(?:\s+(?:break|semester|season|of)\b)",
    "React": r"(?:\s+(?:to|quickly|fast)\b)",
    "Express": r"(?:\s+(?:interest|yourself)\b)",
    "Lambda": r"(?:\s+(?:function)?s?\s+of\b)",
    "own the": r"(?:\s+(?:company|equity))",
    "stakeholder": r"(?:s?\s+value)",
    "roadmap": r"(?:\s+for\s+your\s+career)",
    "prototype": r"(?:\s+of\b)",
    "PCI": r"(?:e\b)",
    "Leadership": r"(?:\s+(?:team|group|roles?|positions?)\b)",
    "Software engineering": r"(?:\s+(?:team|manager|org))",
    "API": r"(?:\s+keys?\b)",
}

NOT_PRECEDED_BY = {
    "C": r"(?<!Series )(?<!Objective-)(?<!Level )",
    "R": r"(?<!HR )(?<!Q)",
    "Pricing": r"(?<!competitive )",
    "Hiring": r"(?<!re )(?<!are )(?<!is )(?<!now )(?<!Now )",
}


@dataclass
class SkillDef:
    name: str
    category: str
    aliases: list[str]
    patterns: list[tuple[str, re.Pattern]] = field(default_factory=list)


def _is_case_sensitive(alias: str) -> bool:
    letters = re.sub(r"[^A-Za-z]", "", alias)
    if alias in CASE_SENSITIVE:
        return True
    return bool(letters) and letters.isupper() and len(letters) <= 5


def _compile(alias: str) -> re.Pattern:
    body = re.escape(alias).replace(r"\ ", r"[\s-]+") if " " in alias else re.escape(alias)
    left = r"(?<![A-Za-z0-9_.@])"
    # Plurals and possessives: "APIs", "LLMs", "dashboards", "Kubernetes'".
    suffix = r"(?:'?s)?" if alias[-1].isalnum() and len(alias) > 1 else ""
    right = r"(?![A-Za-z0-9_+#])"
    pre = NOT_PRECEDED_BY.get(alias, "")
    post = f"(?!{NOT_FOLLOWED_BY[alias]})" if alias in NOT_FOLLOWED_BY else ""
    flags = 0 if _is_case_sensitive(alias) else re.IGNORECASE
    return re.compile(f"{pre}{left}{body}{suffix}{right}{post}", flags)


def _build() -> list[SkillDef]:
    defs: list[SkillDef] = []
    for category, block in RAW.items():
        for line in block.strip().splitlines():
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if not parts:
                continue
            sd = SkillDef(name=parts[0], category=category, aliases=parts)
            sd.patterns = [(a, _compile(a)) for a in parts]
            defs.append(sd)
    return defs


SKILLS: list[SkillDef] = _build()
BY_NAME: dict[str, SkillDef] = {s.name.lower(): s for s in SKILLS}
SOFT_CATEGORIES = {"Soft skills", "Leadership & management"}
TECH_CATEGORIES = {
    "Languages", "Backend frameworks", "Frontend", "Mobile", "Architecture & backend", "Databases",
    "Messaging & streaming", "Cloud & infrastructure", "DevOps & reliability", "Testing & quality",
    "Data engineering", "Analytics & BI", "Machine learning & AI", "Security & compliance",
}


@dataclass
class Match:
    skill: SkillDef
    start: int
    end: int
    surface: str


def find_matches(text: str) -> list[Match]:
    """Every skill mention in ``text``, longest match first when two spellings overlap.

    "React Native" wins over "React", "Spring Boot" over "Spring", "SQL Server" over "SQL".
    """
    found: list[Match] = []
    for sd in SKILLS:
        for _alias, pat in sd.patterns:
            for m in pat.finditer(text):
                found.append(Match(sd, m.start(), m.end(), m.group(0)))
    found.sort(key=lambda m: (-(m.end - m.start), m.start))
    taken: list[tuple[int, int]] = []
    kept: list[Match] = []
    for m in found:
        if any(m.start < e and s < m.end for s, e in taken):
            continue
        taken.append((m.start, m.end))
        kept.append(m)
    kept.sort(key=lambda m: m.start)
    return kept


def canonical(name: str) -> str:
    """The taxonomy's name for a skill, recognising its aliases; the input when unknown."""
    key = name.strip().lower()
    if key in BY_NAME:
        return BY_NAME[key].name
    for sd in SKILLS:
        if any(a.lower() == key for a in sd.aliases):
            return sd.name
    return name.strip()


def category_of(name: str) -> str | None:
    sd = BY_NAME.get(canonical(name).lower())
    return sd.category if sd else None


DOMAINS: dict[str, str] = {
    "Fintech & payments": r"\b(fintech|payments?|banking|lending|credit cards?|neobank|trading|"
                          r"wealth management|financial services)\b",
    "Healthcare": r"\b(healthcare|health tech|healthtech|clinical|patients?|hospitals?|medical|"
                  r"telehealth|EHR|EMR)\b",
    "E-commerce & retail": r"\b(e-?commerce|retail|online store|checkout|merchants?|shopping)\b",
    "Advertising & marketing tech": r"\b(ad ?tech|advertising|ad platform|programmatic)\b",
    "Education": r"\b(ed ?tech|education|learners|students|e-learning)\b",
    "Gaming": r"\b(gaming|video games?|game studio|game engine)\b",
    "Logistics & supply chain": r"\b(logistics|supply chain|shipping|fleet|warehousing|"
                                r"last-mile|delivery network)\b",
    "Cybersecurity": r"\b(cyber ?security|security products?|threat detection|SOC team)\b",
    "Crypto & web3": r"\b(crypto(?:currency)?|blockchain|web3|DeFi|smart contracts?)\b",
    "Insurance": r"\b(insurance|insurtech|underwriting|claims processing)\b",
    "Media & streaming": r"\b(media|streaming platform|video streaming|content platform|"
                         r"publishing)\b",
    "Travel & hospitality": r"\b(travel|hospitality|bookings?|hotels?|airlines?)\b",
    "Marketplaces": r"\b(marketplaces?|two-sided)\b",
    "Developer tools": r"\b(developer tools|devtools|developer platform|developer experience|"
                       r"SDKs?)\b",
    "AI products": r"\b(AI-native|AI products?|AI platform|foundation models?|AI-powered)\b",
    "Climate & energy": r"\b(climate|energy|renewables?|solar|carbon|sustainability)\b",
    "Automotive & mobility": r"\b(automotive|vehicles?|mobility|autonomous driving|EV)\b",
    "Telecom": r"\b(telecom|telecommunications|5G|network operators?)\b",
    "Government & public sector": r"\b(government|public sector|federal|civic)\b",
    # Generic, so last: a more specific domain leads the headline when there is one.
    "SaaS / B2B": r"\b(SaaS|B2B|enterprise software|enterprise customers)\b",
}
DOMAIN_PATTERNS = {k: re.compile(v, re.IGNORECASE) for k, v in DOMAINS.items()}
