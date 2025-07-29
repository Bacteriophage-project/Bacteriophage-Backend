import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import csv
import json
import subprocess
from pathlib import Path
from utils.download_genomes import download_and_decompress_fasta
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing


def parse_fasta_header(fasta_path):
    """Extract accession and genus from the first header line of a FASTA file."""
    with open(fasta_path, 'r') as f:
        for line in f:
            if line.startswith('>'):
                parts = line[1:].split()
                accession = parts[0]
                genus = parts[1] if len(parts) > 1 else ''
                return accession, genus
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
                    genes_by_class[current_class].add(parts[0])
                    gene_hits.add((current_class, parts[0]))
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
                genes_by_class[current_class].add(gene)
    return genes_by_class

def get_all_class_gene_pairs_from_db(db_dir):
    class_gene_pairs = set()
    for fasta_file in Path(db_dir).glob('*.fsa'):
        class_name = fasta_file.stem.replace('_', ' ').capitalize()
        with open(fasta_file, 'r') as f:
            for line in f:
                if line.startswith('>'):
                    gene = line[1:].split()[0]
                    class_gene_pairs.add((class_name, gene))
    return class_gene_pairs

def process_one_genome(genome, db_path, output_dir, blast_path):
    url = genome['url'] if isinstance(genome, dict) else genome
    provided_genus = genome.get('genus', '') if isinstance(genome, dict) else ''
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
        accession, _ = parse_fasta_header(fasta_path)
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
            'genus': provided_genus,
            'genes_by_class': genes_by_class,
            'url': url
        }
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] ResFinder subprocess failed for {url}: {e}")
        return {'accession': url, 'genus': provided_genus, 'genes_by_class': {}, 'url': url}
    except Exception as e:
        print(f"[ERROR] General failure for {url}: {e}")
        return {'accession': url, 'genus': provided_genus, 'genes_by_class': {}, 'url': url}
        return {'accession': url, 'genus': provided_genus, 'genes_by_class': {}, 'url': url}

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
    max_workers = multiprocessing.cpu_count()
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(process_one_genome, genome, db_path, output_dir, blast_path): genome for genome in genome_list}
        for future in as_completed(future_to_url):
            result = future.result()
            results.append(result)
            # Collect all found class/gene pairs for header
            for cls, genes in result['genes_by_class'].items():
                for gene in genes:
                    found_class_gene_pairs.add((cls, gene))

    # Only keep columns for genes found in at least one genome
    class_gene_columns = sorted(found_class_gene_pairs, key=lambda x: (x[0], x[1]))
    # Build a list of unique classes in order
    classes = []
    genes_by_class_ordered = {}
    for cls, gene in class_gene_columns:
        if cls not in classes:
            classes.append(cls)
            genes_by_class_ordered[cls] = []
        genes_by_class_ordered[cls].append(gene)
    # First header: class names, spanning the number of genes in each class
    header_class = ["ACCESION No.", "GENUS"]
    for cls in classes:
        header_class.extend([cls] + [""] * (len(genes_by_class_ordered[cls]) - 1))
    # Second header: gene names
    header_gene = ["", ""]
    for cls in classes:
        header_gene.extend(genes_by_class_ordered[cls])
    with output_path.open("w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header_class)
        writer.writerow(header_gene)
        for row in results:
            row_data = [row['accession'], row['genus']]
            gene_presence = []
            for cls in classes:
                for gene in genes_by_class_ordered[cls]:
                    present = gene if (cls in row['genes_by_class'] and gene in row['genes_by_class'][cls]) else ''
                    gene_presence.append(present)
                    
            writer.writerow(row_data + gene_presence)
    return str(output_path)

