import os
import csv
import subprocess
from pathlib import Path
from utils.download_genomes import download_and_decompress_fasta
import pandas as pd

def calc_kb_gc(fasta_path):
    bases = 0
    gc = 0
    with open(fasta_path, 'r') as f:
        for line in f:
            if line.startswith('>'):
                continue
            seq = line.strip().upper()
            bases += len(seq)
            gc += seq.count('G') + seq.count('C')
    kb = bases / 1000 if bases else 0
    gc_pct = (gc / bases * 100) if bases else 0
    return round(kb, 1), round(gc_pct, 2)

def get_genus_from_fasta(fasta_path):
    with open(fasta_path, 'r') as f:
        for line in f:
            if line.startswith('>'):
                parts = line[1:].split()
                if len(parts) > 1:
                    return parts[1]
                return ''
    return ''

def run_vfdb(genome_urls, output_file="vfdb_output.csv"):
    output_path = Path(output_file)
    output_dir = Path("vfdb_results")
    output_dir.mkdir(exist_ok=True)

    all_genes = set()
    genome_rows = []

    for url in genome_urls:
        try:
            fasta_path = download_and_decompress_fasta(url, output_dir)
            genome_name = Path(fasta_path).stem
            result_file = output_dir / f"{genome_name}_vfdb.tsv"

            # Run abricate with VFDB
            subprocess.run([
                "abricate", "--db", "vfdb", str(fasta_path), "-o", str(result_file)
            ], check=True)

            # Parse abricate TSV output
            if result_file.exists():
                df = pd.read_csv(result_file, sep='\t', comment='#')
                genes = set(df['GENE']) if 'GENE' in df.columns else set()
                all_genes.update(genes)
            else:
                print(f"[WARN] No abricate output for {genome_name}")
                genes = set()
            # Metadata
            genus = get_genus_from_fasta(fasta_path)
            kb, gc_pct = calc_kb_gc(fasta_path)
            genome_rows.append({
                'genome': genome_name,
                'prophage': '',
                'host_genus': genus,
                'kb': kb,
                'gc_pct': gc_pct,
                'first_gene': '',
                'genes': genes
            })
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] ABRicate failed for {url}: {e}")
            genome_rows.append({'genome': url, 'prophage': '', 'host_genus': '', 'kb': '', 'gc_pct': '', 'first_gene': '', 'genes': set(), 'error': str(e)})
        except Exception as e:
            print(f"[ERROR] General failure for {url}: {e}")
            genome_rows.append({'genome': url, 'prophage': '', 'host_genus': '', 'kb': '', 'gc_pct': '', 'first_gene': '', 'genes': set(), 'error': str(e)})

    # Build matrix
    all_genes = sorted(all_genes)
    with output_path.open("w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        header = ["GENOME", "Prophage", "Host genus", "KB", "GC%", "First gene"] + all_genes
        writer.writerow(header)
        for row in genome_rows:
            row_data = [row['genome'], row['prophage'], row['host_genus'], row['kb'], row['gc_pct'], row['first_gene']]
            for gene in all_genes:
                row_data.append(1 if gene in row['genes'] else 0)
            writer.writerow(row_data)

    return str(output_path) 
