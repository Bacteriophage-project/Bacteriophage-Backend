import os
import csv
import requests
from pathlib import Path
from utils.download_genomes import download_and_decompress_fasta
import zipfile
import shutil
import json
import time

def is_valid_fasta(fasta_path):
    try:
        with open(fasta_path, 'r') as f:
            first_line = f.readline()
            if not first_line.startswith('>'):
                return False
            # Check for at least one sequence line
            for line in f:
                if line.strip() and not line.startswith('>'):
                    return True
        return False
    except Exception:
        return False

def submit_and_download_phastest(fasta_files, zip_folder="phastest_results", output_csv="phastest_zip_output.csv"):
    """
    For each local FASTA file, submit to PHASTEST API, poll for status, download the result zip, and parse all zips.
    If the API is under maintenance or cluster is unreachable, abort immediately and inform the user.
    """
    import re
    os.makedirs(zip_folder, exist_ok=True)
    session = requests.Session()
    
    for i, fasta_path in enumerate(fasta_files):
        # Submit to PHASTEST API
        with open(fasta_path, 'rb') as f:
            resp = session.post("https://phastest.ca/phastest_api", files={"file": (os.path.basename(fasta_path), f, "application/octet-stream")})
        resp.raise_for_status()
        resp_json = resp.json()
        job_id = resp_json.get("job_id")
        error_msg = resp_json.get("error", "")
        
        if not job_id:
            print(f"❌ No job_id returned for {fasta_path}: {resp_json}")
            # If this is the first file and the error indicates maintenance or cluster issue, abort immediately
            if i == 0 and ("maintenance" in error_msg.lower() or "cluster" in error_msg.lower() or "try again later" in error_msg.lower()):
                raise RuntimeError(error_msg.strip())
            continue
        
        print(f"Submitted {fasta_path} as job {job_id}")
        
        # Poll for status and result
        for attempt in range(60):  # Wait up to ~10 minutes
            status_resp = session.get(f"https://phastest.ca/phastest_api?acc={job_id}")
            status_resp.raise_for_status()
            status_json = status_resp.json()
            status = status_json.get("status", "")
            
            if status.lower().startswith("complete") or status.lower() == "complete":
                zip_url = status_json.get("zip")
                if zip_url:
                    if not zip_url.startswith("http"):
                        zip_url = "https://phastest.ca/" + zip_url.lstrip("/")
                    zip_path = os.path.join(zip_folder, f"{job_id}.PHASTEST.zip")
                    zip_file_resp = session.get(zip_url)
                    if zip_file_resp.status_code == 200:
                        with open(zip_path, 'wb') as zf:
                            zf.write(zip_file_resp.content)
                        print(f"✅ Downloaded {zip_path}")
                    else:
                        print(f"❌ Failed to download zip for {job_id} from {zip_url}")
                else:
                    print(f"❌ No zip URL in result for {job_id}: {status_json}")
                break
            elif status_json.get("error"):
                print(f"❌ Error for {job_id}: {status_json['error']}")
                # If this is the first file and the error indicates maintenance or cluster issue, abort immediately
                if i == 0 and ("maintenance" in status_json['error'].lower() or "cluster" in status_json['error'].lower() or "try again later" in status_json['error'].lower()):
                    raise RuntimeError(status_json['error'].strip())
                break
            else:
                print(f"Job {job_id} status: {status}")
                time.sleep(10)
        else:
            print(f"❌ Timed out waiting for PHASTEST result for {fasta_path} (job {job_id})")
    
    # Parse all zip files (do not delete zip or extract files)
    parse_phastest_zip_folder(zip_folder=zip_folder, output_file=output_csv)
    # (No deletion of .PHASTEST.zip or extraction folders)

def parse_fasta_header_for_prophage(fasta_path):
    accession = strain = genus = ''
    with open(fasta_path, 'r') as f:
        for line in f:
            if line.startswith('>'):
                parts = line[1:].split()
                accession = parts[0]
                if len(parts) > 1:
                    strain = parts[1]
                if len(parts) > 2:
                    genus = parts[2]
                break
    return accession, strain, genus

def parse_phastest_zip_folder(zip_folder="phastest_results", output_file="phastest_zip_output.csv", excel_path=None, excel_sheet_name=None):
    """
    Process all .PHASTEST.zip files in the given folder, extract and parse predicted_phage_regions.json,
    count intact/incomplete/questionable prophages, extract accession/genus/strain, and output a CSV.
    Optionally merge into an Excel file and sheet if excel_path and excel_sheet_name are provided.
    """
    import pandas as pd
    all_records = []
    extract_path = os.path.join(zip_folder, "PHASTEST_EXTRACT")
    zip_files = [f for f in os.listdir(zip_folder) if os.path.isfile(os.path.join(zip_folder, f)) and f.endswith('.PHASTEST.zip')]
    print(f"Found {len(zip_files)} PHASTEST zip files in {zip_folder}")
    for zip_file in zip_files:
        zip_path = os.path.join(zip_folder, zip_file)
        submission_id = zip_file.replace(".PHASTEST.zip", "")
        link = f"https://phastest.ca/submissions/{submission_id}"
        # Create and clear extract_path for each zip
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
        os.makedirs(extract_path, exist_ok=True)
        print(f"Processing {zip_file}...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        json_path = os.path.join(extract_path, "predicted_phage_regions.json")
        if not os.path.exists(json_path):
            print(f"❌ predicted_phage_regions.json not found in {zip_file}")
            continue
        else:
            print(f"✅ Found predicted_phage_regions.json in {zip_file}")
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
        print(f"Accession: {accession}, Intact: {intact}, Incomplete: {incomplete}, Questionable: {questionable}, Total: {total}")
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
    print(f"DataFrame before filtering: {len(df_new)} rows")
    if not df_new.empty and "Accession No" in df_new.columns:
        df_new = df_new[df_new["Accession No"].str.match(r"^(CP|NZ|JA|JAI)", na=False)]
    print(f"DataFrame after filtering: {len(df_new)} rows")
    if excel_path and excel_sheet_name:
        try:
            df_existing = pd.read_excel(excel_path, sheet_name=excel_sheet_name)
            print(f"Existing Excel sheet rows: {len(df_existing)}")
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        except (ValueError, FileNotFoundError):
            df_combined = df_new
        print(f"Combined DataFrame rows: {len(df_combined)}")
        with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_combined.to_excel(writer, sheet_name=excel_sheet_name, index=False)
        print(f"✅ Successfully processed {len(zip_files)} PHASTEST zip files. Saved to '{excel_sheet_name}' sheet in {os.path.basename(excel_path)}.")
    df_new.to_csv(output_file, index=False)
    print(f"✅ Saved results to {output_file}.")

def automate_phastest_with_selenium(fasta_folder="phastest_results", download_dir=None, output_file="phastest_zip_output.csv", excel_path=None, excel_sheet_name=None, headless=False):
    """
    Automate PHASTEST submission and download using Selenium for all .fna files in fasta_folder.
    Downloads .PHASTEST.zip files to download_dir (defaults to fasta_folder), then parses them.
    """
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    import time
    import os

    if download_dir is None:
        download_dir = fasta_folder

    chrome_options = Options()
    chrome_options.add_experimental_option("prefs", {
        "download.default_directory": os.path.abspath(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    })
    if headless:
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')

    driver = webdriver.Chrome(options=chrome_options)

    try:
        fasta_files = [os.path.join(fasta_folder, f) for f in os.listdir(fasta_folder) if f.endswith('.fna')]
        for fasta_file in fasta_files:
            print(f"Processing {fasta_file}...")
            driver.get("https://phastest.ca/submissions")
            time.sleep(2)

            # Upload the FASTA file
            file_input = driver.find_element(By.NAME, "submission[sequence]")
            file_input.send_keys(fasta_file)
            time.sleep(1)

            # Submit the form
            submit_btn = driver.find_element(By.XPATH, "//input[@type='submit' and @value='Submit']")
            submit_btn.click()
            print("Submitted file, waiting for results...")

            # Wait for the results page and the download link
            for _ in range(60):  # Wait up to 5 minutes
                time.sleep(5)
                links = driver.find_elements(By.PARTIAL_LINK_TEXT, ".PHASTEST.zip")
                if links:
                    zip_link = links[0]
                    zip_url = zip_link.get_attribute("href")
                    print(f"Found zip link: {zip_url}")
                    zip_link.click()
                    print("Downloading zip file...")
                    time.sleep(10)  # Wait for download to complete
                    break
            else:
                print("❌ Timed out waiting for PHASTEST zip file.")
    finally:
        driver.quit()

    print("All genomes processed. Now parsing downloaded zip files...")
    parse_phastest_zip_folder(zip_folder=download_dir, output_file=output_file, excel_path=excel_path, excel_sheet_name=excel_sheet_name)