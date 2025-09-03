import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import csv
import json
import subprocess
from pathlib import Path
from utils.download_genomes import download_and_decompress_fasta
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing


def parse_fasta_header(fasta_path):
    """Extract accession and genus+species from the first header line of a FASTA file."""
    with open(fasta_path, 'r') as f:
        for line in f:
            if line.startswith('>'):
                parts = line[1:].split()
                accession = parts[0]
                # Extract genus and species (first two words after accession)
                if len(parts) >= 3:
                    genus_species = f"{parts[1]} {parts[2]}"
                elif len(parts) == 2:
                    genus_species = parts[1]
                else:
                    genus_species = ''
                return accession, genus_species
    return '', ''

def parse_resfinder_results_table(table_path):
    """Parse Resfinder_results_table.txt to get a dict of class -> set of genes, and a list of (class, gene) hits."""
    genes_by_class = {}
    gene_hits = set()
    current_class = None
    with open(table_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if not '\t' in line and not line.endswith('found'):
                current_class = line
                genes_by_class.setdefault(current_class, set())
            elif line.endswith('No hit found'):
                continue
            elif current_class and not line.startswith('Resistance gene'):
                parts = line.split('\t')
                if parts and parts[0] != 'No hit found':
                    clean_gene = clean_gene_name(parts[0])
                    genes_by_class[current_class].add(clean_gene)
                    gene_hits.add((current_class, clean_gene))
    return genes_by_class, gene_hits

def parse_resfinder_results_txt(txt_path):
    """Parse Resfinder_results.txt to get a dict of class -> set of genes."""
    genes_by_class = {}
    current_class = None
    with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Look for class header
            if line.startswith('#####################') and line.endswith('#####################'):
                # e.g. '##################### aminoglycoside #####################'
                class_name = line.strip('#').strip().capitalize()
                current_class = class_name
                if current_class not in genes_by_class:
                    genes_by_class[current_class] = set()
            elif current_class and ',' in line and 'ID:' in line:
                # e.g. 'aph(6)-Id, ID: 99.88 %, ...'
                gene = line.split(',')[0].strip()
                clean_gene = clean_gene_name(gene)
                genes_by_class[current_class].add(clean_gene)
    return genes_by_class

def clean_gene_name(gene_name):
    """Extract clean gene name from database gene name."""
    # Remove accession numbers and other suffixes
    # Examples: blaBEL4_1_KX388629 -> blaBEL-4, blaCTX-M-64_1_AB284167 -> blaCTX-M-64
    
    # Split by underscore and take the first part
    clean_name = gene_name.split('_')[0]
    
    # Handle special cases for gene names with numbers
    # Convert patterns like blaBEL4 to blaBEL-4
    import re
    
    # Handle patterns like blaBEL4 -> blaBEL-4
    match = re.match(r'([a-zA-Z]+)(\d+)$', clean_name)
    if match:
        prefix, number = match.groups()
        clean_name = f"{prefix}-{number}"
    
    # Handle patterns like blaCTX-M64 -> blaCTX-M-64 (add dash before number)
    match = re.match(r'([a-zA-Z-]+)(\d+)$', clean_name)
    if match:
        prefix, number = match.groups()
        if not prefix.endswith('-'):
            clean_name = f"{prefix}-{number}"
    
    # Handle patterns like blaCTX-M-64 (already correct)
    # No change needed
    
    return clean_name

def get_all_class_gene_pairs_from_db(db_dir):
    class_gene_pairs = set()
    for fasta_file in Path(db_dir).glob('*.fsa'):
        # Skip the all.fsa file to avoid creating an "All" class
        if fasta_file.name == 'all.fsa':
            continue
        class_name = fasta_file.stem.replace('_', ' ').capitalize()
        with open(fasta_file, 'r') as f:
            for line in f:
                if line.startswith('>'):
                    gene = line[1:].split()[0]
                    clean_gene = clean_gene_name(gene)
                    class_gene_pairs.add((class_name, clean_gene))
    return class_gene_pairs

def extract_accession_from_url(url):
    """Extract accession number from NCBI FTP URL."""
    if not url:
        return ''
    
    # Handle different URL formats
    if 'ftp.ncbi.nlm.nih.gov' in url or 'ncbi.nlm.nih.gov' in url:
        # Extract from URL like https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/014/844/835/GCF_014844835.1_ASM1484483v1_genomic.fna.gz
        parts = url.split('/')
        # Sort parts by length (longest first) to prioritize longer accession patterns
        parts.sort(key=len, reverse=True)
        for part in parts:
            if part.startswith(('GCF_', 'GCA_', 'NZ_', 'CP', 'JA', 'JAI')):
                # Remove any file extensions
                accession = part.split('.')[0] if '.' in part else part
                return accession
    
    # If it's already just an accession number
    if url.startswith(('GCF_', 'GCA_', 'NZ_', 'CP', 'JA', 'JAI')):
        return url.split('.')[0] if '.' in url else url
    
    return url

def format_genus_species(genus, species=''):
    """Format genus and species consistently."""
    if not genus:
        return 'Unknown'
    
    # If genus already contains both genus and species, return as is
    if ' ' in genus and not species:
        return genus
    
    # Combine genus and species
    if species and species != 'Unknown':
        return f"{genus} {species}"
    else:
        return genus

def process_one_genome(genome, db_path, output_dir, blast_path):
    url = genome['url'] if isinstance(genome, dict) else genome
    provided_genus = genome.get('genus', '') if isinstance(genome, dict) else ''
    provided_species = genome.get('species', '') if isinstance(genome, dict) else ''
    
    try:
        fasta_path = download_and_decompress_fasta(url, output_dir)
        genome_name = Path(fasta_path).stem
        result_dir = output_dir / f"{genome_name}_resfinder"
        result_dir.mkdir(exist_ok=True)
        subprocess.run([
            "python", "resfinder/src/resfinder/run_resfinder.py",
            "--acquired",
            "-ifa", str(fasta_path),
            "-o", str(result_dir),
                "-l", "0.6",
                "-t", "0.9",
                "--blastPath", blast_path,
                "-db_res", db_path
            ], cwd=Path.cwd(), check=True)
        accession, genus_species = parse_fasta_header(fasta_path)
        
        # If parse_fasta_header didn't get good data, use provided data
        if not accession or accession == '':
            accession = extract_accession_from_url(url)
        if not genus_species or genus_species == '':
            genus_species = format_genus_species(provided_genus, provided_species)
        
        table_file = None
        for f in result_dir.iterdir():
            if f.is_file() and f.name.lower().startswith('resfinder_results_table'):
                table_file = f
                break
        txt_file = result_dir / "Resfinder_results.txt"
        genes_by_class, gene_hits = {}, set()
        if table_file and table_file.exists():
            genes_by_class, gene_hits = parse_resfinder_results_table(table_file)
        if (not genes_by_class or all(len(v) == 0 for v in genes_by_class.values())) and txt_file.exists():
            genes_by_class = parse_resfinder_results_txt(txt_file)
        return {
                'accession': accession,
            'genus': genus_species,
            'genes_by_class': genes_by_class,
            'url': url
        }
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] ResFinder subprocess failed for {url}: {e}")
        return {
            'accession': extract_accession_from_url(url), 
            'genus': format_genus_species(provided_genus, provided_species), 
            'genes_by_class': {}, 
            'url': url
        }
    except Exception as e:
        print(f"[ERROR] General failure for {url}: {e}")
        return {
            'accession': extract_accession_from_url(url), 
            'genus': format_genus_species(provided_genus, provided_species), 
            'genes_by_class': {}, 
            'url': url
        }

def run_resfinder(genome_list, output_file="resfinder_output.csv"):
    output_path = Path(output_file)
    output_dir = Path("resfinder_results")
    output_dir.mkdir(exist_ok=True)
    db_path = str(Path("resfinder/data/ResFinder").resolve())
    all_class_gene_pairs = get_all_class_gene_pairs_from_db(db_path)
    class_gene_columns = sorted(all_class_gene_pairs, key=lambda x: (x[0], x[1]))
    found_class_gene_pairs = set()
    blast_path = "C:/Users/Administrator/Desktop/NCBI/blast-2.16.0+/bin/blastn.exe"

    # Parallel processing of genomes
    results = []
    max_workers = min(multiprocessing.cpu_count(), 4)  # Limit to 4 threads to avoid overwhelming
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(process_one_genome, genome, db_path, output_dir, blast_path): genome for genome in genome_list}
        for future in as_completed(future_to_url):
            result = future.result()
            results.append(result)
            # Collect all found class/gene pairs for header
            for cls, genes in result['genes_by_class'].items():
                for gene in genes:
                    found_class_gene_pairs.add((cls, gene))

    # Only use found class/gene pairs - only include columns for genes that are actually present
    class_gene_columns = sorted(found_class_gene_pairs, key=lambda x: (x[0], x[1]))
    
    # Build a list of unique classes in order (only for classes that have found genes)
    classes = []
    genes_by_class_ordered = {}
    for cls, gene in class_gene_columns:
        if cls not in classes:
            classes.append(cls)
            genes_by_class_ordered[cls] = []
        genes_by_class_ordered[cls].append(gene)
    
    # Get all possible antibiotic classes from the database for consistent headers
    all_classes = set()
    for cls, _ in all_class_gene_pairs:
        all_classes.add(cls)
    all_classes = sorted(all_classes)
    
    if not classes:
        # No genes found, but show all antibiotic class headers with "None" values
        header = ["ACCESSION No.", "GENUS"]
        for cls in all_classes:
            header.extend([cls])
    else:
        # Single header: class names, spanning the number of genes in each class
        header = ["ACCESSION No.", "GENUS"]
        for cls in classes:
            header.extend([cls] + [""] * (len(genes_by_class_ordered[cls]) - 1))
    
    with output_path.open("w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)
        for row in results:
            row_data = [row['accession'], row['genus']]
            if classes:
                gene_presence = []
                for cls in classes:
                    for gene in genes_by_class_ordered[cls]:
                        present = gene if (cls in row['genes_by_class'] and gene in row['genes_by_class'][cls]) else ''
                        gene_presence.append(present)
                writer.writerow(row_data + gene_presence)
            else:
                # No genes found, add "None" for each antibiotic class
                none_values = ["None"] * len(all_classes)
                writer.writerow(row_data + none_values)
    return str(output_path)

