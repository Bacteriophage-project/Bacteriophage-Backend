import streamlit as st
import pandas as pd
import os
import subprocess
from utils.ncbi_fetcher import get_genomes_from_bioproject
from utils.run_resfinder import run_resfinder
from utils.download_genomes import download_and_decompress_fasta
from utils.vfdb_blast import build_blast_db, aggregate_results
from utils.vfdb_excel_formatter import format_vfdb_matrix
import tempfile

st.title("Genome Analysis Tool")

# --- Input: BioProject ID ---
bioproject_id = st.text_input("Enter BioProject No/ID")

# --- Session State ---
if 'genome_urls' not in st.session_state:
    st.session_state['genome_urls'] = None
if 'amr_csv' not in st.session_state:
    st.session_state['amr_csv'] = None
if 'prophage_csv' not in st.session_state:
    st.session_state['prophage_csv'] = None
if 'phastest_attempted' not in st.session_state:
    st.session_state['phastest_attempted'] = False

# --- NCBI Fetch Button ---
if st.button("NCBI Fetch"):
    if bioproject_id:
        st.info(f"Fetching genome URLs for BioProject {bioproject_id}...")
        try:
            genomes = get_genomes_from_bioproject([bioproject_id])
            st.session_state['genome_urls'] = genomes
            st.success("NCBI Fetch completed. Check your results folder.")
            if genomes:
                st.markdown("**Genomes fetched:**")
                for genome in genomes:
                    st.write(f"{genome['url']} (Genus: {genome['genus']})")
            else:
                st.warning("No genomes found for this BioProject.")
        except Exception as e:
            st.error(f"NCBI Fetch failed: {e}")
            st.session_state['genome_urls'] = None
    else:
        st.warning("Please enter a BioProject No/ID.")

# --- Run ResFinder Button ---
if st.button("Run ResFinder"):
    genomes = st.session_state.get('genome_urls')
    if genomes:
        st.info("Running ResFinder (AMR)...")
        try:
            amr_csv = run_resfinder(genomes)
            if amr_csv and os.path.exists(amr_csv):
                st.session_state['amr_csv'] = amr_csv
                st.success("ResFinder completed.")
            else:
                st.session_state['amr_csv'] = None
                st.error("ResFinder did not produce an output CSV. Please check the script output and results folder.")
        except Exception as e:
            st.error(f"ResFinder failed: {e}")
            st.session_state['amr_csv'] = None
    else:
        st.warning("Please fetch genome URLs first.")

# --- Run PHASTEST Button ---
if st.button("Run PHASTEST"):
    st.session_state['phastest_attempted'] = True
    if st.session_state.get('genome_urls'):
        st.info("Running PHASTEST (Prophages)...")
        try:
            subprocess.run(["python", "utils/phastest_full_automation.py"], check=True)
            prophage_csv = "phastest_results/phastest_zip_output.csv"
            if os.path.exists(prophage_csv):
                st.session_state['prophage_csv'] = prophage_csv
                st.success("PHASTEST completed.")
            else:
                st.session_state['prophage_csv'] = None
                st.error("PHASTEST did not produce an output CSV. Please check the script output and results folder.")
        except subprocess.CalledProcessError:
            st.error("Ooops! PHASTEST server seems to be down, try again later.")
            st.session_state['prophage_csv'] = None
        except Exception as e:
            st.error(f"PHASTEST failed: {e}")
            st.session_state['prophage_csv'] = None
    else:
        st.warning("Please fetch genome URLs first.")

# --- Run VFDB Button ---
if st.button("Run VFDB"):
    genomes = st.session_state.get('genome_urls')
    if genomes:
        st.info("Running VFDB (Virulence Factors)...")
        try:
            from utils.download_genomes import download_and_decompress_fasta
            from utils.vfdb_blast import build_blast_db, aggregate_results
            from utils.vfdb_excel_formatter import format_vfdb_matrix
            import os
            output_dir = os.path.join(os.path.dirname(__file__), "vfdb_results")
            os.makedirs(output_dir, exist_ok=True)
            # Download/decompress FASTA files
            fasta_paths = []
            for genome in genomes:
                url = genome['url'] if isinstance(genome, dict) else genome
                fasta_path = download_and_decompress_fasta(url, output_dir)
                fasta_paths.append(fasta_path)
            # Run BLAST workflow
            build_blast_db()
            matrix_csv = os.path.join(output_dir, "vfdb_matrix.csv")
            aggregate_results(fasta_paths, matrix_csv, output_dir=output_dir)
            # Format Excel output
            mapping_csv = os.path.join(os.path.dirname(__file__), "utils", "vfdb_data", "vfdb_gene_category_mapping.csv")
            excel_out = os.path.join(output_dir, "vfdb_matrix_formatted.xlsx")
            format_vfdb_matrix(matrix_csv, mapping_csv, excel_out)
            st.session_state['vfdb_excel'] = excel_out
            st.success("VFDB analysis completed.")
        except Exception as e:
            st.session_state['vfdb_excel'] = None
            st.error(f"VFDB analysis failed: {e}")
    else:
        st.warning("Please fetch genome URLs first.")

# --- Results and Download Buttons ---
st.header("Results")

if st.session_state.get('amr_csv') and os.path.exists(st.session_state['amr_csv']):
    st.subheader("AMR (ResFinder)")
    try:
        amr_df = pd.read_csv(st.session_state['amr_csv'], header=[0,1])
        st.dataframe(amr_df)
        st.download_button("Download AMR CSV", open(st.session_state['amr_csv'], 'rb').read(), file_name=os.path.basename(st.session_state['amr_csv']))
    except Exception as e:
        st.error(f"Could not display AMR CSV: {e}")
else:
    st.info("No AMR results available.")

if st.session_state.get('prophage_csv') and os.path.exists(st.session_state['prophage_csv']):
    st.subheader("Prophages (PHASTEST)")
    try:
        prophage_df = pd.read_csv(st.session_state['prophage_csv'])
        st.dataframe(prophage_df)
        st.download_button("Download Prophage CSV", open(st.session_state['prophage_csv'], 'rb').read(), file_name=os.path.basename(st.session_state['prophage_csv']))
    except Exception as e:
        st.error(f"Could not display Prophage CSV: {e}")
else:
    if st.session_state.get('phastest_attempted'):
        st.error("PHASTEST server is currently unavailable. Please try again later.")
    else:
        st.info("No Prophage results available.")

# --- VFDB Results and Download Button ---
if st.session_state.get('vfdb_excel') and os.path.exists(st.session_state['vfdb_excel']):
    st.subheader("Virulence Factors (VFDB)")
    st.download_button("Download VFDB Excel", open(st.session_state['vfdb_excel'], 'rb').read(), file_name=os.path.basename(st.session_state['vfdb_excel']))
else:
    st.info("No VFDB results available.") 