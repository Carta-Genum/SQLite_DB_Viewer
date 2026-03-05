"""
Enrich missing technology and pathology annotations in spatial_transcriptomics.db
by parsing:
  1. Abstract/description text for technology keywords and disease terms
  2. File name patterns (each platform has characteristic file names)

Then propagates dataset-level annotations to samples.
"""

import re
import sqlite3
from collections import Counter

DB_PATH = "/Users/zuixote/Documents/carta_genum/projects/SQLite_DB_Viewer/spatial_transcriptomics.db"

# ─────────────────────────────────────────────────────────────────────────────
# Technology: abstract-text patterns (specific first, generic last)
# ─────────────────────────────────────────────────────────────────────────────
TECH_TEXT_PATTERNS: list[tuple[str, str]] = [
    (r"\bVisium\s*HD\b|\bVisiumHD\b", "VisiumHD"),
    (r"\bVisium\b", "Visium"),
    (r"\bXenium\b", "Xenium"),
    (r"\bGeoMx\b|\bGeo-Mx\b", "GeoMx DSP"),
    (r"\bMERFISH\b", "MERFISH"),
    (r"\bCosMx\b", "CosMx"),
    (r"\bSlide-[Ss]eq\b|\bSlideseq\b", "Slide-seq"),
    (r"\bseqFISH\+?\b", "seqFISH"),
    (r"\bHDST\b", "HDST"),
    (r"\bStereo-seq\b|\bSTEReo-seq\b", "Stereo-seq"),
    (r"\bCODEX\b", "CODEX"),
    (r"\bImaging\s+Mass\s+Cytometry\b|\bIMC\b", "IMC"),
    (r"\bMIBI-TOF\b|\bMIBI\b", "MIBI"),
    (r"\bsmFISH\b", "smFISH"),
    (r"\bSTARmap\b", "STARmap"),
    (r"\b[Ss]eq-[Ss]cope\b|\bseqScope\b", "Seq-Scope"),
    (r"\bDBIT-seq\b", "DBIT-seq"),
    (r"\bNova-ST\b", "Nova-ST"),
    (r"\bHybISS\b", "HybISS"),
    (r"\bMolecular Cartography\b", "Molecular Cartography"),
    (r"\bMALDI\b", "MALDI"),
    (r"\bBARISTA-seq\b", "BARISTA-seq"),
    (r"\bosmFISH\b|\bOsmFISH\b", "osmFISH"),
    (r"\bEXSeq\b|\bExpansion sequencing\b", "EXSeq"),
    (r"\biseqPLA\b|\bProximity Ligation Assay\b", "seqPLA"),
    (r"\bCITE-seq\b", "CITE-seq"),
    (r"\bSpatial Transcriptomics\b", "Spatial Transcriptomics (ST)"),
]

# ─────────────────────────────────────────────────────────────────────────────
# Technology: file-name patterns (most distinctive patterns first)
# Each tuple: (regex on filename, technology)
# ─────────────────────────────────────────────────────────────────────────────
TECH_FILE_PATTERNS: list[tuple[str, str]] = [
    # VisiumHD: binned_outputs, square_00Xum directories
    (r"binned_outputs|square_002um|square_008um|square_016um|tissue_positions\.parquet", "VisiumHD"),
    # Visium: spatial coordinates + h5 files
    (r"filtered_feature_bc_matrix\.h5|raw_feature_bc_matrix\.h5|tissue_positions(?:_list)?\.csv|scalefactors_json\.json|tissue_(?:hires|lowres)_image\.png|spatial\.tar\.gz", "Visium"),
    # Xenium: cell feature matrix + transcript/boundary files
    (r"cell_feature_matrix\.h5|cell_feature_matrix\.zarr|transcripts\.zarr|cell_boundaries\.parquet|nucleus_boundaries\.parquet|cells\.parquet|xenium_output|_xenium_|Xenium_FFPE|analysis_summary\.html.*xenium", "Xenium"),
    # GeoMx DSP: .dcc files with DSP- prefix
    (r"DSP-\d{13}-[A-Z]-[A-Z]\d{2}\.dcc|_WTA\.dcc|_CTA\.dcc|\.pkc\.gz|GeoMx", "GeoMx DSP"),
    # MERFISH (Vizgen MERSCOPE): cell_by_gene + detected_transcripts
    (r"_cell_by_gene\.csv|_detected_transcripts\.csv|_cell_metadata\.csv|\.vzg$|merscope|MERSCOPE|vizgen", "MERFISH"),
    # CosMx: exprMat_file, fov_positions_file, tx_file, polygons
    (r"_exprMat_file\.|_fov_positions_file\.|_tx_file\.|CellComposite|CellLabels|CellOverlay|CompartmentLabels|RawMorphologyImages", "CosMx"),
    # Stereo-seq: .gem.gz or .gef files
    (r"\.gem\.gz$|\.cellBin\.gef$|\.gef$|stereoseq|Stereo-seq", "Stereo-seq"),
    # Slide-seq: bead locations + digital expression
    (r"BeadLocations\.csv|_digital_expression\.txt|MappedDGEForR|slideseq|Slide-seq", "Slide-seq"),
    # HDST
    (r"HDST|hdst", "HDST"),
    # seqFISH
    (r"seqFISH|seqfish", "seqFISH"),
    # CODEX / Akoya
    (r"CODEX|codex|akoya|PhenoCycler", "CODEX"),
    # IMC
    (r"\.mcd\.gz$|\.txt\.gz.*IMC|imaging.mass.cytometry", "IMC"),
    # MIBI
    (r"MIBI|mibi_", "MIBI"),
    # STARmap
    (r"STARmap|starmap", "STARmap"),
    # Seq-Scope
    (r"SeqScope|seqscope|Seq-Scope", "Seq-Scope"),
    # HybISS
    (r"HybISS|hybiss", "HybISS"),
    # Molecular Cartography (Resolve Biosciences)
    (r"Molecular.Cartography|resolve.biosciences", "Molecular Cartography"),
    # Nova-ST
    (r"Nova-ST|nova_st", "Nova-ST"),
    # osmFISH
    (r"osmFISH|osmfish", "osmFISH"),
]

# ─────────────────────────────────────────────────────────────────────────────
# Pathology: text patterns (specific first)
# ─────────────────────────────────────────────────────────────────────────────
PATHOLOGY_PATTERNS: list[tuple[str, str]] = [
    # Neuro
    (r"\bglioblastoma\b|\bGBM\b", "glioblastoma"),
    (r"\bmedulloblastoma\b", "medulloblastoma"),
    (r"\bmeningioma\b", "meningioma"),
    (r"\bAlzheimer['\u2019s]*\s*disease\b|\bAlzheimer['\u2019s]*\b", "Alzheimer's disease"),
    (r"\bParkinson['\u2019s]*\s*disease\b|\bParkinson['\u2019s]*\b", "Parkinson's disease"),
    (r"\bMultiple\s+[Ss]clerosis\b|\brelapsing[-\s]remitting\b", "multiple sclerosis"),
    (r"\bepilep[st]", "epilepsy"),
    (r"\bautism\s+spectrum\b|\bASD\b", "autism spectrum disorder"),
    (r"\bschizophrenia\b", "schizophrenia"),
    (r"\bmajor\s+depressive\b|\bdepression\b|\bMDD\b", "depression"),
    (r"\bamyotrophic\s+lateral\s+sclerosis\b|\bALS\b", "ALS"),
    (r"\bHuntington['\u2019s]*\b", "Huntington's disease"),
    (r"\bneuroblastoma\b", "neuroblastoma"),
    (r"\bstroke\b|\bischemic\s+stroke\b|\bcerebral\s+ischemia\b", "stroke"),
    (r"\bspinal\s+cord\s+injury\b", "spinal cord injury"),
    (r"\btraumatic\s+brain\s+injury\b|\bTBI\b", "traumatic brain injury"),

    # Cancer - specific types first
    (r"\bpancreatic\s+(?:ductal\s+)?(?:adeno)?carcinoma\b|\bPDAC\b|\bpancreatic\s+cancer\b", "pancreatic cancer"),
    (r"\bhepato(?:cellular)?\s*carcinoma\b|\bHCC\b|\bliver\s+cancer\b|\bhepatic\s+cancer\b", "liver cancer"),
    (r"\bcolorectal\s+(?:cancer|carcinoma)\b|\bCRC\b|\bcolon\s+cancer\b|\brectal\s+cancer\b", "colorectal cancer"),
    (r"\bbreast\s+(?:cancer|carcinoma|tumor)\b|\btriple[-\s]negative\b|\bER\+\b|\bHER2\b", "breast cancer"),
    (r"\blung\s+(?:adeno)?carcinoma\b|\blung\s+cancer\b|\bNSCLC\b|\bSCLC\b", "lung cancer"),
    (r"\bprostate\s+(?:cancer|carcinoma|adenocarcinoma)\b", "prostate cancer"),
    (r"\bovarian\s+(?:cancer|carcinoma)\b", "ovarian cancer"),
    (r"\bcervical\s+(?:cancer|carcinoma)\b", "cervical cancer"),
    (r"\bendometrial\s+(?:cancer|carcinoma)\b|\buterine\s+cancer\b", "endometrial cancer"),
    (r"\bmelanoma\b", "melanoma"),
    (r"\bhead\s+and\s+neck\s+(?:squamous\s+cell\s+)?(?:carcinoma|cancer)\b|\bHNSCC\b", "squamous cell carcinoma; head and neck cancer"),
    (r"\bsquamous\s+cell\s+carcinoma\b|\bSCC\b", "squamous cell carcinoma"),
    (r"\bgastric\s+(?:cancer|carcinoma)\b|\bstomach\s+cancer\b", "gastric cancer"),
    (r"\besophageal\s+(?:cancer|carcinoma)\b", "esophageal cancer"),
    (r"\bbladder\s+cancer\b|\burothelial\s+carcinoma\b", "bladder cancer"),
    (r"\brenal\s+cell\s+carcinoma\b|\bkidney\s+cancer\b|\bRCC\b", "renal cell carcinoma"),
    (r"\bthyroid\s+(?:cancer|carcinoma)\b", "thyroid cancer"),
    (r"\bmesothelioma\b", "mesothelioma"),
    (r"\bleukemia\b|\bAML\b|\bCLL\b|\bCML\b|\bALL\b|\bacute\s+myeloid\b", "leukemia"),
    (r"\blymphoma\b|\bDLBCL\b|\bHodgkin\b|\bB-?cell\s+lymphoma\b|\bT-?cell\s+lymphoma\b", "lymphoma"),
    (r"\bmultiple\s+myeloma\b|\bMM\b(?=\s+patient|\s+cell|\s+tumor)", "multiple myeloma"),
    (r"\bhemangioma\b", "hemangioma"),
    (r"\bchondrosarcoma\b|\bosteosarcoma\b|\bsarcoma\b", "sarcoma"),
    (r"\bglioma\b|\bastroc?ytoma\b|\boligodendroglioma\b", "glioma"),

    # Cardiovascular
    (r"\batherosclerosis\b|\batherosclerotic\b|\bplaque\b", "atherosclerosis"),
    (r"\bheart\s+failure\b|\bcardiac\s+failure\b|\bdilated\s+cardiomyopathy\b|\bhypertrophic\s+cardiomyopathy\b", "heart failure"),
    (r"\bmyocardial\s+infarction\b|\bheart\s+attack\b", "myocardial infarction"),
    (r"\baortic\s+(?:aneurysm|stenosis|dissection)\b", "aortic disease"),
    (r"\bpulmonary\s+hypertension\b|\bPAH\b", "pulmonary hypertension"),

    # Metabolic
    (r"\btype\s+[12]\s+diabetes\b|\bT1D\b|\bT2D\b|\bdiabetes\b|\bhyperglycemia\b", "diabetes"),
    (r"\bobesity\b|\bobese\b|\boverweight\b", "obesity"),
    (r"\bNASH\b|\bNAFLD\b|\bnon-?alcoholic\s+(?:steato)?hepatitis\b|\bfatty\s+liver\b", "fatty liver disease"),
    (r"\bmetabolic\s+syndrome\b", "metabolic syndrome"),

    # Fibrosis
    (r"\bpulmonary\s+fibrosis\b|\bIPF\b|\binterstitial\s+lung\s+disease\b", "fibrosis; pulmonary fibrosis"),
    (r"\brenal\s+fibrosis\b|\bkidney\s+fibrosis\b", "renal fibrosis"),
    (r"\bliver\s+fibrosis\b|\bhepatic\s+fibrosis\b|\bcirrhosis\b", "liver fibrosis"),
    (r"\bcardiac\s+fibrosis\b|\bmyocardial\s+fibrosis\b", "cardiac fibrosis"),
    (r"\bfibrosis\b", "fibrosis"),

    # Infection / Inflammatory
    (r"\btuberculosis\b|\bMtb\b|\bMycobacterium\s+tuberculosis\b|\bTB\b", "tuberculosis"),
    (r"\bCOVID-?19\b|\bSARS-CoV-2\b|\bcoronavirus\b", "COVID-19"),
    (r"\binfluenza\b|\bflu\b", "influenza"),
    (r"\bHIV\b|\bAIDS\b|\bHIV-1\b|\bHIV-2\b", "HIV/AIDS"),
    (r"\brheumatoid\s+arthritis\b|\bRA\b", "rheumatoid arthritis"),
    (r"\bosteoarthritis\b|\bOA\b", "osteoarthritis"),
    (r"\bCrohn['\u2019s]*\b|\bulcerative\s+colitis\b|\bIBD\b|\binflammatory\s+bowel\b", "inflammatory bowel disease"),
    (r"\bsepsis\b|\bseptic\s+shock\b|\bbacteremia\b", "sepsis"),
    (r"\bmalaria\b|\bPlasmodium\b", "malaria"),
    (r"\bschistosomiasis\b|\bSchistosoma\b", "schistosomiasis"),
    (r"\bHPV\b|\bhuman\s+papillomavirus\b", "HPV infection"),
    (r"\blasthma\b", "asthma"),
    (r"\bCOPD\b|\bchronic\s+obstructive\s+pulmonary\b", "COPD"),
    (r"\bpneumonia\b", "pneumonia"),
    (r"\bsystemic\s+lupus\b|\bSLE\b|\blupus\b", "lupus"),

    # Kidney
    (r"\bchronic\s+kidney\s+disease\b|\bCKD\b|\brenal\s+failure\b", "chronic kidney disease"),
    (r"\bnephritis\b|\bglomerulonephritis\b", "nephritis"),

    # Skin
    (r"\bpsoriasis\b|\bpsoriatic\b", "psoriasis"),
    (r"\batopic\s+dermatitis\b|\beczema\b", "atopic dermatitis"),

    # Eye
    (r"\bmacular\s+degeneration\b|\bAMD\b|\bretinopathy\b", "retinal disease"),
    (r"\bglaucoma\b", "glaucoma"),

    # Bone / Musculoskeletal
    (r"\bosteoporosis\b|\bosteopenia\b", "osteoporosis"),

    # Reproductive
    (r"\bendometriosis\b", "endometriosis"),
    (r"\bpreeclampsia\b|\beclampsia\b", "preeclampsia"),

    # Liver (non-cancer)
    (r"\bprimary\s+biliary\b|\bPBC\b|\bcholangitis\b", "cholangitis"),
]


def extract_technology_from_text(text: str) -> str | None:
    if not text:
        return None
    for pattern, tech in TECH_TEXT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return tech
    return None


def extract_technology_from_files(filenames: list[str]) -> str | None:
    """Detect technology from file name patterns, using a vote across all files."""
    votes: Counter = Counter()
    combined = "\n".join(filenames)
    for pattern, tech in TECH_FILE_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE):
            votes[tech] += 1
    if not votes:
        return None
    return votes.most_common(1)[0][0]


def extract_pathology(text: str) -> str | None:
    if not text:
        return None
    matches: list[str] = []
    seen: set[str] = set()
    for pattern, pathology in PATHOLOGY_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            if pathology not in seen:
                matches.append(pathology)
                seen.add(pathology)
    return "; ".join(matches) if matches else None


def enrich_datasets(conn: sqlite3.Connection) -> dict:
    cur = conn.cursor()

    cur.execute("""
        SELECT id, description, technology, pathology
        FROM datasets
        WHERE (technology IS NULL OR technology = '')
           OR (pathology IS NULL OR pathology = '')
    """)
    datasets = cur.fetchall()

    # Pre-fetch all filenames grouped by dataset_pk
    cur.execute("SELECT dataset_pk, filename FROM files")
    files_by_dataset: dict[int, list[str]] = {}
    for dataset_pk, filename in cur.fetchall():
        files_by_dataset.setdefault(dataset_pk, []).append(filename)

    stats = {
        "tech_from_text": 0,
        "tech_from_files": 0,
        "tech_not_found": 0,
        "path_filled": 0,
        "path_not_found": 0,
    }

    for row_id, description, current_tech, current_pathology in datasets:
        updates: dict[str, str] = {}

        if not current_tech:
            tech_text = extract_technology_from_text(description)
            filenames = files_by_dataset.get(row_id, [])
            tech_files = extract_technology_from_files(filenames)

            if tech_text and tech_text != "Spatial Transcriptomics (ST)":
                # Specific platform named in abstract takes priority
                updates["technology"] = tech_text
                stats["tech_from_text"] += 1
            elif tech_files:
                # File patterns give a more specific answer
                updates["technology"] = tech_files
                stats["tech_from_files"] += 1
            elif tech_text:
                # Only generic "Spatial Transcriptomics (ST)" from text
                updates["technology"] = tech_text
                stats["tech_from_text"] += 1
            else:
                stats["tech_not_found"] += 1

        if not current_pathology:
            pathology = extract_pathology(description)
            if pathology:
                updates["pathology"] = pathology
                stats["path_filled"] += 1
            else:
                stats["path_not_found"] += 1

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [row_id]
            cur.execute(
                f"UPDATE datasets SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values,
            )

    conn.commit()
    return stats


def propagate_to_samples(conn: sqlite3.Connection) -> dict:
    cur = conn.cursor()

    cur.execute("""
        UPDATE samples
        SET technology = (
            SELECT d.technology FROM datasets d
            WHERE d.id = samples.dataset_pk
              AND d.technology IS NOT NULL AND d.technology != ''
        )
        WHERE (technology IS NULL OR technology = '')
          AND EXISTS (
            SELECT 1 FROM datasets d
            WHERE d.id = samples.dataset_pk
              AND d.technology IS NOT NULL AND d.technology != ''
          )
    """)
    tech_propagated = cur.rowcount

    cur.execute("""
        UPDATE samples
        SET disease = (
            SELECT d.pathology FROM datasets d
            WHERE d.id = samples.dataset_pk
              AND d.pathology IS NOT NULL AND d.pathology != ''
        )
        WHERE (disease IS NULL OR disease = '')
          AND EXISTS (
            SELECT 1 FROM datasets d
            WHERE d.id = samples.dataset_pk
              AND d.pathology IS NOT NULL AND d.pathology != ''
          )
    """)
    disease_propagated = cur.rowcount

    conn.commit()
    return {"tech_propagated": tech_propagated, "disease_propagated": disease_propagated}


def coverage_report(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("""
        SELECT
            (SELECT COUNT(*) FROM datasets) as d_total,
            (SELECT COUNT(*) FROM datasets WHERE technology IS NOT NULL AND technology != '') as d_tech,
            (SELECT COUNT(*) FROM datasets WHERE pathology IS NOT NULL AND pathology != '') as d_path,
            (SELECT COUNT(*) FROM samples) as s_total,
            (SELECT COUNT(*) FROM samples WHERE technology IS NOT NULL AND technology != '') as s_tech,
            (SELECT COUNT(*) FROM samples WHERE disease IS NOT NULL AND disease != '') as s_disease
    """)
    d_total, d_tech, d_path, s_total, s_tech, s_disease = cur.fetchone()

    cur.execute("""
        SELECT technology, COUNT(*) FROM datasets
        WHERE technology IS NOT NULL AND technology != ''
        GROUP BY technology ORDER BY COUNT(*) DESC LIMIT 15
    """)
    tech_dist = cur.fetchall()

    print("\n=== Coverage after enrichment ===")
    print(f"Datasets : technology {d_tech}/{d_total} ({100*d_tech//d_total}%), pathology {d_path}/{d_total} ({100*d_path//d_total}%)")
    print(f"Samples  : technology {s_tech}/{s_total} ({100*s_tech//s_total}%), disease {s_disease}/{s_total} ({100*s_disease//s_total}%)")
    print("\nDataset technology distribution:")
    for tech, cnt in tech_dist:
        print(f"  {tech}: {cnt}")


def main() -> None:
    conn = sqlite3.connect(DB_PATH)

    print("Step 1: Enriching datasets from abstracts + file patterns...")
    stats = enrich_datasets(conn)
    print(f"  Technology from abstract text : {stats['tech_from_text']}")
    print(f"  Technology from file patterns : {stats['tech_from_files']}")
    print(f"  Technology not determined     : {stats['tech_not_found']}")
    print(f"  Pathology filled              : {stats['path_filled']}")
    print(f"  Pathology not determined      : {stats['path_not_found']}")

    print("\nStep 2: Propagating dataset annotations to samples...")
    prop = propagate_to_samples(conn)
    print(f"  Technology propagated to samples: {prop['tech_propagated']}")
    print(f"  Disease propagated to samples   : {prop['disease_propagated']}")

    coverage_report(conn)
    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
