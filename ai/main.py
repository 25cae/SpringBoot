from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv
import fitz
import requests
import os
import re

app = FastAPI()
load_dotenv()

# Load config from environment or hard-code temporarily (not secure for production)
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_DEPLOYMENT_ID = os.getenv("AZURE_DEPLOYMENT_ID")

app.mount("/static", StaticFiles(directory=".", html=True), name="static")
app.mount("/documents", StaticFiles(directory="documents"), name="documents")

def read_and_label_pdfs(file_paths: list[str]) -> str:
    """
    Reads multiple PDF files, extracts text from each,
    and labels the content with its source filename.
    """
    combined_text = ""

    for path in file_paths:
        if os.path.exists(path):
            try:
                doc = fitz.open(path)
                text = ""

                # Extract text from all pages
                for page in doc:
                    text += page.get_text()

                doc.close()

                # Label the section with filename
                filename = os.path.basename(path)
                labeled_text = f"\n\n### SOURCE: {filename}\n{text.strip()}"

                combined_text += labeled_text

            except Exception as e:
                print(f"Error reading {path}: {e}")
        else:
            print(f"Warning: File not found → {path}")

    return combined_text

def load_chunks_from_file():
    with open("chunked_data.json", "r") as f:
        return f.read()  # returns raw string format

def extract_source_documents(answer_text: str) -> list[str]:
    """
    Extracts document names from the 'Source Document:' section of the LLM response.
    """
    match = re.search(r"Source Document:\s*(.+)", answer_text)
    if match:
        doc_line = match.group(1)
        return [doc.strip() for doc in doc_line.split(",")]
    return []

class QueryRequest(BaseModel):
    query: str

@app.post("/ask")
async def answer_from_pdf(data: QueryRequest):
    user_query = data.query
    
    # Step 1: Read the PDF
    file_paths = ["documents/testing.pdf", "documents/Food.pdf", "documents/testing copy.pdf"]
    raw_document = read_and_label_pdfs(file_paths)

    # Step 4: Generate final answer
    answer_prompt = f"""
    Question:
    {user_query}

    Chunks:
    {raw_document}
    
    Using the given documents, answer the question concisely and as close as the original text as possible. No need to summarize or paraphrase, just extract the relevant information. Give explanation to the answer when provided by the original text:
    And provide the source document name (example "testing.pdf"). If you find multiple source docuemtns with the answer to the user query, provide only one best answer, but give the list of documents that contains the answer to the user query (so if 
    "testing.pdf" and "testing copy.pdf" both provides an answer to the user query, find the best answer and output both documents as the reference) Give me the answer in this format:

    Answer:
    <answer>
    
    Source Document:
    <source document name(s)>
    """

    answer_payload = {
        "messages": [
            { "role": "system", "content": "You are a helpful expert FAA assistant." },
            { "role": "user", "content": answer_prompt }
        ]
    }

    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_OPENAI_API_KEY
    }

    url = f"{AZURE_OPENAI_ENDPOINT}openai/deployments/{AZURE_DEPLOYMENT_ID}/chat/completions?api-version=2025-01-01-preview"

    answer_response = requests.post(url, headers=headers, json=answer_payload)
    final_answer = answer_response.json()["choices"][0]["message"]["content"]

    relevant_docs = extract_source_documents(final_answer)
    print(f"Relevant documents extracted: {relevant_docs}")

    document_links = [
        {
            "name": doc,
            "url": f"/documents/{doc}"  # Assuming documents are served from the /documents endpoint
        }
        for doc in relevant_docs
        if os.path.exists(f"documents/{doc}")
    ]

    return { 
        "answer": final_answer, 
        "documents": document_links
    }

'''
@app.post("/ask")
async def answer_from_pdf(data: QueryRequest):
    user_query = data.query
    
    # Step 1: Read the PDF
    file_paths = ["documents/testing.pdf", "documents/Food.pdf"]
    raw_document = read_and_label_pdfs(file_paths)

    # Step 2: Chunk the document
    chunk_prompt = f"""
    You're an expert document processor. Break the following document into labeled chunks based on chapters (like I. YEARLY, MONTHLY & WEEKLY FLIGHT LIMITS). Each chunk should include:
    - A clear heading
    - A concise summary
    - The full relevant text
    - The source document name (like "testing.pdf")

    Document:
    {raw_document}
    """

    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_OPENAI_API_KEY
    }

    url = f"{AZURE_OPENAI_ENDPOINT}openai/deployments/{AZURE_DEPLOYMENT_ID}/chat/completions?api-version=2025-01-01-preview"

    chunk_payload = {
        "messages": [
            { "role": "system", "content": "You're a chunking expert." },
            { "role": "user", "content": chunk_prompt }
            ]
    }

    chunk_response = requests.post(url, headers=headers, json=chunk_payload)
    chunk_response.raise_for_status()  # Ensure the request was successful
    chunk_texts = chunk_response.json()["choices"][0]["message"]["content"]

    # Step 3: Retrieve relevant chunks
    retrieval_prompt = f"""
    Based on this query — "{user_query}" — return only the chunks from the following list that are directly relevant. Focus on clarity and direct relevance.

    Document Chunks:
    {chunk_texts}
    """

    retrieval_payload = {
        "messages": [
            { "role": "system", "content": "You are a document retriever." },
            { "role": "user", "content": retrieval_prompt }
        ]
    }

    retrieval_response = requests.post(url, headers=headers, json=retrieval_payload)
    relevant_chunks = retrieval_response.json()["choices"][0]["message"]["content"]

    # Step 4: Generate final answer
    answer_prompt = f"""
    Using the following chunks, answer this question concisely and as close as the original text as possible. No need to summarize or paraphrase, just extract the relevant information. Give explanation to the answer when provided by the original text:
    And provide the source document name (example "testing.pdf").

    Question:
    {user_query}

    Chunks:
    {relevant_chunks}
    """

    answer_payload = {
        "messages": [
            { "role": "system", "content": "You are a helpful FAA assistant." },
            { "role": "user", "content": answer_prompt }
        ]
    }

    answer_response = requests.post(url, headers=headers, json=answer_payload)
    final_answer = answer_response.json()["choices"][0]["message"]["content"]

    return { "answer": final_answer }
'''


@app.get("/", response_class=HTMLResponse)
def serve_home():
    with open("index.html", "r") as f:
        return f.read()

@app.get("/ask")
def answer_from_query(q: str):
    return {"message": f"you asked: {q}"}