from pathlib import Path
from utils.download_genomes import download_and_decompress_fasta
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing
