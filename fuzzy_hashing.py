import os
import readline
import glob
import sqlite3
import hashlib
from pdf2image import convert_from_path
from PIL import Image
import ssdeep
import fitz  # PyMuPDF
from collections import defaultdict
from multiprocessing import Pool, cpu_count, Manager, Queue
import tempfile

# Enable tab completion
readline.parse_and_bind("tab: complete")

def complete_path(text, state):
    line = readline.get_line_buffer().split()
    if '~' in text:
        text = os.path.expanduser(text)
    return [x for x in glob.glob(text + '*')][state]

readline.set_completer(complete_path)

# Initialize database
def init_db(db_path):
    conn = sqlite3.connect(db_path, check_same_thread=False)
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
    conn.commit()
    conn.close()

# Worker function to hash pages and store in database
def hash_pdf_pages(queue, db_path):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()

    while True:
        pdf_path = queue.get()
        if pdf_path is None:
            break

        try:
            images = convert_from_path(pdf_path)
            original_md5 = calculate_md5(pdf_path)
            for page_number, image in enumerate(images, start=1):
                with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmpfile:
                    image.save(tmpfile.name)
                    with open(tmpfile.name, 'rb') as f:
                        page_hash = ssdeep.hash(f.read())
                        cursor.execute('''
                            INSERT INTO page_hashes (pdf_path, page_number, page_hash, original_md5)
                            VALUES (?, ?, ?, ?)
                        ''', (pdf_path, page_number, page_hash, original_md5))
            conn.commit()
        except Exception as e:
            print(f"Error processing file {pdf_path}: {e}")
            if 'Unable to get page count' in str(e):
                print("Please ensure poppler-utils is installed and in your PATH.")

    conn.close()

def calculate_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def find_similar_pages(db_path, similarity_threshold=95):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('SELECT DISTINCT page_hash FROM page_hashes')
    hashes = [row[0] for row in cursor.fetchall()]

    similar_pages = defaultdict(list)

    for i in range(len(hashes)):
        for j in range(i + 1, len(hashes)):
            similarity = ssdeep.compare(hashes[i], hashes[j])
            if similarity >= similarity_threshold:
                cursor.execute('SELECT pdf_path, page_number, original_md5 FROM page_hashes WHERE page_hash=?', (hashes[i],))
                pages_i = cursor.fetchall()
                cursor.execute('SELECT pdf_path, page_number, original_md5 FROM page_hashes WHERE page_hash=?', (hashes[j],))
                pages_j = cursor.fetchall()
                similar_pages[hashes[i]].extend(pages_i)
                similar_pages[hashes[i]].extend(pages_j)

    conn.close()
    return similar_pages

def save_similar_pages(similar_pages, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    for hash_, pages in similar_pages.items():
        if len(pages) > 1:
            doc = fitz.open()
            for pdf_path, page_number, original_md5 in pages:
                original_doc = fitz.open(pdf_path)
                page = original_doc.load_page(page_number - 1)
                doc.insert_pdf(original_doc, from_page=page_number - 1, to_page=page_number - 1)
            output_pdf_path = os.path.join(output_dir, f"{hash_}.pdf")
            doc.save(output_pdf_path)
            doc.close()

def main():
    input_directory = input("Enter the path to the directory containing PDFs: ").strip()
    db_path = "page_hashes.db"
    output_directory = input("Enter the path to the output directory for similar pages: ").strip()

    # Ensure input directory is correct
    if not os.path.isdir(input_directory):
        print(f"Error: The directory '{input_directory}' does not exist.")
        return

    # Initialize the database
    init_db(db_path)

    # Find all PDF files recursively
    pdf_files = []
    for root, _, files in os.walk(input_directory):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_path = os.path.join(root, file)
                pdf_files.append(pdf_path)
                print(f"Found file: {pdf_path}")  # Debug print

    total_files = len(pdf_files)
    print(f"Found {total_files} PDF files to hash.")

    if total_files == 0:
        print("No PDF files found to process.")
        return

    # Process all PDFs in parallel using a manager queue
    manager = Manager()
    queue = manager.Queue()

    # Start worker processes
    pool = Pool(cpu_count())
    for _ in range(cpu_count()):
        pool.apply_async(hash_pdf_pages, (queue, db_path))

    # Add files to queue
    for pdf_path in pdf_files:
        queue.put(pdf_path)

    # Add sentinel values to stop the workers
    for _ in range(cpu_count()):
        queue.put(None)

    # Close the pool and wait for the work to finish
    pool.close()
    pool.join()

    # Find similar pages
    similar_pages = find_similar_pages(db_path)

    # Save similar pages to new PDFs
    if similar_pages:
        print("Similar pages found and saving to new PDFs:")
        save_similar_pages(similar_pages, output_directory)
        print(f"Similar pages saved in {output_directory}.")
    else:
        print("No similar pages found.")

if __name__ == "__main__":
    main()
