"""
resume_parser.py
Extracts structured data from a student's PDF resume using pdfplumber + regex.
Returns a dict with: name, email, phone, cgpa, skills, department, experience
"""

import re
import pdfplumber

# ── Comprehensive skills vocabulary ────────────────────────────────────────────
SKILLS = [
    # Languages
    'Python', 'Java', 'JavaScript', 'TypeScript', 'C', 'C++', 'C#', 'Go',
    'Rust', 'Ruby', 'PHP', 'Swift', 'Kotlin', 'R', 'MATLAB', 'Scala',
    'Perl', 'Bash', 'Shell', 'PowerShell', 'Dart', 'Lua',

    # Web front-end
    'HTML', 'CSS', 'React', 'Angular', 'Vue', 'Next.js', 'Nuxt.js',
    'Svelte', 'Bootstrap', 'Tailwind', 'jQuery', 'Redux', 'Webpack',

    # Web back-end / frameworks
    'Django', 'Flask', 'FastAPI', 'Express', 'Node.js', 'Spring',
    'Spring Boot', 'Laravel', 'Rails', 'ASP.NET', 'Hibernate',
    'Gin', 'Echo',

    # Databases
    'SQL', 'MySQL', 'PostgreSQL', 'SQLite', 'MongoDB', 'Redis',
    'Cassandra', 'DynamoDB', 'Elasticsearch', 'Firebase',
    'Oracle', 'MS SQL Server', 'MariaDB',

    # Cloud & DevOps
    'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Terraform',
    'Ansible', 'Jenkins', 'GitHub Actions', 'CircleCI', 'Linux',
    'Nginx', 'Apache', 'CI/CD',

    # Data & ML
    'Machine Learning', 'Deep Learning', 'TensorFlow', 'PyTorch',
    'Keras', 'Scikit-learn', 'Pandas', 'NumPy', 'Matplotlib',
    'Seaborn', 'OpenCV', 'NLP', 'Computer Vision', 'LangChain',
    'Hugging Face', 'Spark', 'Hadoop', 'Kafka', 'Airflow',
    'Tableau', 'Power BI', 'Excel',

    # APIs & Architecture
    'REST API', 'GraphQL', 'gRPC', 'Microservices', 'WebSocket',
    'OAuth', 'JWT',

    # Version control & tools
    'Git', 'GitHub', 'GitLab', 'Bitbucket', 'Jira', 'Confluence',
    'Postman', 'VS Code', 'IntelliJ', 'Eclipse',

    # Methodologies
    'Agile', 'Scrum', 'Kanban', 'TDD', 'BDD',

    # Networking
    'TCP/IP', 'HTTP', 'DNS', 'VPN', 'Firewall', 'Wireshark',

    # Mobile
    'Android', 'iOS', 'React Native', 'Flutter', 'Xamarin',

    # Other
    'Blockchain', 'Solidity', 'Unity', 'Unreal Engine', 'Arduino',
    'Raspberry Pi', 'IoT',
]

# Build a lowercase lookup for fast matching
_SKILLS_LOWER = {s.lower(): s for s in SKILLS}

# ── Department / stream keywords ───────────────────────────────────────────────
DEPT_KEYWORDS = {
    'CSE':  ['computer science', 'cse', 'b.tech cse', 'b.e. cse'],
    'ECE':  ['electronics', 'ece', 'e&c', 'e & c'],
    'IT':   ['information technology', ' it '],
    'EEE':  ['electrical', 'eee', 'e&ee'],
    'ME':   ['mechanical', ' me ', 'mech'],
    'CE':   ['civil', ' ce ', 'civil engineering'],
    'Chem': ['chemical', 'chem'],
    'Data Science': ['data science', 'ds'],
    'AI/ML': ['artificial intelligence', 'machine learning', ' ai '],
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_text(path: str) -> str:
    """Extract all text from a PDF."""
    text = ''
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + '\n'
    except Exception:
        pass
    return text


def _extract_email(text: str) -> str:
    m = re.search(r'[\w.+\-]+@[\w\-]+\.[\w.]+', text)
    return m.group(0).strip() if m else ''


def _extract_phone(text: str) -> str:
    # Match common Indian & international formats
    patterns = [
        r'(?:\+91[\s\-]?)?[789]\d{9}',           # Indian mobile
        r'\+?\d{1,3}[\s\-]?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{4}',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return re.sub(r'\s+', ' ', m.group(0)).strip()
    return ''


def _extract_cgpa(text: str) -> str:
    patterns = [
        r'(?:CGPA|GPA|CPI|SGPA)[:\s/]*([0-9]\.[0-9]{1,2})',
        r'([0-9]\.[0-9]{1,2})\s*(?:/\s*(?:10|4))',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            val = float(m.group(1))
            # Normalise 4.0 scale → 10.0 scale
            if val <= 4.0:
                val = round(val * 2.5, 2)
            if 0 < val <= 10:
                return str(val)
    return ''


def _extract_skills(text: str) -> list:
    text_lower = text.lower()
    found = []
    for skill_lower, skill_display in _SKILLS_LOWER.items():
        # Use word-boundary aware search
        pattern = r'(?<![a-z])' + re.escape(skill_lower) + r'(?![a-z])'
        if re.search(pattern, text_lower):
            found.append(skill_display)
    # Deduplicate keeping insertion order
    seen = set()
    result = []
    for s in found:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result


def _extract_name(text: str) -> str:
    """
    Try to extract candidate name from the first 5 non-empty lines.
    A name is: 2-4 words, only letters and spaces, no numbers/email/@.
    """
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for line in lines[:8]:
        # Skip lines that look like headings, emails, URLs, phone numbers
        if re.search(r'[@\d/:\\]', line):
            continue
        if re.search(r'(?i)(resume|curriculum|email|phone|address|objective|summary|linkedin|github)', line):
            continue
        words = line.split()
        if 2 <= len(words) <= 4 and all(re.match(r"^[A-Za-z.'\-]+$", w) for w in words):
            return line.title()
    return ''


def _extract_department(text: str) -> str:
    text_lower = text.lower()
    for dept, keywords in DEPT_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return dept
    return ''


def _extract_experience(text: str) -> str:
    """Return experience string like '1 year' or 'Fresher'."""
    m = re.search(r'(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\s*(?:of)?\s*(?:experience|exp)',
                  text, re.IGNORECASE)
    if m:
        yrs = float(m.group(1))
        return f"{int(yrs)} year{'s' if yrs != 1 else ''}"

    if re.search(r'(?i)(fresher|fresh graduate|entry[- ]level)', text):
        return 'Fresher'
    return ''


# ── Public API ─────────────────────────────────────────────────────────────────

def parse_resume(pdf_path: str) -> dict:
    """
    Parse a PDF resume and return a dict with extracted fields.
    All values are strings; `skills` is a list.
    """
    text = _extract_text(pdf_path)
    if not text.strip():
        return {'error': 'Could not extract text from PDF. The file may be scanned/image-based.'}

    return {
        'name':       _extract_name(text),
        'email':      _extract_email(text),
        'phone':      _extract_phone(text),
        'cgpa':       _extract_cgpa(text),
        'skills':     _extract_skills(text),
        'department': _extract_department(text),
        'experience': _extract_experience(text),
        'raw_length': len(text),   # useful for debugging
    }
