import gzip
import shutil
import urllib.request
from pathlib import Path
import requests

def download_and_decompress_fasta(url, output_dir="."):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    gz_path = output_dir / Path(url).name
    fasta_path = gz_path.with_suffix("")

    if not gz_path.exists():
        try:
            with requests.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(gz_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
        except Exception as e:
            if gz_path.exists():
                gz_path.unlink()
            raise RuntimeError(f"Failed to download {url}: {e}")

    # Verify the file is a valid gzip before decompressing
    try:
        # Try to read the first few bytes to check gzip validity
        with gzip.open(gz_path, 'rb') as f_in:
            f_in.read(10)
    except Exception as e:
        if gz_path.exists():
            gz_path.unlink()
        raise RuntimeError(f"Downloaded file is not a valid gzip file: {gz_path}. Error: {e}")

    # Now decompress
    try:
        with gzip.open(gz_path, 'rb') as f_in:
            with open(fasta_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
    except Exception as e:
        if fasta_path.exists():
            fasta_path.unlink()
        raise RuntimeError(f"Failed to decompress {gz_path}: {e}")

    # Ensure the first line is a FASTA header (starts with '>') and all lines are clean
    try:
        with open(fasta_path, 'r', encoding='utf-8-sig', newline=None) as fin:
            lines = fin.readlines()
        # Find the first header line
        header_index = None
        for i, line in enumerate(lines):
            if line.lstrip().startswith('>'):
                header_index = i
                break
        if header_index is None:
            raise RuntimeError(f"No FASTA header found in {fasta_path}")
        # Clean lines: strip whitespace, ensure header is first, use only \n
        cleaned_lines = [l.strip() for l in lines[header_index:]]
        if not cleaned_lines or not cleaned_lines[0].startswith('>'):
            raise RuntimeError(f"First line after cleaning is not a FASTA header in {fasta_path}")
        with open(fasta_path, 'w', encoding='utf-8', newline='\n') as fout:
            for l in cleaned_lines:
                fout.write(l + '\n')
    except Exception as e:
        raise RuntimeError(f"Failed to ensure FASTA header in {fasta_path}: {e}")

    return str(fasta_path)
