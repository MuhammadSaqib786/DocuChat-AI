from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
from tqdm import tqdm

# Load the local embedding model (downloads on first use)
model = SentenceTransformer('all-MiniLM-L6-v2')

def get_local_embedding(text):
    """Get local embedding for a single chunk."""
    return model.encode([text])[0]

def embed_chunks(chunks):
    """Embed all chunks using the local model."""
    embeddings = []
    for chunk in tqdm(chunks, desc="Embedding chunks (local)"):
        emb = get_local_embedding(chunk)
        embeddings.append(emb)
    return np.array(embeddings, dtype='float32')

def save_faiss_index(embeddings, idx_path):
    """Save the embeddings to a FAISS index."""
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    faiss.write_index(index, idx_path)
