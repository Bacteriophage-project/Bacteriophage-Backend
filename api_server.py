from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import subprocess
import tempfile
import shutil
import pandas as pd
from pathlib import Path
import json
import threading
import time
from datetime import datetime, timedelta
import glob
import sqlite3
import requests
import zipfile

class JobStatus:
    def __init__(self, job_id, job_type):
        self.job_id = job_id
        self.job_type = job_type
        self.status = "pending"  # pending, running, completed, failed
        self.progress = 0
        self.result = None
        self.error = None
        self.created_at = datetime.now()
        self.completed_at = None

# Import your existing utilities
from utils.ncbi_fetcher import get_genomes_from_bioproject
from utils.run_resfinder import run_resfinder
from utils.download_genomes import download_and_decompress_fasta
from utils.vfdb_blast import build_blast_db, aggregate_results
from utils.vfdb_excel_formatter import format_vfdb_matrix
from utils.run_phastest import submit_and_download_phastest, parse_phastest_zip_folder

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

# Global storage for job status and results
jobs = {}
job_counter = 0

DB_PATH = 'jobs.sqlite3'

# Initialize SQLite DB and jobs table
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    job_type TEXT,
    status TEXT,
    progress INTEGER,
    result TEXT,
    error TEXT,
    created_at TEXT,
    completed_at TEXT
)''')
conn.commit()

def cleanup_old_jobs():
    import datetime
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=31)).isoformat()
    c.execute('DELETE FROM jobs WHERE created_at < ?', (cutoff,))
    conn.commit()

def cleanup_temp_files():
    """Clean up temporary files older than X days"""
    try:
        cutoff_date = datetime.now() - timedelta(days=7)  # Keep files for 7 days
        print(f"🧹 Starting cleanup of files older than {cutoff_date}")
        
        # Directories to clean
        directories_to_clean = [
            'resfinder_results',
            'phastest_results', 
            'vfdb_results',
            'temp_downloads'
        ]
        
        total_cleaned = 0
        
        for directory in directories_to_clean:
            if os.path.exists(directory):
                for file in os.listdir(directory):
                    file_path = os.path.join(directory, file)
                    if os.path.isfile(file_path):
                        try:
                            file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                            if file_time < cutoff_date:
                                os.remove(file_path)
                                total_cleaned += 1
                                print(f"🗑️ Cleaned up: {file_path}")
                        except Exception as e:
                            print(f"⚠️ Error cleaning {file_path}: {e}")
        
        print(f"✅ Cleanup completed. Removed {total_cleaned} files.")
        
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")

def start_cleanup_scheduler():
    """Background thread for scheduled cleanup"""
    while True:
        try:
            # Run cleanup every day at 2 AM
            now = datetime.now()
            if now.hour == 2 and now.minute == 0:
                cleanup_temp_files()
            time.sleep(3600)  # Check every hour
        except Exception as e:
            print(f"❌ Error in cleanup scheduler: {e}")
            time.sleep(3600)

# Start cleanup thread
cleanup_thread = threading.Thread(target=start_cleanup_scheduler, daemon=True)
cleanup_thread.start()

cleanup_old_jobs()

# Helper functions for DB jobs
import json as _json

def save_job_to_db(job):
    c.execute('''REPLACE INTO jobs (job_id, job_type, status, progress, result, error, created_at, completed_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (job.job_id, job.job_type, job.status, job.progress, _json.dumps(job.result), job.error, job.created_at.isoformat(), job.completed_at.isoformat() if job.completed_at else None))
    conn.commit()

def delete_job_from_db(job_id):
    c.execute('DELETE FROM jobs WHERE job_id = ?', (job_id,))
    conn.commit()

def load_jobs_from_db():
    jobs.clear()
    for row in c.execute('SELECT * FROM jobs'):
        job = JobStatus(row[0], row[1])
        job.status = row[2]
        job.progress = row[3]
        job.result = _json.loads(row[4]) if row[4] else None
        job.error = row[5]
        from datetime import datetime
        job.created_at = datetime.fromisoformat(row[6])
        job.completed_at = datetime.fromisoformat(row[7]) if row[7] else None
        jobs[job.job_id] = job

load_jobs_from_db()

def safe_serialize(obj):
    """Safely serialize objects that might contain non-JSON-serializable data"""
    if isinstance(obj, dict):
        return {str(k): safe_serialize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [safe_serialize(item) for item in obj]
    elif isinstance(obj, (pd.DataFrame, pd.Series)):
        return obj.to_dict('records') if hasattr(obj, 'to_dict') else str(obj)
    elif isinstance(obj, (tuple, set)):
        return str(obj)
    elif hasattr(obj, '__dict__'):
        return str(obj)
    else:
        return obj

def create_job(job_type):
    global job_counter
    job_counter += 1
    job_id = f"job_{job_counter}_{int(time.time())}"
    jobs[job_id] = JobStatus(job_id, job_type)
    save_job_to_db(jobs[job_id])
    return job_id

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route('/api/fetch-genomes', methods=['POST'])
def fetch_genomes():
    """Fetch genomes from NCBI using BioProject ID"""
    try:
        data = request.get_json()
        bioproject_id = data.get('bioproject_id')
        
        if not bioproject_id:
            return jsonify({"error": "BioProject ID is required"}), 400
        
        # Create job for tracking
        job_id = create_job("fetch_genomes")
        jobs[job_id].status = "running"
        
        def fetch_task():
            try:
                genomes = get_genomes_from_bioproject([bioproject_id])
                jobs[job_id].status = "completed"
                jobs[job_id].result = {
                    "genomes": genomes,
                    "count": len(genomes) if genomes else 0
                }
                jobs[job_id].completed_at = datetime.now()
                save_job_to_db(jobs[job_id])
            except Exception as e:
                jobs[job_id].status = "failed"
                jobs[job_id].error = str(e)
                jobs[job_id].completed_at = datetime.now()
                save_job_to_db(jobs[job_id])
        
        # Run in background
        thread = threading.Thread(target=fetch_task)
        thread.start()
        
        return jsonify({
            "job_id": job_id,
            "message": "Genome fetching started",
            "status": "pending"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/run-resfinder', methods=['POST'])
def run_resfinder_api():
    """Run ResFinder analysis on genome URLs"""
    try:
        data = request.get_json()
        genome_urls = data.get('genome_urls')
        
        if not genome_urls:
            return jsonify({"error": "Genome URLs are required"}), 400
        
        # Create job for tracking
        job_id = create_job("resfinder")
        jobs[job_id].status = "running"
        
        def resfinder_task():
            try:
                # Run ResFinder using your existing function
                output_file = f"resfinder_results/resfinder_output_{job_id}.csv"
                run_resfinder(genome_urls, output_file)
                
                # Read and return results
                if os.path.exists(output_file):
                    df = pd.read_csv(output_file, header=[0,1])
                    
                    # Convert MultiIndex columns to strings to avoid JSON serialization issues
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = [f"{col[0]}_{col[1]}" if isinstance(col, tuple) else str(col) for col in df.columns]
                    
                    results = {
                        "csv_path": output_file,
                        "data": safe_serialize(df.to_dict('records')),
                        "columns": safe_serialize(df.columns.tolist()),
                        "shape": df.shape
                    }
                    jobs[job_id].status = "completed"
                    jobs[job_id].result = results
                    save_job_to_db(jobs[job_id])
                else:
                    jobs[job_id].status = "failed"
                    jobs[job_id].error = "ResFinder did not produce output file"
                    save_job_to_db(jobs[job_id])
                
                jobs[job_id].completed_at = datetime.now()
                save_job_to_db(jobs[job_id])
                
            except Exception as e:
                jobs[job_id].status = "failed"
                jobs[job_id].error = str(e)
                jobs[job_id].completed_at = datetime.now()
                save_job_to_db(jobs[job_id])
        
        # Run in background
        thread = threading.Thread(target=resfinder_task)
        thread.start()
        
        return jsonify({
            "job_id": job_id,
            "message": "ResFinder analysis started",
            "status": "pending"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/run-phastest', methods=['POST'])
def run_phastest_api():
    """Run PHASTEST analysis with API status check and fallback"""
    try:
        # Check PHASTEST API status first
        try:
            print("🔍 Checking PHASTEST API status...")
            test_response = requests.get("https://phastest.ca/phastest_api", timeout=10)
            if test_response.status_code != 200:
                raise Exception("PHASTEST API returned non-200 status")
            print("✅ PHASTEST API is available")
        except Exception as api_error:
            print(f"❌ PHASTEST API check failed: {api_error}")
            # API is down, return fallback option
            return jsonify({
                "status": "api_unavailable",
                "message": "PHASTEST API is currently unavailable",
                "fallback_available": True,
                "instructions": "Download FASTA files and submit manually to phastest.ca",
                "error": str(api_error)
            }), 503

        # Continue with normal API flow
        data = request.get_json()
        genome_urls = data.get('genome_urls', [])
        
        if not genome_urls:
            return jsonify({"error": "No genome URLs provided"}), 400
        
        job_id = create_job('phastest')
        
        def phastest_task():
            try:
                jobs[job_id].status = 'running'
                jobs[job_id].progress = 10
                save_job_to_db(jobs[job_id])
                
                # Find FASTA files in resfinder_results directory
                fasta_files = []
                for ext in ['*.fa', '*.fasta', '*.fna']:
                    fasta_files.extend(glob.glob(os.path.join('resfinder_results', ext)))
                
                if not fasta_files:
                    jobs[job_id].status = 'failed'
                    jobs[job_id].error = "No FASTA files found in resfinder_results/"
                    save_job_to_db(jobs[job_id])
                    return
                
                print(f"Found {len(fasta_files)} FASTA files for PHASTEST analysis")
                jobs[job_id].progress = 30
                save_job_to_db(jobs[job_id])
                
                # Run PHASTEST analysis
                submit_and_download_phastest(
                    fasta_files=fasta_files,
                    zip_folder='phastest_results',
                    output_csv='phastest_results.csv'
                )
                
                jobs[job_id].status = 'completed'
                jobs[job_id].progress = 100
                jobs[job_id].result = {
                    'message': f'PHASTEST analysis completed for {len(fasta_files)} files',
                    'files_processed': len(fasta_files)
                }
                save_job_to_db(jobs[job_id])
                
            except Exception as e:
                jobs[job_id].status = 'failed'
                jobs[job_id].error = str(e)
                save_job_to_db(jobs[job_id])
                print(f"PHASTEST analysis failed: {e}")
        
        thread = threading.Thread(target=phastest_task)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "job_id": job_id,
            "message": "PHASTEST analysis started",
            "status": "started"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/download-fasta-files', methods=['POST'])
def download_fasta_files():
    """Create a zip file with all FASTA files for manual PHASTEST submission"""
    try:
        data = request.get_json()
        genome_urls = data.get('genome_urls', [])
        
        print(f"📥 Received request to download FASTA files for {len(genome_urls)} genomes")
        
        if not genome_urls:
            print("❌ No genome URLs provided")
            return jsonify({"error": "No genome URLs provided"}), 400
        
        # Create temporary directory
        temp_dir = f"temp_fasta_{int(time.time())}"
        os.makedirs(temp_dir, exist_ok=True)
        
        print(f"📁 Created temporary directory: {temp_dir}")
        
        # Download all FASTA files
        downloaded_files = []
        for i, genome in enumerate(genome_urls):
            try:
                # Extract filename from URL or use assembly accession
                filename = f"{genome.get('assembly_accession', f'genome_{i+1}')}.fasta"
                file_path = os.path.join(temp_dir, filename)
                
                print(f"⬇️ Downloading {filename} from {genome['url']}...")
                
                # Download the file
                response = requests.get(genome['url'], stream=True, timeout=30)
                response.raise_for_status()
                
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                downloaded_files.append(file_path)
                print(f"✅ Downloaded {filename} ({os.path.getsize(file_path)} bytes)")
                
            except Exception as e:
                print(f"❌ Failed to download {genome.get('assembly_accession', f'genome_{i+1}')}: {e}")
        
        if not downloaded_files:
            print("❌ No files were successfully downloaded")
            return jsonify({"error": "No files were successfully downloaded"}), 500
        
        # Create zip file
        zip_filename = f"{temp_dir}_fasta_files.zip"
        zip_path = os.path.join(temp_dir, zip_filename)
        
        print(f"📦 Creating zip file: {zip_filename}")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in downloaded_files:
                zipf.write(file_path, os.path.basename(file_path))
        
        zip_size = os.path.getsize(zip_path)
        print(f"✅ Zip file created with {len(downloaded_files)} FASTA files ({zip_size} bytes)")
        
        # Return the zip file
        print(f"📤 Sending file: {zip_path} ({zip_size} bytes)")
        response = send_file(
            zip_path,
            as_attachment=True,
            download_name=zip_filename
        )
        
        # Add proper headers for file download
        response.headers['Content-Type'] = 'application/zip'
        response.headers['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
        
        print(f"📤 Response created: {response}")
        print(f"📤 Headers: {response.headers}")
        return response
        
    except Exception as e:
        print(f"❌ Error in download_fasta_files: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/phastest-status', methods=['GET'])
def check_phastest_status():
    """Check if PHASTEST API is available"""
    try:
        response = requests.get("https://phastest.ca/phastest_api", timeout=10)
        return jsonify({
            "status": "available" if response.status_code == 200 else "unavailable",
            "status_code": response.status_code
        })
    except Exception as e:
        return jsonify({
            "status": "unavailable",
            "error": str(e)
        }), 503

@app.route('/api/phastest-zip-files', methods=['GET'])
def list_phastest_zip_files():
    """List available PHASTEST zip files"""
    try:
        phastest_dir = "phastest_results"
        if not os.path.exists(phastest_dir):
            return jsonify({"zip_files": []})
        
        zip_files = [f for f in os.listdir(phastest_dir) if f.endswith('.PHASTEST.zip')]
        zip_files_info = []
        
        for zip_file in zip_files:
            zip_path = os.path.join(phastest_dir, zip_file)
            file_size = os.path.getsize(zip_path)
            zip_files_info.append({
                "filename": zip_file,
                "size": file_size,
                "size_mb": round(file_size / (1024 * 1024), 2)
            })
        
        return jsonify({"zip_files": zip_files_info})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/temp-fasta-zip-files', methods=['GET'])
def list_temp_fasta_zip_files():
    """List available temporary FASTA zip files"""
    try:
        # Get the project root directory (where api_server.py is located)
        project_root = os.path.dirname(os.path.abspath(__file__))
        print(f"🔍 Searching for temp_fasta directories in: {project_root}")
        
        # List all directories in project root
        all_dirs = [d for d in os.listdir(project_root) if os.path.isdir(os.path.join(project_root, d))]
        print(f"📁 All directories found: {all_dirs}")
        
        # Find all temp_fasta_* directories
        temp_dirs = [d for d in all_dirs if d.startswith('temp_fasta_')]
        print(f"🎯 Temp FASTA directories found: {temp_dirs}")
        
        zip_files_info = []
        
        for temp_dir in temp_dirs:
            # Look for zip files in each temp directory
            temp_dir_path = os.path.join(project_root, temp_dir)
            print(f"📂 Checking directory: {temp_dir_path}")
            
            if os.path.exists(temp_dir_path):
                zip_files = [f for f in os.listdir(temp_dir_path) if f.endswith('.zip')]
                print(f"📦 Zip files found in {temp_dir}: {zip_files}")
                
                for zip_file in zip_files:
                    zip_path = os.path.join(temp_dir_path, zip_file)
                    file_size = os.path.getsize(zip_path)
                    zip_files_info.append({
                        "filename": zip_file,
                        "temp_dir": temp_dir,
                        "full_path": zip_path,
                        "size": file_size,
                        "size_mb": round(file_size / (1024 * 1024), 2),
                        "created_time": os.path.getctime(zip_path)
                    })
            else:
                print(f"❌ Directory does not exist: {temp_dir_path}")
        
        # Sort by creation time (newest first)
        zip_files_info.sort(key=lambda x: x['created_time'], reverse=True)
        print(f"📋 Final zip files info: {zip_files_info}")
        
        return jsonify({"zip_files": zip_files_info})
    except Exception as e:
        print(f"❌ Error in list_temp_fasta_zip_files: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/download-temp-fasta-zip/<temp_dir>/<filename>', methods=['GET'])
def download_temp_fasta_zip(temp_dir, filename):
    """Download a specific temporary FASTA zip file"""
    try:
        # Validate the temp directory name
        if not temp_dir.startswith('temp_fasta_') or '..' in temp_dir or '/' in temp_dir:
            return jsonify({"error": "Invalid directory name"}), 400
        
        # Validate the filename
        if not filename.endswith('.zip') or '..' in filename or '/' in filename:
            return jsonify({"error": "Invalid filename"}), 400
        
        # Get the project root directory (where api_server.py is located)
        project_root = os.path.dirname(os.path.abspath(__file__))
        zip_path = os.path.join(project_root, temp_dir, filename)
        
        if not os.path.exists(zip_path):
            return jsonify({"error": "File not found"}), 404
        
        # Return the zip file
        response = send_file(
            zip_path,
            as_attachment=True,
            download_name=filename
        )
        
        # Add proper headers for file download
        response.headers['Content-Type'] = 'application/zip'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/download-resfinder-fasta-zip', methods=['GET'])
def download_resfinder_fasta_zip():
    """Create and download a zip file containing FASTA files from resfinder_results"""
    try:
        # Get the project root directory
        project_root = os.path.dirname(os.path.abspath(__file__))
        resfinder_dir = os.path.join(project_root, 'resfinder_results')
        
        if not os.path.exists(resfinder_dir):
            return jsonify({"error": "ResFinder results directory not found"}), 404
        
        # Find all .fna files in resfinder_results
        fasta_files = [f for f in os.listdir(resfinder_dir) if f.endswith('.fna') and os.path.isfile(os.path.join(resfinder_dir, f))]
        
        if not fasta_files:
            return jsonify({"error": "No FASTA files found in ResFinder results"}), 404
        
        print(f"📦 Found {len(fasta_files)} FASTA files in resfinder_results")
        
        # Create a temporary zip file
        import tempfile
        temp_zip_path = tempfile.mktemp(suffix='.zip')
        
        with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for fasta_file in fasta_files:
                fasta_path = os.path.join(resfinder_dir, fasta_file)
                # Add file to zip with just the filename (no path)
                zipf.write(fasta_path, fasta_file)
                print(f"✅ Added {fasta_file} to zip")
        
        zip_size = os.path.getsize(temp_zip_path)
        print(f"📦 Created zip file: {temp_zip_path} ({zip_size} bytes)")
        
        # Return the zip file
        response = send_file(
            temp_zip_path,
            as_attachment=True,
            download_name=f"phastest_fasta_files_{len(fasta_files)}_genomes.zip"
        )
        
        # Add proper headers for file download
        response.headers['Content-Type'] = 'application/zip'
        response.headers['Content-Disposition'] = f'attachment; filename="phastest_fasta_files_{len(fasta_files)}_genomes.zip"'
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        
        # Clean up the temporary file after sending
        def cleanup_temp_file():
            try:
                os.remove(temp_zip_path)
                print(f"🗑️ Cleaned up temporary file: {temp_zip_path}")
            except:
                pass
        
        # Schedule cleanup after response is sent
        import threading
        timer = threading.Timer(5.0, cleanup_temp_file)
        timer.start()
        
        return response
        
    except Exception as e:
        print(f"❌ Error in download_resfinder_fasta_zip: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/run-vfdb', methods=['POST'])
def run_vfdb_api():
    """Run VFDB analysis on genome URLs"""
    try:
        data = request.get_json()
        genome_urls = data.get('genome_urls')
        
        if not genome_urls:
            return jsonify({"error": "Genome URLs are required"}), 400
        
        # Create job for tracking
        job_id = create_job("vfdb")
        jobs[job_id].status = "running"
        
        def vfdb_task():
            try:
                # Create output directory for this job
                output_dir = f"vfdb_results/{job_id}"
                os.makedirs(output_dir, exist_ok=True)
                
                # Download/decompress FASTA files
                fasta_paths = []
                for genome in genome_urls:
                    url = genome['url'] if isinstance(genome, dict) else genome
                    fasta_path = download_and_decompress_fasta(url, output_dir)
                    fasta_paths.append(fasta_path)
                
                # Run BLAST workflow
                build_blast_db()
                matrix_csv = os.path.join(output_dir, "vfdb_matrix.csv")
                aggregate_results(fasta_paths, matrix_csv, output_dir=output_dir)
                
                # Format Excel output
                mapping_csv = os.path.join("utils", "vfdb_data", "vfdb_gene_category_mapping.csv")
                excel_out = os.path.join(output_dir, "vfdb_matrix_formatted.xlsx")
                format_vfdb_matrix(matrix_csv, mapping_csv, excel_out)
                
                # Read and return results
                if os.path.exists(excel_out) and os.path.exists(matrix_csv):
                    results = {
                        "excel_path": excel_out,
                        "csv_path": matrix_csv,
                        "message": "VFDB analysis completed successfully"
                    }
                    jobs[job_id].status = "completed"
                    jobs[job_id].result = results
                    save_job_to_db(jobs[job_id])
                else:
                    jobs[job_id].status = "failed"
                    jobs[job_id].error = "VFDB did not produce output file"
                    save_job_to_db(jobs[job_id])
                
                jobs[job_id].completed_at = datetime.now()
                save_job_to_db(jobs[job_id])
                
            except Exception as e:
                jobs[job_id].status = "failed"
                jobs[job_id].error = str(e)
                jobs[job_id].completed_at = datetime.now()
                save_job_to_db(jobs[job_id])
        
        # Run in background
        thread = threading.Thread(target=vfdb_task)
        thread.start()
        
        return jsonify({
            "job_id": job_id,
            "message": "VFDB analysis started",
            "status": "pending"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/job-status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get the status of a specific job"""
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
    
    job = jobs[job_id]
    return jsonify({
        "job_id": job.job_id,
        "job_type": job.job_type,
        "status": job.status,
        "progress": job.progress,
        "result": safe_serialize(job.result),
        "error": job.error,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None
    })

@app.route('/api/download/<job_id>/<file_type>', methods=['GET'])
def download_file(job_id, file_type):
    """Download result files"""
    print(f"Download request: job_id={job_id}, file_type={file_type}")
    print(f"Available jobs: {list(jobs.keys())}")
    
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
    
    job = jobs[job_id]
    if job.status != "completed":
        return jsonify({"error": "Job not completed"}), 400
    
    try:
        if file_type == "resfinder_csv" and job.job_type == "resfinder":
            file_path = job.result.get("csv_path")
        elif file_type == "phastest_csv" and job.job_type == "phastest":
            file_path = job.result.get("csv_path")
        elif file_type == "phastest_zip" and job.job_type == "phastest":
            # For PHASTEST zip files, we need to find all zip files in the phastest_results directory
            phastest_dir = "phastest_results"
            if not os.path.exists(phastest_dir):
                return jsonify({"error": "PHASTEST results directory not found"}), 404
            
            # Find all .PHASTEST.zip files
            zip_files = [f for f in os.listdir(phastest_dir) if f.endswith('.PHASTEST.zip')]
            if not zip_files:
                return jsonify({"error": "No PHASTEST zip files found"}), 404
            
            # Create a temporary zip file containing all PHASTEST zip files
            import tempfile
            import zipfile as zipfile_module
            
            temp_zip_path = tempfile.mktemp(suffix='.zip')
            with zipfile_module.ZipFile(temp_zip_path, 'w', zipfile_module.ZIP_DEFLATED) as zipf:
                for zip_file in zip_files:
                    zip_file_path = os.path.join(phastest_dir, zip_file)
                    zipf.write(zip_file_path, zip_file)
            
            # Return the temporary zip file
            response = send_file(temp_zip_path, as_attachment=True, download_name=f"phastest_results_{job_id}.zip")
            
            # Clean up the temporary file after sending
            def cleanup_temp_file():
                try:
                    os.remove(temp_zip_path)
                except:
                    pass
            
            # Schedule cleanup after response is sent
            import threading
            timer = threading.Timer(5.0, cleanup_temp_file)
            timer.start()
            
            return response
        elif file_type == "vfdb_excel" and job.job_type == "vfdb":
            file_path = job.result.get("excel_path")
        elif file_type == "vfdb_csv" and job.job_type == "vfdb":
            # For VFDB, we want to return the formatted Excel file
            # Try both new and old directory structures
            output_dir = f"vfdb_results/{job_id}"
            file_path = os.path.join(output_dir, "vfdb_matrix_formatted.xlsx")
            
            # If not found, try the old directory structure (for existing jobs)
            if not os.path.exists(file_path):
                old_output_dir = f"vfdb_results/job_{job_id}"
                file_path = os.path.join(old_output_dir, "vfdb_matrix_formatted.xlsx")
            
            print(f"VFDB file path: {file_path}")
            print(f"File exists: {os.path.exists(file_path)}")
        else:
            return jsonify({"error": "Invalid file type"}), 400
        
        if not file_path or not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404
        
        return send_file(file_path, as_attachment=True)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/jobs', methods=['GET'])
def list_jobs():
    """List all jobs"""
    job_list = []
    for job_id, job in jobs.items():
        job_list.append({
            "job_id": job.job_id,
            "job_type": job.job_type,
            "status": job.status,
            "created_at": job.created_at.isoformat(),
            "completed_at": job.completed_at.isoformat() if job.completed_at else None
        })
    
    return jsonify({"jobs": job_list})

@app.route('/api/download-existing/<job_id>/<file_type>', methods=['GET'])
def download_existing_file(job_id, file_type):
    """Download existing files even if job is not in memory"""
    print(f"Download existing request: job_id={job_id}, file_type={file_type}")
    try:
        if file_type == "vfdb_csv":
            # Try both directory structures for VFDB
            file_paths = [
                f"vfdb_results/{job_id}/vfdb_matrix_formatted.xlsx",
                f"vfdb_results/job_{job_id}/vfdb_matrix_formatted.xlsx"
            ]
            
            print(f"Checking file paths: {file_paths}")
            for file_path in file_paths:
                print(f"Checking: {file_path} - exists: {os.path.exists(file_path)}")
                if os.path.exists(file_path):
                    print(f"Found file: {file_path}")
                    return send_file(file_path, as_attachment=True, download_name="vfdb_results.xlsx")
            
            print("No file found")
            return jsonify({"error": "VFDB file not found"}), 404
        else:
            return jsonify({"error": "Unsupported file type"}), 400
            
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/cleanup-files', methods=['POST'])
def manual_cleanup_files():
    """Manually trigger file cleanup"""
    try:
        cleanup_temp_files()
        return jsonify({
            "message": "File cleanup completed successfully",
            "status": "success"
        })
    except Exception as e:
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500

@app.route('/api/cleanup/<job_id>', methods=['DELETE'])
def cleanup_job(job_id):
    """Clean up job data and files"""
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
    
    try:
        job = jobs[job_id]
        
        # Clean up result files
        if job.result:
            if job.job_type == "resfinder" and "csv_path" in job.result:
                if os.path.exists(job.result["csv_path"]):
                    os.remove(job.result["csv_path"])
            elif job.job_type == "phastest" and "csv_path" in job.result:
                if os.path.exists(job.result["csv_path"]):
                    os.remove(job.result["csv_path"])
            elif job.job_type == "vfdb":
                if "excel_path" in job.result and os.path.exists(job.result["excel_path"]):
                    os.remove(job.result["excel_path"])
                if "csv_path" in job.result and os.path.exists(job.result["csv_path"]):
                    os.remove(job.result["csv_path"])
        
        # Remove job from memory
        del jobs[job_id]
        delete_job_from_db(job_id)
        
        return jsonify({"message": "Job cleaned up successfully"})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Create necessary directories
    os.makedirs("resfinder_results", exist_ok=True)
    os.makedirs("phastest_results", exist_ok=True)
    os.makedirs("vfdb_results", exist_ok=True)
    
    print("Starting Genome Analysis API Server...")
    print("API will be available at: http://localhost:5000")
    print("React frontend can connect to: http://localhost:5000/api")
    
    app.run(debug=True, host='0.0.0.0', port=5000) 