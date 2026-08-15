"""
Generates data/corpus.json: a 1000-document, multi-domain corpus, replacing the
original 100-document job-postings-only corpus. Content is template-generated
(not hand-written per document) so that 1000 items with 300-500 words each is
actually tractable, while still producing varied, readable, domain-flavored text
rather than word salad.

Run: python3 scripts/generate_corpus.py   (from the search-engine/ directory)
"""
import json
import random
from pathlib import Path

DOCS_PER_DOMAIN = 100
MIN_WORDS = 300
MAX_WORDS = 500

# Master sentence skeletons, domain-agnostic. Each is filled with phrases pulled
# from that document's domain-specific phrase bank (see DOMAINS below).
SENTENCE_TEMPLATES = [
    "{entity} is widely recognized for its work in {subject}, with particular attention to {focus}.",
    "This typically involves {activity}, which requires strong {skill} and careful attention to detail.",
    "One major advantage is {benefit}, a factor that has drawn interest well beyond the immediate field.",
    "At the same time, {challenge} remains a persistent concern that professionals must navigate carefully.",
    "Recent developments, including {development}, have begun to reshape expectations around {subject2}.",
    "Many experts stress the importance of {importance}, arguing that it has a direct effect on {outcome}.",
    "In {location}, these patterns are especially visible, shaping how local organizations approach {subject}.",
    "Looking forward, {trend} is expected to play a growing role in how this area develops.",
    "{entity} has continued to adapt, balancing {focus} with the practical demands of {activity}.",
    "Observers note that {benefit} does not come without tradeoffs, since {challenge} often complicates decision-making.",
    "The relationship between {subject} and {subject2} has become a common topic of discussion among specialists.",
    "As a result, {development} is often cited as a turning point for how {outcome} is measured.",
    "For newcomers, building {skill} is considered essential before tackling more complex aspects of {subject}.",
    "Ultimately, {closing}, a conclusion echoed across much of the recent commentary on {subject}.",
]

DOMAINS = {
    "tech": {
        "entities": ["Google", "Razorpay", "Flipkart", "Juspay", "Atlassian", "Meesho", "Samsung",
                     "Microsoft", "Amazon", "Zomato", "Swiggy", "PhonePe", "Paytm", "Infosys", "TCS"],
        "topics": ["Software Engineer", "Backend Engineer", "Data Engineer", "DevOps Engineer",
                   "Machine Learning Engineer", "Site Reliability Engineer", "Frontend Engineer",
                   "Full Stack Developer", "Cloud Architect", "QA Engineer", "Security Engineer",
                   "Mobile Developer", "Data Scientist", "Product Engineer", "Platform Engineer"],
        "title_fmt": "{topic} at {entity}",
        "phrases": {
            "subject": ["backend systems and distributed infrastructure", "cloud-native application development",
                        "machine learning pipelines", "large-scale data processing", "site reliability and observability"],
            "subject2": ["software architecture", "system design", "API development",
                         "container orchestration", "data engineering practices"],
            "focus": ["writing clean, maintainable code", "building scalable services",
                      "improving system reliability", "optimizing performance under load",
                      "automating deployment pipelines"],
            "activity": ["designing REST APIs", "debugging production incidents", "reviewing pull requests",
                         "writing unit and integration tests", "provisioning cloud infrastructure"],
            "skill": ["proficiency in Python and Java", "a solid grasp of data structures and algorithms",
                      "hands-on experience with Docker and Kubernetes",
                      "strong communication with cross-functional teams", "familiarity with CI/CD pipelines"],
            "benefit": ["faster deployment cycles", "fewer production incidents", "improved developer productivity",
                        "better system observability", "reduced infrastructure costs"],
            "challenge": ["balancing technical debt with new feature work", "scaling systems under unpredictable traffic",
                          "maintaining legacy codebases", "coordinating across multiple time zones",
                          "keeping up with rapidly changing tools"],
            "development": ["the adoption of container orchestration", "the shift toward microservices",
                            "the rise of AI-assisted coding tools", "increased investment in observability tooling",
                            "the move to cloud-native architectures"],
            "importance": ["writing thorough documentation", "maintaining test coverage",
                           "conducting regular code reviews", "monitoring system health continuously",
                           "practicing secure coding habits"],
            "outcome": ["system uptime", "developer velocity", "customer satisfaction",
                        "engineering costs", "product reliability"],
            "trend": ["greater automation in software delivery", "wider adoption of machine learning in production systems",
                      "more emphasis on platform engineering", "increased use of serverless architectures",
                      "a stronger focus on developer experience"],
            "closing": ["engineering teams that invest early in good practices tend to scale more smoothly",
                        "strong technical foundations pay off as products grow",
                        "the best teams treat reliability as a feature, not an afterthought",
                        "hiring for both skill and curiosity tends to produce stronger teams",
                        "clear ownership boundaries reduce coordination overhead"],
        },
    },
    "healthcare": {
        "entities": ["Apollo Hospitals", "Fortis Healthcare", "Mayo Clinic", "Cleveland Clinic", "Max Healthcare",
                     "Manipal Hospitals", "AIIMS", "Johns Hopkins Medicine", "Narayana Health", "Practo",
                     "Medanta", "Cigna", "UnitedHealth Group", "Pfizer", "Moderna"],
        "topics": ["Cardiology", "Pediatrics", "Oncology", "Telemedicine", "Mental Health", "Preventive Care",
                   "Emergency Medicine", "Physical Therapy", "Nutrition Counseling", "Maternal Health",
                   "Diabetes Management", "Vaccination", "Geriatric Care", "Surgical Innovation",
                   "Chronic Disease Management"],
        "title_fmt": "{entity} Expands {topic} Services in {location}",
        "phrases": {
            "subject": ["patient-centered clinical care", "early disease detection", "chronic condition management",
                        "preventive health screenings", "personalized treatment planning"],
            "subject2": ["telehealth adoption", "medical research funding", "hospital staffing",
                         "patient data privacy", "insurance coverage policy"],
            "focus": ["improving patient outcomes", "reducing wait times", "expanding access to specialists",
                      "lowering treatment costs", "strengthening follow-up care"],
            "activity": ["coordinating between specialists", "reviewing patient histories", "running diagnostic tests",
                         "developing treatment plans", "training clinical staff"],
            "skill": ["careful clinical judgment", "strong communication with patients and families",
                      "attention to evolving treatment guidelines", "comfort with electronic health record systems",
                      "collaboration across care teams"],
            "benefit": ["faster diagnosis times", "better long-term patient outcomes",
                        "reduced hospital readmission rates", "more convenient access to care",
                        "lower overall treatment costs"],
            "challenge": ["staffing shortages in certain specialties", "rising costs of specialized equipment",
                          "navigating complex insurance requirements", "ensuring equitable access across regions",
                          "keeping pace with new treatment guidelines"],
            "development": ["the wider adoption of telemedicine", "advances in early-detection screening",
                            "new data-sharing standards between providers", "AI-assisted diagnostic tools",
                            "expanded outpatient care models"],
            "importance": ["clear communication with patients", "consistent follow-up after treatment",
                           "accurate and timely documentation", "respecting patient privacy",
                           "coordinating care across providers"],
            "outcome": ["patient recovery times", "overall care quality", "hospital readmission rates",
                        "patient satisfaction scores", "long-term health outcomes"],
            "trend": ["greater use of remote patient monitoring", "wider adoption of preventive screening programs",
                      "more personalized treatment approaches", "expanded telehealth coverage",
                      "closer integration between primary and specialist care"],
            "closing": ["health systems that invest in prevention tend to see better long-term outcomes",
                        "coordinated care remains one of the strongest predictors of patient recovery",
                        "patients consistently report satisfaction when communication is clear and timely",
                        "investment in staff training continues to pay dividends in care quality",
                        "access remains one of the biggest determinants of health outcomes"],
        },
    },
    "finance": {
        "entities": ["Goldman Sachs", "JPMorgan Chase", "HDFC Bank", "ICICI Bank", "Axis Bank", "Morgan Stanley",
                     "Vanguard", "BlackRock", "Paytm", "Razorpay", "Visa", "Mastercard", "Deutsche Bank",
                     "Fidelity", "Zerodha"],
        "topics": ["Retail Banking", "Investment Strategy", "Digital Payments", "Wealth Management",
                   "Risk Assessment", "Cryptocurrency Regulation", "Mortgage Lending", "Corporate Finance",
                   "Insurance Underwriting", "Financial Planning", "Stock Market Analysis", "Credit Scoring",
                   "Mobile Banking", "Fraud Prevention", "Retirement Savings"],
        "title_fmt": "{entity} Reports on {topic} Trends in {location}",
        "phrases": {
            "subject": ["portfolio diversification strategies", "consumer lending practices",
                        "market volatility analysis", "regulatory compliance", "digital payment adoption"],
            "subject2": ["interest rate policy", "credit risk modeling", "financial technology innovation",
                         "capital markets activity", "retail banking competition"],
            "focus": ["minimizing investment risk", "improving customer trust", "streamlining loan approvals",
                      "strengthening fraud detection", "expanding financial access"],
            "activity": ["analyzing market trends", "assessing borrower creditworthiness", "auditing transaction records",
                         "modeling portfolio risk", "advising clients on investment options"],
            "skill": ["strong quantitative analysis", "attention to regulatory detail", "clear client communication",
                      "careful risk assessment", "familiarity with financial modeling tools"],
            "benefit": ["more stable investment returns", "faster loan processing times", "reduced fraud losses",
                        "improved customer retention", "better-informed financial decisions"],
            "challenge": ["navigating shifting interest rates", "complying with evolving regulations",
                          "managing exposure to market volatility", "detecting increasingly sophisticated fraud",
                          "balancing growth with risk management"],
            "development": ["the rise of digital-only banks", "broader adoption of mobile payments",
                            "new open banking regulations", "increased use of AI in credit scoring",
                            "growing interest in sustainable investing"],
            "importance": ["transparent fee structures", "accurate risk disclosure", "consistent regulatory compliance",
                           "timely customer communication", "rigorous internal auditing"],
            "outcome": ["portfolio performance", "customer trust", "loan default rates",
                        "regulatory standing", "overall financial stability"],
            "trend": ["continued growth in digital payments", "greater demand for personalized financial advice",
                      "tighter regulatory oversight of fintech", "wider adoption of automated investing tools",
                      "increased focus on financial inclusion"],
            "closing": ["firms that prioritize transparency tend to build stronger long-term client relationships",
                        "disciplined risk management remains the foundation of stable returns",
                        "customer trust continues to be the most valuable asset in financial services",
                        "those adapting early to digital channels are gaining a competitive edge",
                        "regulatory compliance is increasingly viewed as a strategic advantage rather than a burden"],
        },
    },
    "education": {
        "entities": ["Harvard University", "Stanford University", "MIT", "Coursera", "Byju's", "Khan Academy",
                     "University of Delhi", "Oxford University", "Cambridge University", "Udemy", "edX",
                     "National Institute of Education", "Pearson", "IIT Bombay", "University of California"],
        "topics": ["STEM Education", "Online Learning", "Vocational Training", "Early Childhood Education",
                   "Special Education", "Higher Education Access", "Teacher Training", "Curriculum Design",
                   "Adult Literacy", "Language Learning", "Educational Technology", "Scholarship Programs",
                   "Remote Learning", "Skill Development", "Academic Research"],
        "title_fmt": "{entity} Launches New {topic} Program in {location}",
        "phrases": {
            "subject": ["student engagement strategies", "curriculum modernization", "personalized learning paths",
                        "classroom technology integration", "teacher professional development"],
            "subject2": ["assessment methods", "remote learning tools", "student mental health support",
                         "funding for public education", "access to higher education"],
            "focus": ["improving learning outcomes", "closing achievement gaps", "increasing student engagement",
                      "supporting teacher development", "expanding access to quality education"],
            "activity": ["designing lesson plans", "training new teachers", "evaluating student progress",
                         "developing online course material", "mentoring first-generation students"],
            "skill": ["patience and adaptability", "strong subject-matter expertise",
                      "the ability to explain complex ideas simply", "empathy for diverse learning needs",
                      "comfort with new educational technology"],
            "benefit": ["higher student retention rates", "improved standardized test scores",
                        "greater student confidence", "more equitable access to resources",
                        "stronger long-term academic outcomes"],
            "challenge": ["limited funding for public schools", "unequal access to technology", "large class sizes",
                          "teacher burnout and turnover", "keeping curricula relevant to a changing job market"],
            "development": ["the growth of online and hybrid learning", "new adaptive learning software",
                            "expanded scholarship and financial aid programs", "greater emphasis on vocational training",
                            "increased use of data to guide instruction"],
            "importance": ["individualized attention to struggling students", "clear and consistent feedback",
                           "strong family and community involvement", "ongoing teacher training",
                           "equitable access to learning materials"],
            "outcome": ["graduation rates", "standardized test performance", "long-term career outcomes",
                        "student well-being", "overall literacy rates"],
            "trend": ["wider adoption of blended learning models", "growing investment in early childhood education",
                      "more personalized, technology-assisted instruction", "expanded access to online courses",
                      "greater focus on practical, job-ready skills"],
            "closing": ["schools that invest early in strong foundations tend to see the biggest long-term gains",
                        "access remains one of the most persistent challenges in education systems worldwide",
                        "teacher quality continues to be one of the strongest predictors of student success",
                        "technology can meaningfully support learning when paired with strong teaching",
                        "closing opportunity gaps requires sustained, long-term investment rather than short-term fixes"],
        },
    },
    "sports": {
        "entities": ["Manchester United", "Real Madrid", "Los Angeles Lakers", "Mumbai Indians",
                     "Chennai Super Kings", "FC Barcelona", "Golden State Warriors", "Indian Cricket Team",
                     "New York Yankees", "Liverpool FC", "Chicago Bulls", "Australian Cricket Team",
                     "Dallas Cowboys", "Bayern Munich", "Team India"],
        "topics": ["Championship Final", "League Title Race", "Transfer Window", "Injury Update", "Season Opener",
                   "Playoff Push", "Coaching Change", "Youth Academy Development", "Fan Engagement",
                   "Stadium Renovation", "Player Contract Renewal", "Rivalry Match", "Training Camp",
                   "World Cup Qualifier", "Season Review"],
        "title_fmt": "{entity} Prepares for {topic} in {location}",
        "phrases": {
            "subject": ["squad depth and player rotation", "tactical preparation", "fitness and conditioning programs",
                        "team chemistry building", "match-day strategy"],
            "subject2": ["player transfer negotiations", "fan engagement initiatives", "youth talent development",
                         "coaching staff decisions", "stadium and facility upgrades"],
            "focus": ["improving overall team performance", "maintaining player fitness", "strengthening squad depth",
                      "building consistent form", "maximizing home advantage"],
            "activity": ["analyzing opponent tactics", "running high-intensity training sessions",
                         "reviewing match footage", "managing player workloads", "negotiating transfer deals"],
            "skill": ["tactical discipline", "physical conditioning", "mental resilience under pressure",
                      "clear communication on the field", "adaptability to different playing styles"],
            "benefit": ["improved league standings", "stronger fan support", "increased ticket and merchandise sales",
                        "better player morale", "a more balanced squad"],
            "challenge": ["managing player injuries", "dealing with a congested fixture schedule",
                          "handling pressure from fans and media", "integrating new signings quickly",
                          "maintaining form across a long season"],
            "development": ["the introduction of new training technology", "increased use of data analytics in coaching",
                            "a wave of high-profile transfers", "expanded youth academy investment",
                            "new rules affecting match strategy"],
            "importance": ["consistent training discipline", "clear communication between coaches and players",
                           "careful management of player fitness", "strong locker-room culture",
                           "adapting strategy to each opponent"],
            "outcome": ["final league standings", "player fitness levels", "fan attendance", "team morale",
                        "overall season performance"],
            "trend": ["greater reliance on data-driven coaching decisions", "increased investment in youth development",
                      "growing global fan engagement through digital platforms",
                      "more emphasis on player wellness and recovery", "tighter competition across major leagues"],
            "closing": ["teams that manage fitness and rotation well tend to perform better over a long season",
                        "strong squad depth continues to separate title contenders from the rest of the field",
                        "fan support remains a significant factor in home performance",
                        "consistency, more than individual brilliance, tends to decide long campaigns",
                        "the margins between top teams continue to narrow year over year"],
        },
    },
    "entertainment": {
        "entities": ["Netflix", "Warner Bros", "Disney", "Marvel Studios", "Universal Pictures", "HBO",
                     "Sony Pictures", "A24", "Paramount Pictures", "Amazon Studios", "BBC",
                     "Bollywood Productions", "Yash Raj Films", "Pixar", "Sony Music"],
        "topics": ["Film Release", "Streaming Series", "Music Album", "Awards Season", "Box Office Performance",
                   "Celebrity Interview", "Documentary Premiere", "Animation Project", "Concert Tour",
                   "Television Reboot", "Soundtrack Release", "Casting Announcement", "Film Festival",
                   "Video Game Adaptation", "Comedy Special"],
        "title_fmt": "{entity} Announces New {topic} in {location}",
        "phrases": {
            "subject": ["storytelling and character development", "audience engagement across platforms",
                        "production scheduling", "visual effects and design", "marketing and promotional strategy"],
            "subject2": ["streaming platform competition", "box office performance", "critical reception",
                         "fan community engagement", "international distribution"],
            "focus": ["captivating a wider audience", "staying true to the original story",
                      "pushing creative boundaries", "maximizing production quality", "expanding global reach"],
            "activity": ["scouting filming locations", "coordinating with visual effects teams", "conducting casting sessions",
                         "editing and post-production work", "promoting the project across media"],
            "skill": ["strong creative vision", "careful project management", "collaboration across large production teams",
                      "adaptability to shifting schedules", "clear communication with studios and networks"],
            "benefit": ["stronger audience engagement", "higher box office or streaming numbers", "greater critical acclaim",
                        "expanded international reach", "a loyal long-term fan base"],
            "challenge": ["managing tight production schedules", "balancing creative vision with studio expectations",
                          "competing for audience attention in a crowded market", "controlling rising production costs",
                          "adapting to shifting viewer habits"],
            "development": ["the rise of streaming platforms", "increased use of visual effects technology",
                            "new approaches to interactive storytelling", "growing international co-productions",
                            "shifting release strategies between theaters and streaming"],
            "importance": ["staying authentic to the source material", "clear communication with the creative team",
                           "careful audience research", "consistent quality across a franchise",
                           "respecting production timelines"],
            "outcome": ["box office or streaming performance", "critical reviews", "audience satisfaction",
                        "franchise longevity", "awards recognition"],
            "trend": ["continued growth of streaming over traditional theatrical release",
                      "more interactive and immersive entertainment formats", "greater demand for diverse storytelling",
                      "increased international collaboration in production", "shorter gaps between franchise installments"],
            "closing": ["projects that stay true to their core audience tend to perform best over time",
                        "strong storytelling continues to matter more than spectacle alone",
                        "the entertainment industry keeps adapting quickly to changing viewer habits",
                        "franchises that respect their existing fan base tend to sustain long-term success",
                        "production quality increasingly competes directly with originality for audience attention"],
        },
    },
    "food": {
        "entities": ["Zomato", "Swiggy", "Gordon Ramsay Restaurants", "The Culinary Institute", "Nobu", "Taco Bell",
                     "Domino's", "Starbucks", "MasterChef Productions", "Blue Bottle Coffee", "Olive Garden",
                     "Local Bistro Group", "Farm to Table Co", "Whole Foods", "Michelin Guide"],
        "topics": ["Seasonal Recipe", "Restaurant Opening", "Culinary Technique", "Food Safety Standards",
                   "Sustainable Sourcing", "Wine Pairing", "Street Food Culture", "Baking Innovation",
                   "Plant-Based Menu", "Food Festival", "Chef Interview", "Kitchen Equipment Review",
                   "Regional Cuisine", "Coffee Culture", "Dessert Trend"],
        "title_fmt": "{topic}: Insights from {entity} in {location}",
        "phrases": {
            "subject": ["ingredient sourcing and quality", "flavor balance and technique", "kitchen efficiency",
                        "menu design", "seasonal ingredient availability"],
            "subject2": ["food safety practices", "sustainable sourcing decisions", "customer dining preferences",
                         "kitchen staffing", "supply chain logistics"],
            "focus": ["improving flavor consistency", "supporting local farmers and suppliers", "reducing food waste",
                      "enhancing the overall dining experience", "maintaining strict food safety standards"],
            "activity": ["testing new recipes", "sourcing seasonal ingredients", "training kitchen staff",
                         "plating and presentation", "managing inventory and food costs"],
            "skill": ["precise knife and cooking technique", "a refined sense of flavor balance",
                      "efficient time management under pressure", "creativity within recipe constraints",
                      "strong communication across the kitchen team"],
            "benefit": ["more consistent dish quality", "stronger customer loyalty", "reduced food waste and costs",
                        "a more memorable dining experience", "closer relationships with local suppliers"],
            "challenge": ["managing rising ingredient costs", "maintaining consistency across busy service periods",
                          "sourcing quality ingredients year-round", "staffing shortages in professional kitchens",
                          "adapting menus to shifting dietary trends"],
            "development": ["growing interest in plant-based menus", "increased demand for sustainably sourced ingredients",
                            "new kitchen technology improving efficiency", "the rise of delivery-first restaurant concepts",
                            "greater transparency around ingredient sourcing"],
            "importance": ["consistent food safety practices", "clear communication between kitchen and service staff",
                           "careful ingredient sourcing", "balancing creativity with practicality",
                           "respecting customer dietary preferences"],
            "outcome": ["customer satisfaction", "repeat business", "dish consistency", "overall food quality",
                        "restaurant reputation"],
            "trend": ["continued growth in plant-based dining options", "greater emphasis on sustainable and local sourcing",
                      "more experimentation with global flavor combinations",
                      "increased reliance on delivery and takeout models",
                      "growing interest in transparent, traceable ingredient sourcing"],
            "closing": ["kitchens that prioritize consistency tend to build the strongest customer loyalty",
                        "sourcing quality ingredients remains the foundation of a great dish",
                        "small technique improvements often make the biggest difference in the final result",
                        "the best dining experiences balance creativity with genuine hospitality",
                        "attention to detail continues to separate memorable meals from forgettable ones"],
        },
    },
    "travel": {
        "entities": ["Lonely Planet", "Airbnb", "Marriott International", "TripAdvisor", "Emirates Airlines",
                     "Make My Trip", "Booking.com", "Taj Hotels", "Expedia", "Intrepid Travel", "Qatar Airways",
                     "Hilton Hotels", "National Geographic Travel", "Contiki", "Trip.com"],
        "topics": ["Hidden Gem Destination", "Budget Travel Guide", "Luxury Resort Review", "Adventure Tourism",
                   "Cultural Heritage Site", "Solo Travel Tips", "Family Vacation Planning", "Sustainable Tourism",
                   "Food Tourism", "Road Trip Itinerary", "Island Getaway", "Mountain Trekking Route",
                   "City Break Guide", "Travel Safety Advisory", "Off-Season Travel Deals"],
        "title_fmt": "Exploring {location}: {entity}'s Guide to {topic}",
        "phrases": {
            "subject": ["local culture and customs", "hidden travel destinations", "budget-friendly itinerary planning",
                        "sustainable tourism practices", "seasonal travel patterns"],
            "subject2": ["accommodation options", "transportation logistics", "travel safety considerations",
                         "local cuisine exploration", "cultural etiquette"],
            "focus": ["making travel more accessible", "supporting local communities and economies",
                      "reducing the environmental impact of tourism", "helping travelers avoid common pitfalls",
                      "uncovering lesser-known destinations"],
            "activity": ["researching local customs", "planning multi-city itineraries", "comparing accommodation options",
                         "navigating public transportation", "negotiating with local guides"],
            "skill": ["careful budget planning", "adaptability to unfamiliar environments",
                      "basic knowledge of the local language", "patience with travel delays",
                      "an eye for authentic local experiences"],
            "benefit": ["a more authentic travel experience", "significant cost savings", "reduced environmental impact",
                        "stronger connections with local communities", "fewer travel-related stresses"],
            "challenge": ["navigating unpredictable weather", "managing tight travel budgets",
                          "adjusting to unfamiliar customs", "dealing with overtourism in popular spots",
                          "coping with last-minute itinerary changes"],
            "development": ["growing interest in sustainable and responsible tourism",
                            "wider availability of budget travel options", "increased use of travel-planning apps",
                            "greater demand for off-the-beaten-path destinations",
                            "expanded direct flight routes to smaller cities"],
            "importance": ["respecting local customs and traditions", "careful pre-trip planning",
                           "choosing accommodations that support local communities", "staying flexible with itineraries",
                           "prioritizing traveler safety"],
            "outcome": ["overall traveler satisfaction", "local economic benefit", "environmental impact",
                        "trip cost efficiency", "cultural understanding"],
            "trend": ["continued growth in sustainable and eco-conscious travel",
                      "more travelers seeking authentic, off-the-beaten-path experiences",
                      "increased reliance on travel apps for planning",
                      "growing popularity of extended slow-travel itineraries",
                      "rising interest in multi-generational family travel"],
            "closing": ["travelers who plan thoughtfully tend to have more rewarding experiences",
                        "supporting local businesses often leads to a richer, more authentic trip",
                        "flexibility remains one of the most valuable traits for any traveler",
                        "the most memorable trips often come from the least expected detours",
                        "sustainable travel choices increasingly shape where and how people choose to explore"],
        },
    },
    "science_environment": {
        "entities": ["NASA", "NOAA", "World Wildlife Fund", "Intergovernmental Panel on Climate Change",
                     "National Geographic Society", "MIT Media Lab", "Greenpeace", "CSIRO",
                     "European Space Agency", "National Renewable Energy Laboratory",
                     "Woods Hole Oceanographic Institution", "Indian Space Research Organisation",
                     "Smithsonian Institution", "Max Planck Institute", "Nature Conservancy"],
        "topics": ["Climate Research", "Renewable Energy Innovation", "Marine Conservation",
                   "Space Exploration Mission", "Biodiversity Study", "Carbon Capture Technology",
                   "Wildlife Protection Program", "Sustainable Agriculture Research", "Ocean Cleanup Initiative",
                   "Air Quality Monitoring", "Reforestation Project", "Genetic Research Breakthrough",
                   "Astronomical Discovery", "Renewable Grid Development", "Environmental Policy Study"],
        "title_fmt": "{entity} Study Reveals New Insights on {topic}",
        "phrases": {
            "subject": ["climate data analysis", "ecosystem preservation strategies", "renewable energy adoption",
                        "biodiversity monitoring", "carbon emissions reduction"],
            "subject2": ["policy implications", "public awareness campaigns", "long-term data collection",
                         "international research collaboration", "technological innovation"],
            "focus": ["reducing carbon emissions", "protecting vulnerable ecosystems",
                      "advancing renewable energy adoption", "improving climate prediction models",
                      "strengthening biodiversity conservation"],
            "activity": ["collecting field data", "analyzing satellite imagery", "monitoring wildlife populations",
                         "modeling long-term climate trends", "testing renewable energy prototypes"],
            "skill": ["rigorous data analysis", "careful field observation methods", "cross-disciplinary collaboration",
                      "clear science communication", "long-term project planning"],
            "benefit": ["improved climate prediction accuracy", "stronger conservation outcomes",
                        "reduced carbon emissions", "greater public awareness of environmental issues",
                        "more efficient renewable energy systems"],
            "challenge": ["securing consistent research funding", "translating research into effective policy",
                          "measuring long-term environmental impact", "coordinating international research efforts",
                          "addressing skepticism around scientific findings"],
            "development": ["improved satellite monitoring technology", "breakthroughs in renewable energy storage",
                            "expanded international climate agreements", "new modeling techniques for extreme weather",
                            "growing citizen-science data collection efforts"],
            "importance": ["transparent and reproducible research methods", "long-term consistent data collection",
                           "clear communication of findings to the public",
                           "international collaboration across research institutions",
                           "translating findings into actionable policy"],
            "outcome": ["global emissions levels", "ecosystem health", "public policy decisions",
                        "renewable energy adoption rates", "biodiversity preservation"],
            "trend": ["accelerating investment in renewable energy infrastructure",
                      "greater international cooperation on climate policy",
                      "wider adoption of data-driven conservation strategies",
                      "growing public engagement with environmental science",
                      "increased urgency around biodiversity loss"],
            "closing": ["sustained, long-term research remains essential for understanding complex environmental systems",
                        "the gap between scientific findings and policy action continues to narrow but slowly",
                        "collaboration across borders remains critical for tackling global environmental challenges",
                        "small, consistent interventions often add up to meaningful long-term impact",
                        "public understanding of the science increasingly shapes the pace of policy change"],
        },
    },
    "law_government": {
        "entities": ["Supreme Court", "Ministry of Law and Justice", "United Nations", "European Union",
                     "Department of Justice", "Election Commission", "World Trade Organization",
                     "State Legislature", "City Council", "International Court of Justice",
                     "National Human Rights Commission", "Ministry of Home Affairs", "Parliament",
                     "White House", "House of Representatives"],
        "topics": ["Policy Reform", "Election Regulation", "Data Privacy Law", "Trade Agreement", "Judicial Ruling",
                   "Public Safety Initiative", "Tax Legislation", "Human Rights Report", "Environmental Regulation",
                   "Immigration Policy", "Constitutional Amendment", "Anti-Corruption Measure", "Labor Law Reform",
                   "Cybersecurity Regulation", "Housing Policy"],
        "title_fmt": "{entity} Proposes New {topic} in {location}",
        "phrases": {
            "subject": ["public policy development", "legislative negotiation", "regulatory compliance",
                        "judicial interpretation", "government transparency"],
            "subject2": ["public opinion and consultation", "enforcement mechanisms", "international legal cooperation",
                         "budget allocation", "administrative implementation"],
            "focus": ["improving government accountability", "protecting individual rights",
                      "streamlining regulatory processes", "strengthening enforcement mechanisms",
                      "increasing public transparency"],
            "activity": ["drafting legislative proposals", "conducting public consultations", "reviewing case precedents",
                         "negotiating with stakeholders", "enforcing existing regulations"],
            "skill": ["careful legal analysis", "clear public communication", "negotiation across differing viewpoints",
                      "attention to procedural detail", "balancing competing stakeholder interests"],
            "benefit": ["greater government transparency", "stronger protection of individual rights",
                        "more efficient regulatory processes", "improved public trust in institutions",
                        "more consistent enforcement of laws"],
            "challenge": ["navigating political disagreement", "balancing competing stakeholder interests",
                          "ensuring consistent enforcement across regions", "managing public skepticism",
                          "adapting older laws to new technology"],
            "development": ["new data privacy regulations", "expanded international trade agreements",
                            "updated cybersecurity legislation", "reforms to judicial procedure",
                            "increased use of digital government services"],
            "importance": ["transparent decision-making processes", "consistent and fair enforcement",
                           "clear communication with the public", "protecting due process",
                           "incorporating diverse stakeholder input"],
            "outcome": ["public trust in institutions", "regulatory compliance rates", "policy effectiveness",
                        "legal precedent", "government efficiency"],
            "trend": ["growing demand for greater government transparency",
                      "increased focus on digital privacy protections",
                      "wider international cooperation on regulatory standards",
                      "greater public participation in policy consultations",
                      "accelerating modernization of legal and administrative systems"],
            "closing": ["policies developed with broad public input tend to see stronger long-term compliance",
                        "transparency continues to be one of the strongest predictors of public trust in institutions",
                        "balancing competing interests remains at the core of effective governance",
                        "legal systems that adapt to new technology tend to remain more effective over time",
                        "sustained public engagement often determines whether reforms succeed in practice"],
        },
    },
}

LOCATIONS = [
    "Bengaluru", "Mumbai", "Delhi", "Hyderabad", "Pune", "Chennai", "San Francisco", "New York",
    "London", "Singapore", "Toronto", "Sydney", "Berlin", "Tokyo", "Dubai", "Seattle", "Austin",
    "Boston", "Amsterdam", "Chicago",
]


def build_content(rng, phrase_bank, entity, location, subject_for_title):
    sentences = []
    total_words = 0
    template_indices = list(range(len(SENTENCE_TEMPLATES)))
    while total_words < MIN_WORDS:
        rng.shuffle(template_indices)
        for i in template_indices:
            if total_words >= 480:
                break
            fill = {key: rng.choice(values) for key, values in phrase_bank.items()}
            fill["entity"] = entity
            fill["location"] = location
            sentence = SENTENCE_TEMPLATES[i].format(**fill)
            sentences.append(sentence)
            total_words += len(sentence.split())
        if total_words >= MIN_WORDS:
            break
    # trim from the end if we overshot the max
    while total_words > MAX_WORDS and len(sentences) > 1:
        removed = sentences.pop()
        total_words -= len(removed.split())
    paragraphs = [" ".join(sentences[i:i + 4]) for i in range(0, len(sentences), 4)]
    return "\n\n".join(paragraphs), total_words


def generate_docs():
    docs = []
    doc_id = 1
    for domain_name, domain in DOMAINS.items():
        rng = random.Random(f"{domain_name}-seed")
        for _ in range(DOCS_PER_DOMAIN):
            entity = rng.choice(domain["entities"])
            topic = rng.choice(domain["topics"])
            location = rng.choice(LOCATIONS)
            title = domain["title_fmt"].format(entity=entity, topic=topic, location=location)
            content, word_count = build_content(rng, domain["phrases"], entity, location, topic)
            docs.append({
                "id": doc_id,
                "title": title,
                "company": entity,
                "location": location,
                "content": content,
                "url": f"https://example.com/{domain_name}/{doc_id}",
                "category": domain_name,
                "_word_count": word_count,  # stripped before writing to disk
            })
            doc_id += 1
    return docs


def inject_duplicates(docs, rng, num_pairs=5):
    # picks num_pairs distinct docs and overwrites num_pairs LATER docs with
    # identical title+content (different id/url/location), so dedup_results()
    # still has real exact-duplicate pairs to catch, same as the original corpus did.
    total = len(docs)
    sources = rng.sample(range(total // 2), num_pairs)
    targets = rng.sample(range(total // 2, total), num_pairs)
    for src_idx, tgt_idx in zip(sources, targets):
        src = docs[src_idx]
        tgt = docs[tgt_idx]
        tgt["title"] = src["title"]
        tgt["content"] = src["content"]
        tgt["company"] = src["company"]
        tgt["category"] = src["category"]
        tgt["_word_count"] = src["_word_count"]
    return [(docs[s]["id"], docs[t]["id"]) for s, t in zip(sources, targets)]


def build_links(docs, rng, min_links=2, max_links=4):
    ids = [d["id"] for d in docs]
    for doc in docs:
        n = rng.randint(min_links, max_links)
        candidates = [i for i in ids if i != doc["id"]]
        doc["links"] = sorted(rng.sample(candidates, n))
    return docs


def main():
    docs = generate_docs()
    dup_rng = random.Random("duplicates-seed")
    dup_pairs = inject_duplicates(docs, dup_rng, num_pairs=5)

    link_rng = random.Random(42)
    docs = build_links(docs, link_rng)

    word_counts = [d["_word_count"] for d in docs]
    for d in docs:
        del d["_word_count"]

    out_path = Path(__file__).resolve().parent.parent / "data" / "corpus.json"
    out_path.write_text(json.dumps(docs, indent=2))

    print(f"Wrote {len(docs)} documents to {out_path}")
    print(f"Word count: min={min(word_counts)} max={max(word_counts)} avg={sum(word_counts)/len(word_counts):.1f}")
    print(f"Docs outside [300,500]: {sum(1 for w in word_counts if w < 300 or w > 500)}")
    print(f"Duplicate pairs injected (for dedup testing): {dup_pairs}")
    categories = {}
    for d in docs:
        categories[d["category"]] = categories.get(d["category"], 0) + 1
    print(f"Docs per category: {categories}")


if __name__ == "__main__":
    main()
