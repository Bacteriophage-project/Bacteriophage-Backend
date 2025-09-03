# Bacteriophage-Backend-
#Overview
This backend is a unified API service built with FastAPI to support bacterial genome analysis workflows. It enables fetching of genome assemblies from NCBI based on BioProject IDs, downloads and manages genomic FASTA files, and prepares structured data for frontend display or downstream analyses including antimicrobial resistance and virulence factor identification.

#Features
Fetch Genome Assemblies:
Retrieves assembly accessions and detailed metadata from NCBI Entrez APIs for a given BioProject ID.

#Data Parsing and Formatting:
Parses assembly summaries into enriched metadata including organism names, GC content, assembly levels, and formats descriptive summaries.

#Antimicrobial Resistance and Virulence Factor Analysis Integration:

#ResFinder: Detects acquired antimicrobial resistance genes and chromosomal mutations associated with resistance, using a comprehensive and curated database.

#Phastest: Planned integration for rapid identification of prophage sequences, which are important in bacterial evolution and virulence.

#VFDB (Virulence Factor Database): Planned integration to detect bacterial virulence factors, enhancing analysis of pathogenic potential.

#Consistent API Endpoints:
Provides REST endpoints for fetching assemblies and for submitting genomes for resistance and virulence analyses.

#Project Structure
All backend functionality is contained in these core modules:

#app.py
The FastAPI application defines API routes, handles requests, manages FASTA file storage, coordinates calls to genome fetching and parsing modules, and controls response formatting.

#fetch_genomes.py
Contains functions to:

Query NCBI Entrez for assembly IDs and summaries

Download FASTA files with overwrite and cleanup handling

Fetch assemblies and genomes for a BioProject ID with cleanup

Process assembly data for API responses

#parse_genome.py
Provides parsing utilities for assembly summaries and for future integration of ResFinder, Phastest, and VFDB API responses.

Usage
Start the backend server with Uvicorn:

bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
(Use the if __name__ == "__main__": guard on Windows.)

Configure CORS in app.py to allow your frontend origin.

Use the /assemblies endpoint to retrieve genome assemblies and download FASTA files by providing a valid BioProject ID.

Antimicrobial resistance and virulence factor analysis endpoints (e.g., /run_resfinder) will incorporate ResFinder, Phastest, and VFDB analyses as they are integrated.

#File Management Strategy
All downloaded FASTA files are stored in the dedicated folder FASTA_files.

The folder is cleared before downloading new data for a different BioProject, avoiding stale data overlap.

This ensures fixed and predictable genome file paths for downstream tools like ResFinder, Phastest, and VFDB.

#Dependencies
Python 3.13+

FastAPI

Uvicorn

Requests

FTP (standard library)
