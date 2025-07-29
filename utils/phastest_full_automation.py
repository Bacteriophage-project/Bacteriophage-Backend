import os
import time
import requests
import zipfile
import shutil
import json
import pandas as pd
import sys
import subprocess
import pathlib

# === USER CONFIGURATION (EDIT THESE VARIABLES) ===

# Folder containing your .fna files (now set to resfinder_results)
fna_folder = os.path.join(os.path.dirname(__file__), '..', 'resfinder_results')
fna_folder = os.path.abspath(fna_folder)

# Folder to save downloaded .PHASTEST.zip files and Excel output
phastest_folder = os.path.join(os.path.dirname(__file__), '..', 'phastest_results')
phastest_folder = os.path.abspath(phastest_folder)

# Name of your Excel file (optional, for merging results)
excel_filename = "Phastest.xlsx"  # <-- CHANGE THIS IF NEEDED
excel_sheet_name = "Prophages"    # <-- CHANGE THIS IF NEEDED

# === END USER CONFIGURATION ===

# === PATHS ===
excel_path = os.path.join(phastest_folder, excel_filename)
API_URL = "https://phastest.ca/phastest_api"


def preprocess_fna_file(fna_path):
    # Read as bytes to check for BOM and leading whitespace
    with open(fna_path, 'rb') as f:
        content = f.read()
    # Remove UTF-8 BOM if present
    if content.startswith(b'\xef\xbb\xbf'):
        content = content[3:]
    # Convert to text for line processing
    lines = content.decode('utf-8', errors='replace').splitlines()
    changed = False
    # Remove leading blank lines
    while lines and not lines[0].strip():
        lines.pop(0)
        changed = True
    # Remove leading whitespace before '>'
    if lines and not lines[0].startswith('>'):
        lines[0] = lines[0].lstrip()
        changed = True
    if lines and not lines[0].startswith('>'):
        print(f"Warning: {fna_path} first line does not start with '>' even after stripping whitespace.")
    # Write back if changed
    if changed:
        with open(fna_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
        print(f"Fixed file: {fna_path}")

def submit_fna(fna_path):
    preprocess_fna_file(fna_path)
    with open(fna_path, 'rb') as f:
        response = requests.post(API_URL, data=f.read())  # Send as raw body, not multipart
    try:
        data = response.json()
    except Exception:
        print(f"Non-JSON response for {fna_path}: {response.text}")
        return None
    print(f"Submission response for {os.path.basename(fna_path)}: {data}")  # DEBUG
    if 'job_id' in data:
        return data['job_id']
    else:
        print(f"Error submitting {fna_path}: {data.get('error')}")
        return None

def poll_job(job_id):
    while True:
        r = requests.get(API_URL, params={'acc': job_id})
        try:
            data = r.json()
        except Exception:
            print(f"Error: Non-JSON response for job {job_id}: {r.text}")
            return None
        if 'status' in data:
            print(f"Job {job_id} status: {data['status']}")
            if data['status'].lower().startswith('complete') and 'zip' in data:
                return data['zip']
        elif 'error' in data:
            print(f"Error for job {job_id}: {data['error']}")
            return None
        else:
            print(f"Unexpected response for job {job_id}: {data}")
            return None
        time.sleep(30)  # Wait 30 seconds before polling again

def download_zip(zip_url, out_path):
    if not zip_url.startswith("http"):
        zip_url = "https://" + zip_url
    r = requests.get(zip_url)
    with open(out_path, 'wb') as f:
        f.write(r.content)

def parse_phastest_zips():
    """
    Parse all .PHASTEST.zip files in phastest_folder and merge results into Excel.
    """
    extract_path = os.path.join(phastest_folder, "PHASTEST_EXTRACT")
    zip_files = [
        f for f in os.listdir(phastest_folder)
        if os.path.isfile(os.path.join(phastest_folder, f)) and f.endswith('.PHASTEST.zip')
    ]
    all_records = []
    for zip_file in zip_files:
        zip_path = os.path.join(phastest_folder, zip_file)
        submission_id = zip_file.replace(".PHASTEST.zip", "")
        link = f"https://phastest.ca/submissions/{submission_id}"
        # Create and clear extract_path for each zip
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
        os.makedirs(extract_path, exist_ok=True)
        # Extract zip
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        json_path = os.path.join(extract_path, "predicted_phage_regions.json")
        if not os.path.exists(json_path):
            print(f"❌ predicted_phage_regions.json not found in {zip_file}")
            continue
        with open(json_path, 'r') as f:
            try:
                phage_data = json.load(f)
            except json.JSONDecodeError:
                print(f"❌ Invalid JSON in {zip_file}")
                continue
        intact = incomplete = questionable = 0
        genus = "Unknown"
        strain = "Unknown"
        accession = "Unknown"
        for region in phage_data:
            completeness = region.get("completeness", "").lower()
            if completeness == "intact":
                intact += 1
            elif completeness == "incomplete":
                incomplete += 1
            elif completeness == "questionable":
                questionable += 1
            contig_tag = region.get("contig_tag", "")
            if contig_tag:
                parts = [p.strip() for p in contig_tag.split(",")]
                if parts:
                    accession = parts[0]
                if len(parts) >= 3:
                    genus = f"{parts[1]} {parts[2]}"
                try:
                    strain_index = parts.index("strain")
                    if strain_index + 1 < len(parts):
                        strain = parts[strain_index + 1]
                except ValueError:
                    pass
        total = intact + incomplete + questionable
        all_records.append({
            "Accession No": accession,
            "Genus": genus,
            "Strain": strain,
            "Intact": intact,
            "Incomplete": incomplete,
            "Questionable": questionable,
            "Total Prophages": total,
            "Link": link
        })
    # Clean up extract_path after all parsing
    if os.path.exists(extract_path):
        shutil.rmtree(extract_path)
    df_new = pd.DataFrame(all_records)
    # Filter valid accession numbers
    if not df_new.empty and "Accession No" in df_new.columns:
        df_new = df_new[df_new["Accession No"].str.match(r"^(CP|NZ|JA|JAI)", na=False)]
    # Load existing Excel data and merge
    if not df_new.empty:
        excel_exists = os.path.exists(excel_path)
        if not excel_exists:
            with pd.ExcelWriter(excel_path, engine='openpyxl', mode='w') as writer:
                df_new.head(0).to_excel(writer, sheet_name=excel_sheet_name, index=False)
        try:
            df_existing = pd.read_excel(excel_path, sheet_name=excel_sheet_name)
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        except (ValueError, FileNotFoundError):
            df_combined = df_new
        with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_combined.to_excel(writer, sheet_name=excel_sheet_name, index=False)
        print(f"✅ Successfully processed {len(zip_files)} PHASTEST zip files. Saved to '{excel_sheet_name}' sheet in {excel_filename}.")
    else:
        print("No results to write to Excel.")

if __name__ == "__main__":
    print("=== PHASTEST API AUTOMATION START ===")
    fna_files = [f for f in os.listdir(fna_folder) if f.endswith('.fna')]
    print(f"Found {len(fna_files)} .fna files to submit.")
    for idx, fna_file in enumerate(fna_files):
        fna_path = os.path.join(fna_folder, fna_file)
        preprocess_fna_file(fna_path)
        print(f"Submitting {fna_file} to PHASTEST API...")
        job_id = submit_fna(fna_path)
        if not job_id:
            print(f"[PHASTEST] Submission failed for {fna_file}. PHASTEST server is currently unavailable. Please try again later.")
            sys.exit(1)
        zip_url = poll_job(job_id)
        if zip_url:
            out_zip = os.path.join(phastest_folder, f"{os.path.splitext(fna_file)[0]}.PHASTEST.zip")
            download_zip(zip_url, out_zip)
            print(f"Downloaded results for {fna_file} to {out_zip}")
        else:
            print(f"[PHASTEST] Failed to get results for {fna_file}. PHASTEST server is currently unavailable. Please try again later.")
            sys.exit(1)
    print("--- Parsing downloaded PHASTEST zip files ---")
    parse_phastest_zips() 