import os
import subprocess
import pandas as pd
from pathlib import Path
import gzip
import shutil
import re

VFDB_DIR = os.path.join(os.path.dirname(__file__), "vfdb_data")
VFDB_FASTA_GZ = os.path.join(VFDB_DIR, "VFDB_setA_nt.fas.gz")
VFDB_FASTA = os.path.join(VFDB_DIR, "VFDB_setA_nt.fas")
VFDB_DB = os.path.join(VFDB_DIR, "VFDB")
VFGID_GENE_CATEGORY_CSV = os.path.join(VFDB_DIR, "vfdb_vfgid_gene_category_mapping.csv")
VF_NAME_DESC_CSV = os.path.join(VFDB_DIR, "vf_name_description_mapping.csv")

# BLAST+ executables configuration with environment variable support
BLAST_BIN = os.environ.get('BLAST_BIN', r"C:/Users/Administrator/Desktop/NCBI/blast-2.16.0+/bin")
IS_WINDOWS = os.name == 'nt'  # Check if running on Windows

# Set executable names with appropriate extension
MAKEBLASTDB = os.path.join(BLAST_BIN, "makeblastdb" + (".exe" if IS_WINDOWS else ""))
BLASTN = os.path.join(BLAST_BIN, "blastn" + (".exe" if IS_WINDOWS else ""))

def extract_accession_from_filename(filename):
    # Example: GCF_014844975.1_ASM1484497v1_genomic.fna -> GCF_014844975.1
    base = os.path.basename(filename)
    # Extract accession up to the first occurrence of '_genomic' or the second underscore
    acc = base.split('_genomic')[0] if '_genomic' in base else '_'.join(base.split('_')[:2])
    return acc

def ensure_uncompressed_fasta():
    if not os.path.exists(VFDB_FASTA):
        with gzip.open(VFDB_FASTA_GZ, 'rb') as f_in:
            with open(VFDB_FASTA, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

def build_blast_db():
    ensure_uncompressed_fasta()
    if all(Path(f).exists() for f in [VFDB_DB + ext for ext in ['.nhr', '.nin', '.nsq']]):
        return
    subprocess.run([
        MAKEBLASTDB,
        "-in", VFDB_FASTA,
        "-dbtype", "nucl",
        "-out", VFDB_DB
    ], check=True)

def run_blast(genome_fasta, out_file, max_target_seqs=100, evalue=1e-5):
    subprocess.run([
        BLASTN,
        "-query", genome_fasta,
        "-db", VFDB_DB,
        "-out", out_file,
        "-outfmt", "6 qseqid sseqid pident length evalue bitscore",
        "-max_target_seqs", str(max_target_seqs),
        "-evalue", str(evalue)
    ], check=True)

def extract_vfg_id(sseqid):
    match = re.match(r"(VFG\d+)", str(sseqid))
    return match.group(1) if match else str(sseqid)

def parse_blast_output(blast_out_file):
    df = pd.read_csv(blast_out_file, sep='\t', header=None,
        names=["qseqid", "sseqid", "pident", "length", "evalue", "bitscore"])
    df['vfg_id'] = df['sseqid'].apply(extract_vfg_id)
    vfgid_counts = df['vfg_id'].value_counts().to_dict()
    return vfgid_counts

def parse_fasta_metadata(fasta_path):
    genus_species = ''
    bases = 0
    gc = 0
    with open(fasta_path, 'r') as f:
        for line in f:
            if line.startswith('>'):
                parts = line[1:].split()
                if len(parts) > 2:
                    genus_species = parts[1] + ' ' + parts[2]
                elif len(parts) > 1:
                    genus_species = parts[1]
            else:
                seq = line.strip().upper()
                bases += len(seq)
                gc += seq.count('G') + seq.count('C')
    kb = bases / 1000 if bases else 0
    gc_pct = (gc / bases * 100) if bases else 0
    return genus_species, round(kb, 1), round(gc_pct, 2)

def parse_blast_output_gene_names(blast_out_file, fasta_gene_map):
    df = pd.read_csv(blast_out_file, sep='\t', header=None,
        names=["qseqid", "sseqid", "pident", "length", "evalue", "bitscore"])
    # Map sseqid to short gene symbol using fasta_gene_map
    df['gene'] = df['sseqid'].map(fasta_gene_map.get)
    gene_counts = df['gene'].value_counts().to_dict()
    return gene_counts

def build_fasta_gene_map():
    # Build a map from FASTA header (sseqid) to short gene symbol using the new mapping file
    mapping = pd.read_csv(os.path.join(VFDB_DIR, 'vfdb_gene_category_mapping.csv'))
    # Load the VFDB FASTA and map each header to the short gene symbol
    fasta_map = {}
    with open(VFDB_FASTA, 'r') as f:
        gene = None
        for line in f:
            if line.startswith('>'):
                header = line[1:].strip()
                # Try to match the short gene symbol in the header
                for g in mapping['gene']:
                    if g in header:
                        fasta_map[header.split()[0]] = g
                        break
    return fasta_map

def aggregate_results(genome_fasta_list, output_matrix_csv, output_dir=None):
    # Load mapping from new mapping file (short gene symbol, category)
    mapping = pd.read_csv(os.path.join(VFDB_DIR, 'vfdb_gene_category_mapping.csv'))
    cat2genes = mapping.groupby('category')['gene'].apply(list)
    gene_order = [g for genes in cat2genes.values for g in genes]
    fasta_gene_map = build_fasta_gene_map()
    results = []
    for genome in genome_fasta_list:
        out_file = os.path.join(output_dir or '', os.path.basename(genome) + ".vfdb_blast.tsv")
        run_blast(genome, out_file)
        gene_counts = parse_blast_output_gene_names(out_file, fasta_gene_map)
        gene_row = [gene_counts.get(g, 0) for g in gene_order]
        acc = extract_accession_from_filename(genome)
        genus, kb, gc_pct = parse_fasta_metadata(genome)
        row = [acc, '', genus, kb, gc_pct, ''] + gene_row
        results.append(row)
    meta_cols = ["GENOME", "Prophage", "Host genus", "KB", "GC%", "First gene"]
    df = pd.DataFrame(results, columns=meta_cols + gene_order)
    df.to_csv(output_matrix_csv, index=False)
    return output_matrix_csv

def create_category_matrix(genome_fasta_list, output_category_csv, output_dir=None):
    """
    Create a category matrix where both rows and columns are virulence factor categories.
    The matrix shows presence (1) or absence (0) of each category for each genome.
    """
        # Define the specific categories you want
    target_categories = [
        'Adherence',
        'Motility', 
        'Regulation',
        'Nutritional/Metabolic factor',
        'Effector delivery system',
        'Exotoxin',
        'Immune modulation',
        'Antimicrobial activity/Competitive advantage',
        'Exoenzyme',
        'Biofilm'
    ]

    # Load mapping from new mapping file (short gene symbol, category)
    mapping = pd.read_csv(os.path.join(VFDB_DIR, 'vfdb_gene_category_mapping.csv'))

    # Create a mapping from gene to category
    gene_to_category = dict(zip(mapping['gene'], mapping['category']))

    fasta_gene_map = build_fasta_gene_map()
    results = []

    for genome in genome_fasta_list:
        out_file = os.path.join(output_dir or '', os.path.basename(genome) + ".vfdb_blast.tsv")
        run_blast(genome, out_file)
        gene_counts = parse_blast_output_gene_names(out_file, fasta_gene_map)

                # Create category presence vector
        category_presence = {}
        secretion_present = False
        
        for gene, count in gene_counts.items():
            if count > 0:  # Gene is present
                category = gene_to_category.get(gene)
                if category in target_categories:
                    category_presence[category] = 1
                
                # Check for secretion systems (genes containing "secretion")
                if 'secretion' in gene.lower():
                    secretion_present = True
        
        # Fill in 0 for categories not present
        for category in target_categories:
            if category not in category_presence:
                category_presence[category] = 0
        
        # Add secretion system category
        category_presence['Secretion system'] = 1 if secretion_present else 0

        acc = extract_accession_from_filename(genome)
        genus, kb, gc_pct = parse_fasta_metadata(genome)

        # Create row with genome info and category presence
        all_categories = target_categories + ['Secretion system']
        row = [acc, genus, kb, gc_pct] + [category_presence[cat] for cat in all_categories]
        results.append(row)

    # Create DataFrame
    meta_cols = ["GENOME", "Host genus", "KB", "GC%"]
    all_categories = target_categories + ['Secretion system']
    df = pd.DataFrame(results, columns=meta_cols + all_categories)

    # Save the category matrix
    df.to_csv(output_category_csv, index=False)

        # Also create a summary matrix showing category-to-category relationships
    # This creates a matrix where both rows and columns are categories
    category_summary = {}
    for category in all_categories:
        category_summary[category] = {}
        for other_category in all_categories:
            # Count how many genomes have both categories present
            both_present = sum(1 for row in results if row[meta_cols.index("GENOME") + all_categories.index(category) + 1] == 1 
                             and row[meta_cols.index("GENOME") + all_categories.index(other_category) + 1] == 1)
            category_summary[category][other_category] = both_present

    summary_df = pd.DataFrame(category_summary)
    summary_csv = output_category_csv.replace('.csv', '_summary.csv')
    summary_df.to_csv(summary_csv)

    return output_category_csv, summary_csv 
