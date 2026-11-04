"""Demo data seeder: citizens, teams, problems. Running the seeder also
runs the full analysis pipeline so clusters, matches and duplicate flags
are populated before the first human touches the UI.

These problems are DEMO APP CONTENT only (they flow through the live
inference pipeline). They are NOT used as ML training or evaluation
labels — model labels come exclusively from human annotation of real
Chicago/NYC 311 data (see app/routers/labels.py + data/real/).

Demo logins (password in parentheses):
  admin@civic.demo (admin123)
  citizen1@civic.demo / citizen2@civic.demo (demo123)
  team1@civic.demo ... team8@civic.demo (demo123)
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Feedback, Problem, Team, TeamMember, User
from .pipeline import analyze_problem, invalidate_cache
from .security import hash_password
from .ml.embed import get_shared_embedder

log = logging.getLogger(__name__)

PROBLEMS = [
    # (title, description, location, category, owner_index)
    # Near-duplicate demo pairs (same incident, two wordings) exist so the
    # UI can demonstrate the live inference pipeline; they are NEVER used as
    # ML training/evaluation labels.
    ("Street light not working on Model Town road",
     "The street light near the bus stand on Model Town road has been off for two weeks. It is very dark at night and unsafe for pedestrians.",
     "Model Town, Ludhiana", "street_light", 0),
    ("Street lamp off near Model Town bus stand",
     "Street light near the bus stand in Model Town has not been working for about two weeks now. The whole stretch is dark after sunset and pedestrians feel unsafe walking.",
     "Model Town, Ludhiana", "street_light", 1),
    ("Street light pole damaged by truck",
     "A truck hit the street light pole on Phase 2 road last night. The light is hanging and flickering and there is an electrical hazard.",
     "Phase 2, Ludhiana", "street_light", 0),
    ("Dark lane due to missing street light",
     "The street light in the narrow lane behind Gandhi Market is missing. We have to carry torches at night. Please install a new light.",
     "Gandhi Market lane, Ludhiana", "street_light", 1),

    ("Deep pothole on Main Bazaar road",
     "There is a deep pothole in the middle of Main Bazaar road. Two-wheeler riders are taking sudden U-turns to avoid it. A man was nearly injured yesterday.",
     "Main Bazaar, Ludhiana", "pothole", 0),
    ("Pothole in the middle of Main Bazaar road",
     "A deep pothole is sitting in the middle of Main Bazaar road. Riders are making sudden U-turns to avoid it and someone was nearly injured yesterday.",
     "Main Bazaar, Ludhiana", "pothole", 1),
    ("Road surface badly damaged with multiple potholes",
     "The road surface in front of the new school on Naraina road is badly damaged. There are multiple potholes and the road is very bumpy.",
     "Naraina, Ludhiana", "pothole", 0),
    ("Pothole near shopping mall causing accidents",
     "There is a wide pothole beside the parking lot of the shopping mall. A scooter rider skidded into it this morning and got injured.",
     "City Mall area, Ludhiana", "pothole", 1),

    ("Water supply stopped for three days",
     "We have not received municipal water in Sector 14 for three days. There is no pump working and no announcement. Families with small children are suffering.",
     "Sector 14, Ludhiana", "water_supply", 0),
    ("No water in Sector 14 for three days",
     "We have not been getting municipal water in Sector 14 for three days now. No pump is working and there has been no announcement; families with small children are suffering.",
     "Sector 14, Ludhiana", "water_supply", 1),
    ("Dirty water coming from taps",
     "Since last week the water coming out of our taps in Civil Lines is yellow and smelly. We are worried about its quality and health risks.",
     "Civil Lines, Ludhiana", "water_supply", 0),
    ("Water pipeline burst flooding the street",
     "A water pipeline burst on Focal Point road is flooding the street. Fresh water is wasted and the road is slippery. Please repair urgently.",
     "Focal Point, Ludhiana", "water_supply", 1),

    ("Sewage water overflowing on residential street",
     "Sewage water is overflowing from the drain on our street in Transport Nagar. The smell is unbearable and children have started getting rashes.",
     "Transport Nagar, Ludhiana", "sewage", 0),
    ("Sewage overflow on our street in Transport Nagar",
     "Sewage is overflowing from the drain on our street in Transport Nagar. The stink is unbearable and the kids have started developing rashes.",
     "Transport Nagar, Ludhiana", "sewage", 1),
    ("Blocked drain causing stagnant sewage",
     "The main drain near the vegetable market in Model Town is blocked. Stagnant sewage water is spreading everywhere and mosquitos are breeding.",
     "Model Town, Ludhiana", "sewage", 0),
    ("Open manhole near school crossing",
     "An open manhole near the school crossing on Phase 7 road is covered only by a loose board. A child could fall in. Very dangerous.",
     "Phase 7, Ludhiana", "sewage", 1),

    ("Garbage not collected for a week",
     "Garbage has not been collected in our colony in New Bus Adda for a week. Piles of waste are overflowing from the bins and dogs are scattering it.",
     "New Bus Adda, Ludhiana", "garbage", 0),
    ("Waste not collected in New Bus Adda colony",
     "Garbage has not been picked up in our colony in New Bus Adda for a week. The bins are overflowing with waste and dogs are scattering it all over.",
     "New Bus Adda, Ludhiana", "garbage", 1),
    ("Burning of garbage causing smoke",
     "Someone is burning collected garbage inside the vacant land near Model Town daily in the evening. The smoke and smell are affecting residents.",
     "Model Town, Ludhiana", "garbage", 0),

    ("Traffic signal not working at Ropar crossing",
     "The traffic signal at the Ropar road crossing is not working since Monday. Vehicles are driving without stopping and pedestrians are in danger.",
     "Ropar crossing, Ludhiana", "traffic", 0),
    ("Signal dead at Ropar road crossing",
     "The traffic signal at the Ropar road crossing has not been working since Monday. Vehicles are passing without stopping and pedestrians are at risk.",
     "Ropar crossing, Ludhiana", "traffic", 1),
    ("No signal at busy junction",
     "There is no traffic signal at the busy junction near the old bus stand. Rush hour becomes chaotic and near-miss accidents happen daily.",
     "Old Bus Stand, Ludhiana", "traffic", 0),
    ("Speed breakers removed from school zone",
     "The speed breakers in front of the government school on Civil Lines have been removed. Cars are speeding past the school and children cross the road in fear.",
     "Civil Lines, Ludhiana", "traffic", 1),

    ("Broken playground equipment in public park",
     "The swings and slides in the public park near Phase 5 are broken and rusty. Children are still trying to use them and it is unsafe.",
     "Phase 5 park, Ludhiana", "public_space", 0),
    ("Graffiti and dumping on public wall",
     "The public wall near the railway station is covered with filthy graffiti and the corner is used as a dumping spot for waste.",
     "Station area, Ludhiana", "public_space", 1),
    ("Trees blocking road and electricity wires",
     "Overgrown trees on the roadside in Focal Point are touching electricity wires and blocking the view of the road. A branch already fell last month.",
     "Focal Point, Ludhiana", "public_space", 0),

    ("Encroachment on public footpath",
     "Shopkeepers have put stalls and tables on the public footpath near the hospital gate. Pedestrians, especially elderly people, have to walk on the road.",
     "Hospital gate, Ludhiana", "encroachment", 0),
    ("Footpath blocked by stalls near hospital gate",
     "Shopkeepers have placed stalls and tables on the public footpath near the hospital gate. Pedestrians, especially the elderly, are forced to walk on the road.",
     "Hospital gate, Ludhiana", "encroachment", 1),
]


TEAMS = [
    # (team_name, description, skills, interests, experience, members)
    ("Smart Street Labs",
     "Student team working on IoT-based street lighting monitoring and smart-city sensor projects.",
     ["python", "iot", "sensor networks", "data analysis", "embedded systems"],
     ["street lights", "smart city", "public lighting"],
     "Built a street light monitoring application with motion sensors for a local NGO last year.",
     [("Rohan Gupta", "lead"), ("Sana Iqbal", "hardware"), ("Manav Ahuja", "software")]),
    ("GeoFix Collective",
     "Team using remote sensing and computer vision to detect and map road damage.",
     ["python", "computer vision", "remote sensing", "gis", "image processing"],
     ["potholes", "road maintenance", "urban planning"],
     "Developed a pothole detection pipeline from drone imagery in a university hackathon.",
     [("Ishita Kaur", "lead"), ("Naman Chopra", "cv engineer")]),
    ("AquaTech Guild",
     "Data-science focused team on water quality, supply and drainage analytics.",
     ["python", "data analysis", "statistics", "water quality sensors", "pandas"],
     ["water supply", "sewage", "drainage", "public health"],
     "Analyzed municipal water quality reports and built a demand forecasting notebook.",
     [("Tania Malhotra", "lead"), ("Harsh Bedi", "data engineer"), ("Zoya Khan", "analyst")]),
    ("WasteNot Innovators",
     "Team building apps and IoT for waste management and collection logistics.",
     ["app development", "iot", "machine learning", "python", "react"],
     ["garbage", "waste management", "collection routes"],
     "Shipped a garbage-collection tracking pilot app with a local civic vendor.",
     [("Dev Kapoor", "lead"), ("Riya Sethi", "ml engineer")]),
    ("TrafficSense",
     "Computer vision team working on traffic analysis and road safety systems.",
     ["computer vision", "deep learning", "python", "video analytics", "open cv"],
     ["traffic signals", "road safety", "junction management"],
     "Built a vehicle counting model from CCTV footage for a campus traffic study.",
     [("Arjun Baid", "lead"), ("Niki Rathi", "research")]),
    ("Civic Data Hackers",
     "Web team turning civic datasets into dashboards and public tools.",
     ["web development", "python", "data visualization", "fastapi", "sql"],
     ["civic data", "dashboards", "open data"],
     "Published an open dashboard of ward-level complaint data for the college community.",
     [("Simran Bajwa", "lead"), ("Tanish Kumar", "frontend")]),
    ("EcoWatchers",
     "Drone and image processing team monitoring public spaces and encroachment.",
     ["drone operations", "image processing", "python", "gis"],
     ["encroachment", "public spaces", "tree monitoring"],
     "Mapped encroachment along a riverbank using aerial photos in a summer project.",
     [("Vivaan Gill", "lead"), ("Mira Chadha", "imaging")]),
    ("SafeCity Squad",
     "Team focused on public safety tech: CCTV analytics, safety audits and mobile reporting.",
     ["security", "cctv analytics", "mobile development", "python"],
     ["public safety", "street lighting", "surveillance ethics"],
     "Ran a night-walk safety audit and built a dark-spot reporting form for a neighborhood association.",
     [("Kabir Sandhu", "lead"), ("Anaya Verma", "mobile")]),
]


def seed_if_empty(db: Session) -> bool:
    if db.scalars(select(User)).first() is not None:
        return False
    log.info("Seeding demo data ...")

    # users
    admin = User(name="Demo Admin", email="admin@civic.demo",
                 hashed_password=hash_password("admin123"), role="admin")
    c1 = User(name="Priya Sharma", email="citizen1@civic.demo",
              hashed_password=hash_password("demo123"), role="citizen")
    c2 = User(name="Aarav Verma", email="citizen2@civic.demo",
              hashed_password=hash_password("demo123"), role="citizen")
    db.add_all([admin, c1, c2])
    db.flush()
    owners = [c1, c2]
    team_users = []
    for i in range(len(TEAMS)):
        tu = User(name=f"Team {i + 1} Lead", email=f"team{i + 1}@civic.demo",
                  hashed_password=hash_password("demo123"), role="team")
        db.add(tu)
        team_users.append(tu)
    db.flush()

    # teams
    team_rows = []
    for tu, (name, desc, skills, interests, exp, members) in zip(team_users, TEAMS):
        t = Team(
            user_id=tu.id,
            team_name=name,
            description=desc,
            skills=json.dumps(skills),
            interests=json.dumps(interests),
            experience=exp,
        )
        t.members = [TeamMember(name=n, role=r) for n, r in members]
        db.add(t)
        team_rows.append(t)
    db.flush()

    # problems through the live pipeline
    embedder = get_shared_embedder()
    problem_rows = []
    for idx, (title, desc, loc, cat, owner_i) in enumerate(PROBLEMS):
        p = Problem(
            title=title,
            description=desc,
            location=loc,
            category=cat,
            user_id=owners[owner_i].id,
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        analyze_problem(db, embedder, p, persist=True)
        db.commit()
        problem_rows.append(p)

    db.add(Feedback(
        user_id=admin.id, problem_id=problem_rows[0].id,
        feedback_type="correct_duplicate",
        comment="Demo feedback: duplicate detection matched the Model Town street light reports correctly.",
    ))
    db.commit()

    # re-run analysis so duplicate flags are consistent
    for p in problem_rows:
        analyze_problem(db, embedder, p, persist=True)
    db.commit()
    invalidate_cache()
    log.info("Seed complete: %d problems, %d teams", len(problem_rows), len(team_rows))
    return True
