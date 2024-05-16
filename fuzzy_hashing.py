import os
import sqlite3
import hashlib
from pdf2image import convert_from_path
from PIL import Image
import ssdeep
import fitz  # PyMuPDF
from collections import defaultdict
from multiprocessing import Pool, cpu_count
import tempfile

# Initialize database
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
    conn.commit()
    conn.close()

# Hash pages and store in database
def hash_pdf_pages(pdf_path, db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

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

def process_all_pdfs_in_parallel(pdf_files, db_path):
    with Pool(cpu_count()) as pool:
        pool.starmap(hash_pdf_pages, [(pdf, db_path) for pdf in pdf_files])

def main():
    input_directory = input("Enter the path to the OCR processed directory: ")
    db_path = "page_hashes.db"
    output_directory = input("Enter the path to the output directory for similar pages: ")

    # Initialize the database
    init_db(db_path)
    
    # Find all OCR processed PDF files
    processed_pdf_files = []
    for root, _, files in os.walk(input_directory):
        for file in files:
            if file.endswith(".pdf"):
                processed_pdf_files.append(os.path.join(root, file))
    
    total_files = len(processed_pdf_files)
    print(f"Found {total_files} OCR processed PDF files to hash.")
    
    # Process all PDFs in parallel
    process_all_pdfs_in_parallel(processed_pdf_files, db_path)
    
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
