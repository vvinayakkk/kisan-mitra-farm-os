"""Add citable condition references, never clinical labels or unreviewed dosages."""

import argparse
import uuid

from provision import sql

NS = uuid.UUID("139736f1-55d6-40fe-bd36-0dd104def4dd")
REFERENCES = [
    (
        "tomato",
        "Early blight",
        "https://agritech.tnau.ac.in/crop_protection/tomato_diseases_2.html",
        "Ring-like brown lesions with yellow margins; differential diagnosis requires images.",
    ),
    (
        "rice",
        "Blast",
        "https://www.agritech.tnau.ac.in/expert_system/paddy/cpdisblast.html",
        "Leaf or other plant-part injury; ask for lesions, crop stage and variety.",
    ),
    (
        "wheat",
        "Leaf rust",
        "https://agritech.tnau.ac.in/crop_protection/crop_prot_crop%20diseases_cereals_wheat.html",
        "Small orange-brown pustules mainly on upper leaves and sheaths.",
    ),
    (
        "wheat",
        "Stem rust",
        "https://agritech.tnau.ac.in/crop_protection/crop_prot_crop%20diseases_cereals_wheat.html",
        "Darker reddish-brown pustules on stems, leaves or spikes.",
    ),
    (
        "sugarcane",
        "Red rot",
        "https://www.agritech.tnau.ac.in/expert_system/sugar/faq.html",
        "Internal reddening with interrupted pale patches and leaf yellowing; confirm with local extension.",
    ),
    (
        "sugarcane",
        "Smut",
        "https://www.agritech.tnau.ac.in/expert_system/sugar/faq.html",
        "Reference condition; obtain clear whole-plant and affected-part images before assessment.",
    ),
]
BIO = "https://www.agritech.tnau.ac.in/crop_protection/crop_prot_biocontrol%20control_agents.html"
for crop in (
    "groundnut",
    "sesame",
    "sunflower",
    "pigeon-pea",
    "green-gram",
    "black-gram",
    "cotton",
):
    for name in ("Root rot", "Wilt"):
        REFERENCES.append(
            (
                crop,
                name,
                BIO,
                "Root or wilting symptom reference; inspect roots, stem, soil moisture and disease distribution.",
            )
        )
for crop in (
    "tomato",
    "chilli",
    "bitter-gourd",
    "ash-gourd",
    "watermelon",
    "muskmelon",
):
    REFERENCES.append(
        (
            crop,
            "Damping off",
            BIO,
            "Nursery seedling loss reference; confirm seedling base, root health and drainage.",
        )
    )
for crop, name in [
    ("cabbage", "Club root"),
    ("cauliflower", "Club root"),
    ("mango", "Anthracnose"),
    ("banana", "Wilt"),
    ("banana", "Anthracnose"),
]:
    REFERENCES.append(
        (
            crop,
            name,
            BIO,
            "Reference condition, not image-confirmed disease; obtain affected-part images and local expert review.",
        )
    )


def statements():
    q = [
        "BEGIN;",
        "DO $$ BEGIN IF current_database()<>'skyview_v3_demo' THEN RAISE EXCEPTION 'Local sample reference import only'; END IF; END $$;",
    ]
    for crop, name, url, summary in REFERENCES:
        code = "ref-" + crop + "-" + name.lower().replace(" ", "-")
        key = str(uuid.uuid5(NS, code))
        summary = summary.replace("'", "''")
        q.append(
            f"INSERT INTO sv3.diseases(id,code,name,crop_id,reference_document_id,symptoms) SELECT '{key}','{code}','{name}',c.id,d.id,jsonb_build_object('summary','{summary}','diagnosis_confirmed',false,'chemical_dosage_provided',false) FROM sv3.crops c JOIN LATERAL(SELECT id FROM sv3.documents WHERE source_url='{url}' AND review_status='reviewed' ORDER BY retrieved_at DESC LIMIT 1)d ON true WHERE c.code='{crop}' ON CONFLICT(code) DO NOTHING;"
        )
    return "\n".join(q + ["COMMIT;"])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    if a.apply:
        sql(statements(), "skyview_v3_demo")
    print(f"{len(REFERENCES)} condition references; applied={a.apply}")


if __name__ == "__main__":
    main()
