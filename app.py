from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
import os
from modules.doc_parser import extract_text
import json
from modules.chunker import simple_chunk_text
from modules.embeddings import embed_chunks, save_faiss_index
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
from transformers import pipeline




# Create Flask app
app = Flask(__name__)
app.secret_key = 'your_secret_key'

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


llm = pipeline(
    "text-generation",
    model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    max_new_tokens=128,
    do_sample=False,
    temperature=0.3
)

# Create uploads folder if not exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/qa', methods=['GET', 'POST'])
def qa():
    docs = list_uploaded_docs()
    answer = None
    question = ""
    selected_doc = ""
    context_chunks = []
    if request.method == 'POST':
        question = request.form['question']
        selected_doc = request.form['doc']
        context_chunks = get_top_chunks(question, selected_doc, top_k=3)
        
        rag_prompt = build_rag_prompt(context_chunks, question)
        llm_response = llm(rag_prompt)[0]["generated_text"]
        if "ANSWER:" in llm_response:
            answer = llm_response.split("ANSWER:")[-1].strip()
        else:
            answer = llm_response.strip()
    return render_template('qa.html', docs=docs, answer=answer, question=question, selected_doc=selected_doc)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            # ---- Extract text here ----
            try:
                text = extract_text(filepath)
                txt_path = filepath + ".txt"
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(text)
                # --- Chunking ---
                chunks = simple_chunk_text(text)
                chunks_path = filepath + ".chunks.json"
                with open(chunks_path, "w", encoding="utf-8") as f:
                    json.dump(chunks, f, ensure_ascii=False, indent=2)

                # --- Auto embedding starts here ---
                try:
                    embs = embed_chunks(chunks)
                    idx_path = filepath + ".faiss.idx"
                    save_faiss_index(np.array(embs, dtype='float32'), idx_path)
                    # Save chunk text for later retrieval (meta)
                    meta_path = filepath + ".meta.json"
                    with open(meta_path, "w", encoding="utf-8") as f:
                        json.dump(chunks, f, ensure_ascii=False, indent=2)
                    flash(f'File uploaded, text extracted, chunked, and embeddings created ({len(chunks)} chunks)!')
                except Exception as e:
                    flash(f'Chunking worked, but embedding failed: {e}')

            except Exception as e:
                flash(f'File uploaded but failed to extract text: {e}')
            return redirect(url_for('index'))
        else:
            flash('Invalid file type. Please upload a PDF, DOCX, or TXT file.')
            return redirect(request.url)
    return render_template('upload.html')

def list_uploaded_docs():
    files = []
    for f in os.listdir(app.config['UPLOAD_FOLDER']):
        if f.endswith('.faiss.idx'):
            base = f.rsplit('.faiss.idx', 1)[0]
            files.append(base)
    return files

def get_top_chunks(question, base_path, top_k=3):
    # Load model and question embedding
    model = SentenceTransformer('all-MiniLM-L6-v2')
    q_emb = model.encode([question]).astype('float32')
    # Load FAISS index and meta
    idx_path = os.path.join(app.config['UPLOAD_FOLDER'], base_path + '.faiss.idx')
    index = faiss.read_index(idx_path)
    meta_path = os.path.join(app.config['UPLOAD_FOLDER'], base_path + '.meta.json')
    with open(meta_path, 'r', encoding='utf-8') as f:
        chunks = json.load(f)
    # Search
    D, I = index.search(q_emb, top_k)
    relevant_chunks = [chunks[i] for i in I[0]]
    return relevant_chunks

def load_llm():
    # Phi-2 is small and runs on most CPUs; 
    return pipeline(
        "text-generation",
        model="microsoft/phi-2",
        max_new_tokens=256,
        do_sample=True,
        temperature=0.3
    )

def build_rag_prompt(context_chunks, question):
    prompt = "Use the CONTEXT below to answer the QUESTION. If answer is not found, say so.\n\n"
    prompt += "CONTEXT:\n"
    for chunk in context_chunks:
        prompt += chunk.strip() + "\n---\n"
    prompt += f"\nQUESTION: {question}\nANSWER:"
    return prompt

if __name__ == '__main__':
    app.run(debug=True)
