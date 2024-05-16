import os
import subprocess
import readline
import glob
import sqlite3
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

# Enable tab completion
readline.parse_and_bind("tab: complete")

def complete_path(text, state):
    line = readline.get_line_buffer().split()
    if '~' in text:
        text = os.path.expanduser(text)
    return [x for x in glob.glob(text + '*')][state]

readline.set_completer(complete_path)

# Function to perform OCR on a single PDF file
def ocr_pdf(input_pdf, output_pdf, jobs):
    cmd = [
        'ocrmypdf',
        '-l', 'eng+spa',  # Assuming English and Spanish languages
        '--rotate-pages',
        '--deskew',
        '--jobs', str(jobs),
        '--output-type', 'pdfa',
        input_pdf,
        output_pdf
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd, output=result.stdout, stderr=result.stderr)

# Initialize database and create tables if they don't exist
def init_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS page_hashes (
            id INTEGER PRIMARY KEY,
            pdf_path TEXT,
            page_number INTEGER,
            page_hash TEXT,
            original_md5 TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ocr_status (
            pdf_path TEXT PRIMARY KEY,
            status TEXT,
            attempts INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

# Function to read the OCR status from the database
def read_ocr_status(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT pdf_path, status, attempts FROM ocr_status')
    processed_files = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
    conn.close()
    return processed_files

# Function to update the OCR status in the database
def update_ocr_status(db_path, pdf_path, status, attempts):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO ocr_status (pdf_path, status, attempts)
        VALUES (?, ?, ?)
    ''', (pdf_path, status, attempts))
    conn.commit()
    conn.close()

# Function to process a single PDF file and update the status
def process_single_pdf(pdf_path, output_directory, jobs, db_path, retry_limit):
    output_pdf_path = os.path.join(output_directory, os.path.basename(pdf_path))
    processed_files = read_ocr_status(db_path)
    status, attempts = processed_files.get(pdf_path, ("pending", 0))

    try:
        ocr_pdf(pdf_path, output_pdf_path, jobs)
        update_ocr_status(db_path, pdf_path, "completed", attempts)
    except subprocess.CalledProcessError as e:
        attempts += 1
        if attempts >= retry_limit:
            print(f"Error processing file {pdf_path} after {attempts} attempts: {e.stderr}")
            update_ocr_status(db_path, pdf_path, "failed", attempts)
        else:
            update_ocr_status(db_path, pdf_path, "retry", attempts)
            raise

# Function to perform OCR on all PDF files in the given directory
def process_pdfs(input_directory, output_directory, jobs, db_path, retry_limit):
    processed_files = read_ocr_status(db_path)

    pdf_files = []
    for root, _, files in os.walk(input_directory):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_path = os.path.join(root, file)
                status, attempts = processed_files.get(pdf_path, ("pending", 0))
                if status == "completed":
                    continue
                pdf_files.append((pdf_path, attempts))

    total_files = len(pdf_files)
    print(f"Found {total_files} PDF files to process.")

    if total_files == 0:
        print("No PDF files found to process.")
        return

    os.makedirs(output_directory, exist_ok=True)

    with ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = {executor.submit(process_single_pdf, pdf_path, output_directory, jobs, db_path, retry_limit): pdf_path for pdf_path, _ in pdf_files}
        retry_files = []
        for future in tqdm(as_completed(futures), total=total_files, desc="Processing PDFs", unit="file"):
            try:
                future.result()  # This will raise any exceptions caught during processing
            except Exception as e:
                retry_files.append(futures[future])

    # Retry failed files
    if retry_files:
        print(f"\nRetrying {len(retry_files)} failed files...\n")
        with ThreadPoolExecutor(max_workers=jobs) as executor:
            futures = {executor.submit(process_single_pdf, pdf_path, output_directory, jobs, db_path, retry_limit): pdf_path for pdf_path in retry_files}
            for future in tqdm(as_completed(futures), total=len(retry_files), desc="Retrying PDFs", unit="file"):
                try:
                    future.result()
                except Exception as e:
                    print(f"File failed after multiple attempts: {futures[future]}")

def main():
    input_directory = input("Enter the path to the directory containing PDFs: ").strip()
    output_directory = input("Enter the path to the output directory for processed PDFs: ").strip()
    db_path = os.path.join(output_directory, "page_hashes.db")
    retry_limit = 3  # Define the retry limit

    if not os.path.isdir(input_directory):
        print(f"Error: The directory '{input_directory}' does not exist.")
        return

    # Ensure the output directory exists
    os.makedirs(output_directory, exist_ok=True)

    # Initialize the database
    init_db(db_path)

    # Determine the number of jobs based on available CPU cores
    jobs = os.cpu_count()
    print(f"Using {jobs} concurrent jobs based on available CPU cores.")

    process_pdfs(input_directory, output_directory, jobs, db_path, retry_limit)

if __name__ == "__main__":
    main()
