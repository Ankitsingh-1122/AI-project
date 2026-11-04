"""Student-team profiles used by the matching ranker (mirrors app/seed.py TEAMS,
which are the teams present in the production database)."""
from __future__ import annotations

from types import SimpleNamespace

TEAMS = [
    dict(team_name="Smart Street Labs",
         description="Student team working on IoT-based street lighting monitoring and smart-city sensor projects.",
         skills=["python", "iot", "sensor networks", "data analysis", "embedded systems"],
         interests=["street lights", "smart city", "public lighting"],
         experience="Built a street light monitoring application with motion sensors for a local NGO last year."),
    dict(team_name="GeoFix Collective",
         description="Team using remote sensing and computer vision to detect and map road damage.",
         skills=["python", "computer vision", "remote sensing", "gis", "image processing"],
         interests=["potholes", "road maintenance", "urban planning"],
         experience="Developed a pothole detection pipeline from drone imagery in a university hackathon."),
    dict(team_name="AquaTech Guild",
         description="Data-science focused team on water quality, supply and drainage analytics.",
         skills=["python", "data analysis", "statistics", "water quality sensors", "pandas"],
         interests=["water supply", "sewage", "drainage", "public health"],
         experience="Analyzed municipal water quality reports and built a demand forecasting notebook."),
    dict(team_name="WasteNot Innovators",
         description="Team building apps and IoT for waste management and collection logistics.",
         skills=["app development", "iot", "machine learning", "python", "react"],
         interests=["garbage", "waste management", "collection routes"],
         experience="Shipped a garbage-collection tracking pilot app with a local civic vendor."),
    dict(team_name="TrafficSense",
         description="Computer vision team working on traffic analysis and road safety systems.",
         skills=["computer vision", "deep learning", "python", "video analytics", "open cv"],
         interests=["traffic signals", "road safety", "junction management"],
         experience="Built a vehicle counting model from CCTV footage for a campus traffic study."),
    dict(team_name="Civic Data Hackers",
         description="Web team turning civic datasets into dashboards and public tools.",
         skills=["web development", "python", "data visualization", "fastapi", "sql"],
         interests=["civic data", "dashboards", "open data"],
         experience="Published an open dashboard of ward-level complaint data for the college community."),
    dict(team_name="EcoWatchers",
         description="Drone and image processing team monitoring public spaces and encroachment.",
         skills=["drone operations", "image processing", "python", "gis"],
         interests=["encroachment", "public spaces", "tree monitoring"],
         experience="Mapped encroachment along a riverbank using aerial photos in a summer project."),
    dict(team_name="SafeCity Squad",
         description="Team focused on public safety tech: CCTV analytics, safety audits and mobile reporting.",
         skills=["security", "cctv analytics", "mobile development", "python"],
         interests=["public safety", "street lighting", "surveillance ethics"],
         experience="Ran a night-walk safety audit and built a dark-spot reporting form for a neighborhood association."),
]


def team_ns(i: int) -> SimpleNamespace:
    """Namespace with the attributes app.ml.matching.team_text expects."""
    t = TEAMS[i]
    return SimpleNamespace(
        id=i,
        team_name=t["team_name"],
        description=t["description"],
        skills_list=t["skills"],
        interests_list=t["interests"],
        experience=t["experience"],
    )
