import os
import requests
import pandas as pd
import gzip
import shutil
import re

VFDB_CORE_FASTA_URL = "http://www.mgc.ac.cn/VFs/Down/VFDB_setA_nt.fas.gz"
VFDB_VFS_XLS_GZ_URL = "https://www.mgc.ac.cn/VFs/Down/VFs.xls.gz"
DATA_DIR = os.path.join(os.path.dirname(__file__), "vfdb_data")
FASTA_PATH = os.path.join(DATA_DIR, "VFDB_setA_nt.fas.gz")
FASTA_UNZIPPED = os.path.join(DATA_DIR, "VFDB_setA_nt.fas")
GENE_CATEGORY_CSV = os.path.join(DATA_DIR, "vfdb_gene_category_mapping.csv")
VFS_XLS_GZ_PATH = os.path.join(DATA_DIR, "VFs.xls.gz")
VFS_XLS_PATH = os.path.join(DATA_DIR, "VFs.xls")
VFGID_GENE_CATEGORY_CSV = os.path.join(DATA_DIR, "vfdb_vfgid_gene_category_mapping.csv")

os.makedirs(DATA_DIR, exist_ok=True)

def download_file(url, dest):
    if os.path.exists(dest):
        print(f"File already exists: {dest}")
        return
    print(f"Downloading {url} ...")
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with open(dest, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"Downloaded to {dest}")

def extract_vfgid_gene_category_mapping(fasta_gz, xls_path, output_csv):
    # Unzip FASTA if needed
    if not os.path.exists(FASTA_UNZIPPED):
        with gzip.open(fasta_gz, 'rb') as f_in:
            with open(FASTA_UNZIPPED, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
    # Parse FASTA headers for VFG IDs and descriptions
    vfgid_list = []
    desc_list = []
    with open(FASTA_UNZIPPED, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('>'):
                m = re.match(r'>?(VFG\d+)\s+(.+?)\s*\[(.+)\]', line.strip())
                if m:
                    vfgid, gene_desc, cat = m.groups()
                    vfgid_list.append(vfgid)
                    desc_list.append(gene_desc)
    # Load Excel and build mapping from description to VFID, VF_Name, VFcategory
    df_xls = pd.read_excel(xls_path, header=1)
    # Try to match by VF_FullName or VF_Name
    desc_to_vfid = {}
    desc_to_gene = {}
    desc_to_cat = {}
    for _, row in df_xls.iterrows():
        desc = str(row.get('VF_FullName', '')).strip()
        gene = str(row.get('VF_Name', '')).strip()
        cat = str(row.get('VFcategory', '')).strip()
        vfid = str(row.get('VFID', '')).strip()
        if desc:
            desc_to_vfid[desc] = vfid
            desc_to_gene[desc] = gene
            desc_to_cat[desc] = cat
        # Also allow matching by gene name if unique
        if gene and gene not in desc_to_gene:
            desc_to_gene[gene] = gene
            desc_to_cat[gene] = cat
            desc_to_vfid[gene] = vfid
    # Build mapping
    vfid_out, gene_out, cat_out = [], [], []
    for vfgid, desc in zip(vfgid_list, desc_list):
        vfid = desc_to_vfid.get(desc, '')
        gene = desc_to_gene.get(desc, desc)  # fallback to description
        cat = desc_to_cat.get(desc, 'Unknown')
        vfid_out.append(vfid)
        gene_out.append(gene)
        cat_out.append(cat)
    df = pd.DataFrame({'vfg_id': vfgid_list, 'vfid': vfid_out, 'gene': gene_out, 'category': cat_out})
    df.to_csv(output_csv, index=False)
    print(f"VFG ID-gene-category mapping (with best match) saved to {output_csv}")

def main():
    download_file(VFDB_CORE_FASTA_URL, FASTA_PATH)
    if not os.path.exists(VFS_XLS_PATH):
        print(f"VFs.xls not found, downloading and extracting...")
        download_file(VFDB_VFS_XLS_GZ_URL, VFS_XLS_GZ_PATH)
        with gzip.open(VFS_XLS_GZ_PATH, 'rb') as f_in:
            with open(VFS_XLS_PATH, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        print(f"Extracted {VFS_XLS_GZ_PATH} to {VFS_XLS_PATH}")
    extract_vfgid_gene_category_mapping(FASTA_PATH, VFS_XLS_PATH, VFGID_GENE_CATEGORY_CSV)
    # For legacy, also save gene-category mapping
    df = pd.read_csv(VFGID_GENE_CATEGORY_CSV)
    df[['gene', 'category']].drop_duplicates().to_csv(GENE_CATEGORY_CSV, index=False)
    print("\nSetup complete!")
    print(f"VFDB FASTA: {FASTA_PATH}")
    print(f"Gene-category mapping: {GENE_CATEGORY_CSV}")
    print(f"VFGID-gene-category mapping: {VFGID_GENE_CATEGORY_CSV}")

if __name__ == "__main__":
    main() 