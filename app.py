#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Document Processor Server
Server Python per la trascrizione locale di documenti PDF, DOCX e TXT
"""

import os
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import PyPDF2
import docx
from pathlib import Path

app = Flask(__name__)
CORS(app)

# Directory per i file temporanei
TEMP_DIR = Path("temp_documents")
TEMP_DIR.mkdir(exist_ok=True)

# File JSON per i documenti trascritti
TRANSCRIPTS_FILE = "transcribed_documents.json"

class DocumentProcessor:
    def __init__(self):
        self.transcripts = self.load_transcripts()
    
    def load_transcripts(self):
        """Carica i documenti trascritti dal file JSON"""
        if os.path.exists(TRANSCRIPTS_FILE):
            try:
                with open(TRANSCRIPTS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {"documents": [], "session_id": str(uuid.uuid4())}
        return {"documents": [], "session_id": str(uuid.uuid4())}
    
    def save_transcripts(self):
        """Salva i documenti trascritti nel file JSON"""
        with open(TRANSCRIPTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.transcripts, f, ensure_ascii=False, indent=2)
    
    def extract_text_from_pdf(self, file_path):
        """Estrae testo da file PDF"""
        text = ""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
        except Exception as e:
            raise Exception(f"Errore nell'estrazione PDF: {str(e)}")
        return text.strip()
    
    def extract_text_from_docx(self, file_path):
        """Estrae testo da file DOCX"""
        try:
            doc = docx.Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            raise Exception(f"Errore nell'estrazione DOCX: {str(e)}")
    
    def extract_text_from_txt(self, file_path):
        """Estrae testo da file TXT"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except UnicodeDecodeError:
            # Prova con encoding diverso
            with open(file_path, 'r', encoding='latin-1') as file:
                return file.read().strip()
        except Exception as e:
            raise Exception(f"Errore nell'estrazione TXT: {str(e)}")
    
    def process_document(self, file_data, filename):
        """Processa un documento e ne estrae il testo"""
        # Salva il file temporaneamente
        file_id = str(uuid.uuid4())
        file_extension = Path(filename).suffix.lower()
        temp_file_path = TEMP_DIR / f"{file_id}{file_extension}"
        
        try:
            # Salva il file
            with open(temp_file_path, 'wb') as f:
                f.write(file_data)
            
            # Estrae il testo in base al tipo di file
            if file_extension == '.pdf':
                text = self.extract_text_from_pdf(temp_file_path)
            elif file_extension in ['.docx', '.doc']:
                text = self.extract_text_from_docx(temp_file_path)
            elif file_extension == '.txt':
                text = self.extract_text_from_txt(temp_file_path)
            else:
                raise Exception(f"Formato file non supportato: {file_extension}")
            
            # Crea il documento trascritto
            document = {
                "id": file_id,
                "filename": filename,
                "text": text,
                "file_type": file_extension,
                "processed_at": datetime.now().isoformat(),
                "word_count": len(text.split()),
                "char_count": len(text)
            }
            
            # Aggiunge alla lista dei documenti
            self.transcripts["documents"].append(document)
            self.save_transcripts()
            
            return document
            
        finally:
            # Rimuove il file temporaneo
            if temp_file_path.exists():
                temp_file_path.unlink()
    
    def get_all_documents(self):
        """Restituisce tutti i documenti trascritti"""
        return self.transcripts["documents"]
    
    def remove_document(self, doc_id):
        """Rimuove un documento dalla lista"""
        self.transcripts["documents"] = [
            doc for doc in self.transcripts["documents"] 
            if doc["id"] != doc_id
        ]
        self.save_transcripts()
    
    def clear_session(self):
        """Pulisce tutti i documenti della sessione"""
        self.transcripts = {"documents": [], "session_id": str(uuid.uuid4())}
        self.save_transcripts()
        
        # Rimuove il file JSON
        if os.path.exists(TRANSCRIPTS_FILE):
            os.remove(TRANSCRIPTS_FILE)

# Inizializza il processore
processor = DocumentProcessor()

@app.route('/process_document', methods=['POST'])
def process_document():
    """Endpoint per processare un documento"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "Nessun file fornito"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Nome file vuoto"}), 400
        
        # Processa il documento
        document = processor.process_document(file.read(), file.filename)
        
        return jsonify({
            "success": True,
            "document": {
                "id": document["id"],
                "filename": document["filename"],
                "file_type": document["file_type"],
                "word_count": document["word_count"],
                "char_count": document["char_count"],
                "processed_at": document["processed_at"]
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_documents', methods=['GET'])
def get_documents():
    """Endpoint per ottenere tutti i documenti trascritti"""
    try:
        documents = processor.get_all_documents()
        return jsonify({
            "success": True,
            "documents": [{
                "id": doc["id"],
                "filename": doc["filename"],
                "file_type": doc["file_type"],
                "word_count": doc["word_count"],
                "char_count": doc["char_count"],
                "processed_at": doc["processed_at"]
            } for doc in documents],
            "session_id": processor.transcripts["session_id"]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_document_text/<doc_id>', methods=['GET'])
def get_document_text(doc_id):
    """Endpoint per ottenere il testo di un documento specifico"""
    try:
        documents = processor.get_all_documents()
        document = next((doc for doc in documents if doc["id"] == doc_id), None)
        
        if not document:
            return jsonify({"error": "Documento non trovato"}), 404
        
        return jsonify({
            "success": True,
            "document": document
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/remove_document/<doc_id>', methods=['DELETE'])
def remove_document(doc_id):
    """Endpoint per rimuovere un documento"""
    try:
        processor.remove_document(doc_id)
        return jsonify({"success": True, "message": "Documento rimosso"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/clear_session', methods=['POST'])
def clear_session():
    """Endpoint per pulire la sessione"""
    try:
        processor.clear_session()
        return jsonify({"success": True, "message": "Sessione pulita"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint per verificare lo stato del server"""
    return jsonify({"status": "ok", "message": "Document processor server is running"})

# Cleanup automatico alla chiusura
import atexit

def cleanup_on_exit():
    """Pulisce tutti i documenti alla chiusura del server"""
    processor = DocumentProcessor()
    processor.clear_session()
    print("\n🧹 Documenti puliti alla chiusura del server")

atexit.register(cleanup_on_exit)

if __name__ == '__main__':
    print("🚀 Server di trascrizione documenti avviato su http://localhost:5000")
    print("📄 Formati supportati: PDF, DOCX, TXT")
    print("🔄 I documenti verranno automaticamente puliti alla chiusura")
    app.run(host='0.0.0.0', port=5000, debug=True)