#!/usr/bin/env python3
"""Generate the 30-description pilot dataset for Phase 2.

Writes data/evaluation/pilot_descriptions.jsonl. Every example is synthetic
and marked review_status="pending" + synthetic=true until human-reviewed.
The pilot is NOT the final held-out set (see docs/phase-1-evaluation-plan.md).

Skill labels are resolved to canonical registry IDs at build time; every
evidence span is validated as an exact substring of its description and
every target occupation is validated against the raw dataset.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

PROCESSED = Path("data/processed")
EVAL_DIR = Path("data/evaluation")
RAW_CSV = Path("data/raw/indian_skills_dataset.csv")

# (example_id, description, target_occupation_id, [(skill_label, evidence_span)])
EXAMPLES: list[tuple[str, str, str, list[tuple[str, str]]]] = [
    ("PILOT-001",
     "For two years I did the accounts for my father's textile shop in Hoshiarpur. "
     "I entered every sale in Tally, made bills in Excel, and filed the GST returns with our CA. "
     "I also handled cash, paid the suppliers, and kept the stock register updated.",
     "soc_13-2011_00",
     [("Financial Accounting", "did the accounts"),
      ("Excel/Spreadsheets", "Excel"),
      ("Data Entry", "entered every sale"),
      ("Taxation", "filed the GST returns"),
      ("Record Keeping", "kept the stock register updated")]),

    ("PILOT-002",
     "I worked at a mobile accessories shop in Karol Bagh for a year. I showed phones to customers, "
     "explained the prices and offers, and closed the sale. I also managed the stock in the back room "
     "and counted cash at closing time.",
     "soc_41-2031_00",
     [("Customer Service", "showed phones to customers"),
      ("Sales", "closed the sale"),
      ("Product Knowledge", "explained the prices and offers"),
      ("Inventory Management", "managed the stock in the back room")]),

    ("PILOT-003",
     "For eight months I worked night shifts at a BPO in Noida taking customer calls for a telecom company. "
     "I solved billing complaints, stayed calm with angry callers, typed notes into the computer after every call, "
     "and followed up the next day on unresolved issues.",
     "soc_43-4051_00",
     [("Customer Service", "taking customer calls"),
      ("Problem Solving", "solved billing complaints"),
      ("Conflict Resolution", "stayed calm with angry callers"),
      ("Computer Skills", "typed notes into the computer")]),

    ("PILOT-004",
     "I was the office assistant at a coaching centre in Patna. I made the class timetable, "
     "answered parent phone calls, kept student fee records in registers, and typed letters on the computer for the director.",
     "soc_43-4171_00",
     [("Scheduling", "made the class timetable"),
      ("Communication", "answered parent phone calls"),
      ("Record Keeping", "kept student fee records in registers"),
      ("Computer Skills", "typed letters on the computer")]),

    ("PILOT-005",
     "I worked in a wholesale grocery godown in Indore for a year. I loaded and unloaded trucks all day, "
     "stacked the sacks in proper order, checked incoming goods against the delivery bill, and updated the stock register every evening.",
     "soc_43-5071_00",
     [("Physical Stamina", "loaded and unloaded trucks all day"),
      ("Organization", "stacked the sacks in proper order"),
      ("Quality Control", "checked incoming goods against the delivery bill"),
      ("Inventory Management", "updated the stock register every evening")]),

    ("PILOT-006",
     "I learned Python from YouTube over six months and built small projects like a marks calculator and a to-do app. "
     "I can write basic programs, find and fix errors in my code, and read documentation to learn new libraries.",
     "soc_15-1254_00",
     [("Continuous Learning", "learned Python from YouTube"),
      ("Programming", "write basic programs"),
      ("Technical Troubleshooting", "find and fix errors in my code"),
      ("Documentation", "read documentation to learn new libraries")]),

    ("PILOT-007",
     "After Class 12 I started teaching maths to Class 8 students in my mohalla. "
     "I explain each concept patiently until they understand, check their copies every week, "
     "and talk to parents about progress every month.",
     "soc_25-3041_00",
     [("Teaching", "started teaching maths"),
      ("Patience", "explain each concept patiently until they understand"),
      ("Assessment", "check their copies every week"),
      ("Client Communication", "talk to parents about progress")]),

    ("PILOT-008",
     "For a year I looked after my bedridden grandmother and later helped a neighbour recovering from surgery. "
     "I gave medicines on schedule, dressed her wound daily, helped her bathe and eat, and noted down her temperature every morning.",
     "soc_31-1121_00",
     [("Patient Care", "looked after my bedridden grandmother"),
      ("Time Management", "gave medicines on schedule"),
      ("First Aid", "dressed her wound daily"),
      ("Data Recording", "noted down her temperature every morning")]),

    ("PILOT-009",
     "I cook at a highway dhaba near Ludhiana. I prepare dal, sabzi and tandoori rotis for 100 customers daily, "
     "keep the kitchen clean, chop vegetables fast in the morning, and decide the day's menu with the owner.",
     "soc_35-2014_00",
     [("Food Preparation", "prepare dal, sabzi and tandoori rotis"),
      ("Hygiene Standards", "keep the kitchen clean"),
      ("Speed", "chop vegetables fast"),
      ("Menu Planning", "decide the day's menu")]),

    ("PILOT-010",
     "For two years I assisted an electrician in Jaipur. I pulled wires through pipes, fixed switches and fans, "
     "used testers to find faults, and always switched off the main supply before touching anything.",
     "soc_47-2111_00",
     [("Electrical Systems", "pulled wires through pipes"),
      ("Equipment Repair", "fixed switches and fans"),
      ("Technical Troubleshooting", "used testers to find faults"),
      ("Safety Practices", "switched off the main supply before touching anything")]),

    ("PILOT-011",
     "My family grows wheat and mustard on five acres in Haryana. I prepare the fields before sowing, "
     "manage the canal watering schedule, spray pesticides carefully, and test the soil by hand to decide fertilizer.",
     "soc_11-9013_00",
     [("Agronomy", "prepare the fields before sowing"),
      ("Irrigation", "manage the canal watering schedule"),
      ("Pest Management", "spray pesticides carefully"),
      ("Soil Analysis", "test the soil by hand")]),

    ("PILOT-012",
     "I worked at a ladies' beauty parlour in Lucknow. I did threading and waxing, gave head massages, "
     "suggested hairstyles to customers, sterilized all tools after every use, and maintained the appointment diary.",
     "soc_39-5012_00",
     [("Customer Service", "suggested hairstyles to customers"),
      ("Hygiene Standards", "sterilized all tools after every use"),
      ("Scheduling", "maintained the appointment diary")]),

    ("PILOT-013",
     "I run a small mobile recharge and repair counter in Nashik. I activate SIM cards and explain plans to customers, "
     "replace cracked screens, test phones after repair, and write down daily earnings in a notebook.",
     "soc_49-2011_00",
     [("Customer Service", "explain plans to customers"),
      ("Equipment Repair", "replace cracked screens"),
      ("Technical Troubleshooting", "test phones after repair"),
      ("Record Keeping", "write down daily earnings in a notebook")]),

    ("PILOT-014",
     "I was the receptionist at a small hotel in Jaipur. I greeted guests, managed room bookings on the register, "
     "answered phone queries about tariffs, and coordinated with housekeeping for check-ins.",
     "soc_43-4171_00",
     [("Customer Service", "greeted guests"),
      ("Scheduling", "managed room bookings on the register"),
      ("Communication", "answered phone queries about tariffs"),
      ("Team Coordination", "coordinated with housekeeping for check-ins")]),

    ("PILOT-015",
     "I worked as a security guard at a housing society in Gurgaon for a year. I checked visitor IDs at the gate, "
     "patrolled the building at night, watched the CCTV screens, and stayed alert during my whole shift.",
     "soc_13-1199_07",
     [("Discipline", "patrolled the building at night"),
      ("Surveillance", "watched the CCTV screens"),
      ("Situational Awareness", "stayed alert during my whole shift")]),

    ("PILOT-016",
     "For six months I did data entry at a transport company in Kanpur. I typed lorry receipts into Excel at high speed, "
     "double-checked every entry for mistakes, and kept the files organized by date.",
     "soc_43-9021_00",
     [("Data Entry", "typed lorry receipts into Excel"),
      ("Typing Speed", "at high speed"),
      ("Data Entry Accuracy", "double-checked every entry for mistakes"),
      ("Organization", "kept the files organized by date")]),

    ("PILOT-017",
     "I edit wedding videos as a freelancer in Surat. I cut and join clips to tell the day's story, "
     "add music and titles, fix the colours, and deliver before the deadline.",
     "soc_27-4032_00",
     [("Storytelling", "tell the day's story"),
      ("Creativity", "add music and titles"),
      ("Time Management", "deliver before the deadline")]),

    ("PILOT-018",
     "I help a CA in Ahmedabad with GST work. I collect bills from clients, check them for errors, "
     "enter them in the software, prepare the monthly return summaries, and remind clients about filing deadlines on the phone.",
     "soc_13-2011_00",
     [("Client Communication", "collect bills from clients"),
      ("Auditing", "check them for errors"),
      ("Data Entry", "enter them in the software"),
      ("Taxation", "prepare the monthly return summaries")]),

    ("PILOT-019",
     "I assist at a medical store in Bhopal. I hand over medicines as per the doctor's slip, "
     "explain the dosage timings to customers, keep the racks arranged, and note down stock that is running low.",
     "soc_29-2052_00",
     [("Attention to Detail", "hand over medicines as per the doctor's slip"),
      ("Customer Service", "explain the dosage timings to customers"),
      ("Organization", "keep the racks arranged"),
      ("Inventory Management", "note down stock that is running low")]),

    ("PILOT-020",
     "I manage the office of a private school in Ranchi. I maintain admission records, prepare the monthly fee reports, "
     "answer parent calls, arrange meetings for the principal, and prepare the duty roster for the support staff.",
     "soc_11-3012_00",
     [("Record Keeping", "maintain admission records"),
      ("Report Writing", "prepare the monthly fee reports"),
      ("Communication", "answer parent calls"),
      ("Administrative Coordination", "arrange meetings for the principal")]),

    ("PILOT-021",
     "I work as a mason in Hyderabad. I mix cement in the right ratio, lay bricks in straight lines, "
     "check levels with the thread line, carry bricks up the scaffolding all day, and finish plaster smoothly.",
     "soc_47-2161_00",
     [("Construction Techniques", "mix cement in the right ratio"),
      ("Attention to Detail", "lay bricks in straight lines"),
      ("Measurement", "check levels with the thread line"),
      ("Physical Stamina", "carry bricks up the scaffolding all day")]),

    ("PILOT-022",
     "I do woodwork in Jalandhar. I take exact measurements before cutting any costly wood, "
     "cut wood to exact measurements, join frames with screws and glue, "
     "polish the finished pieces, and repair old furniture.",
     "soc_47-2031_00",
     [("Measurement", "cut wood to exact measurements"),
      ("Hand Tools", "join frames with screws and glue"),
      ("Attention to Detail", "polish the finished pieces"),
      ("Equipment Repair", "repair old furniture")]),

    ("PILOT-023",
     "I handle Instagram for my cousin's clothing shop. I take photos of new stock, write captions, "
     "reply to customer messages, track which posts get more orders, and shoot short videos of the shop for festival sales.",
     "soc_41-3011_00",
     [("Digital Literacy", "handle Instagram"),
      ("Creativity", "take photos of new stock"),
      ("Customer Relations", "reply to customer messages"),
      ("Data Interpretation", "track which posts get more orders")]),

    ("PILOT-024",
     "I run a bank customer service point in my village in Bihar. I help people open accounts, "
     "explain government schemes, do money transfers on the computer, and keep the cash record safe.",
     "soc_43-9061.00",
     [("Customer Service", "help people open accounts"),
      ("Financial Literacy", "explain government schemes"),
      ("Computer Skills", "do money transfers on the computer"),
      ("Record Keeping", "keep the cash record safe")]),

    ("PILOT-025",
     "I work as a health volunteer in my block. I visit homes to check on pregnant women, teach mothers about vaccines, "
     "keep the survey register updated, and give basic first aid for small cuts.",
     "soc_21-1094_00",
     [("Community Outreach", "visit homes to check on pregnant women"),
      ("Teaching", "teach mothers about vaccines"),
      ("Record Keeping", "keep the survey register updated"),
      ("First Aid", "give basic first aid for small cuts")]),

    ("PILOT-026",
     "I pack orders at an e-commerce warehouse in Mumbai. I pick items from shelves as per the list, "
     "pack them quickly and safely, stick address labels without mistakes, and load the dispatch van.",
     "soc_43-5071_00",
     [("Material Management", "pick items from shelves as per the list"),
      ("Speed", "pack them quickly"),
      ("Attention to Detail", "stick address labels without mistakes"),
      ("Physical Stamina", "load the dispatch van")]),

    ("PILOT-027",
     "I write articles from home for blogs. I research topics online, write in simple English, "
     "check facts before publishing, meet client deadlines, and edit the articles based on client feedback.",
     "soc_27-3043_00",
     [("Research", "research topics online"),
      ("Academic Writing", "write in simple English"),
      ("Attention to Detail", "check facts before publishing"),
      ("Time Management", "meet client deadlines")]),

    ("PILOT-028",
     "I am learning web design from free courses. I built two practice websites, styled them with CSS, "
     "fixed layout problems by myself, keep learning new tricks daily, and help friends fix their blog layouts for free.",
     "soc_15-1254_00",
     [("Programming", "built two practice websites"),
      ("Creativity", "styled them with CSS"),
      ("Technical Troubleshooting", "fixed layout problems by myself"),
      ("Continuous Learning", "keep learning new tricks daily")]),

    ("PILOT-029",
     "I work as a cashier at a supermarket in Chennai. I scan items fast, handle cash and card payments carefully, "
     "greet every customer with a smile, and tally the register at closing.",
     "soc_41-2011_00",
     [("Speed", "scan items fast"),
      ("Attention to Detail", "handle cash and card payments carefully"),
      ("Customer Service", "greet every customer with a smile"),
      ("Financial Accounting", "tally the register at closing")]),

    ("PILOT-030",
     "I serve at a restaurant in Delhi. I take orders, serve food and clear tables during the rush, "
     "remember regular customers' preferences, handle complaints politely, and refill water glasses without being asked.",
     "soc_35-3031_00",
     [("Multitasking", "take orders, serve food and clear tables"),
      ("Customer Relations", "remember regular customers' preferences"),
      ("Conflict Resolution", "handle complaints politely")]),
]


def main() -> None:
    # load registry + occupation info
    label_to_id: dict[str, str] = {}
    with (PROCESSED / "skill_registry.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            label_to_id[row["label"]] = row["skill_id"]
    occ_info: dict[str, dict] = {}
    with RAW_CSV.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            occ_info[row["id"].strip()] = {
                "title": row["title"].strip(), "domain": row["domain"].strip()}

    assert len(EXAMPLES) == 30, f"expected 30 examples, got {len(EXAMPLES)}"
    seen_ids = set()
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EVAL_DIR / "pilot_descriptions.jsonl"
    with out_path.open("w", encoding="utf-8") as out:
        for ex_id, desc, occ_id, skills in EXAMPLES:
            assert ex_id not in seen_ids, f"duplicate {ex_id}"
            seen_ids.add(ex_id)
            assert 30 <= len(desc.split()) <= 130, f"{ex_id}: description length out of range"
            assert occ_id in occ_info, f"{ex_id}: unknown occupation {occ_id}"
            expected = []
            for label, span in skills:
                assert label in label_to_id, f"{ex_id}: unknown skill {label}"
                assert span in desc, f"{ex_id}: span not found: {span!r}"
                assert 3 <= len(skills) <= 7
                expected.append({
                    "skill_id": label_to_id[label],
                    "skill_label": label,
                    "evidence_span": span,
                })
            record = {
                "example_id": ex_id,
                "description": desc,
                "target_occupation_id": occ_id,
                "target_occupation_title": occ_info[occ_id]["title"],
                "target_domain": occ_info[occ_id]["domain"],
                "expected_skills": expected,
                "review_status": "pending",
                "reviewer_notes": "",
                "synthetic": True,
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"wrote {out_path} ({len(EXAMPLES)} examples, all pending review)")


if __name__ == "__main__":
    main()
